"""Three-node LangGraph pipeline: lead -> researcher -> fact_checker.

Usage: python pipeline.py              (runs every candidate, writes results.md and logs/)
       python pipeline.py C-02 C-05    (runs only those candidates)

Inputs:  data/aws_reinvent_candidate_items.csv   (the claims)
         data/aws_official_source_snapshot.json  (the 40 official AWS pages)
         confirm_rule.md                         (the fact-checker's rule, read from file)
All keys and the model id are read from .env -- nothing is typed in here.
"""
import csv
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.tracers.langchain import wait_for_all_tracers
from langgraph.graph import END, START, StateGraph
from langsmith import Client
from langsmith.wrappers import wrap_openai
from openai import OpenAI

ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT, ".env"))

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
MODEL_ID = os.environ["OPENROUTER_MODEL"]
if not MODEL_ID.startswith("anthropic/"):
    sys.exit(f"OPENROUTER_MODEL must be an anthropic/ id, got {MODEL_ID!r}")
for name in ("LANGSMITH_API_KEY", "LANGSMITH_PROJECT"):
    if not os.environ.get(name):
        sys.exit(f"Missing {name} in .env")

CANDIDATES_CSV = os.path.join(ROOT, "data", "aws_reinvent_candidate_items.csv")
SNAPSHOT_JSON = os.path.join(ROOT, "data", "aws_official_source_snapshot.json")
RULE_FILE = os.path.join(ROOT, "confirm_rule.md")
LOG_DIR = os.path.join(ROOT, "logs")
RESULTS_MD = os.path.join(ROOT, "results.md")
NO_MATCH = "no match"

client = wrap_openai(
    OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
)


def load_candidates():
    with open(CANDIDATES_CSV, encoding="utf-8-sig", newline="") as f:
        return {row["candidate_id"]: row for row in csv.DictReader(f)}


def load_snapshot():
    with open(SNAPSHOT_JSON, encoding="utf-8") as f:
        return {page["page_id"]: page for page in json.load(f)}


def ask_json(system, user):
    """Ask the model and parse the JSON object in its reply."""
    response = client.chat.completions.create(
        model=MODEL_ID,
        max_tokens=1000,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    text = response.choices[0].message.content
    return json.loads(text[text.find("{"): text.rfind("}") + 1]), text


class State(TypedDict, total=False):
    candidate_id: str
    claim: dict
    evidence: dict
    quote_check: dict
    checks: dict
    log: list


# --- Node 1: lead agent hands out the claim --------------------------------
def lead(state):
    row = load_candidates()[state["candidate_id"]]
    claim = {k: row[k] for k in ("candidate_id", "claim_text", "claimed_service")}
    entry = {"node": "lead", "got": {"candidate_id": state["candidate_id"]},
             "csv_row": row, "gave_researcher": claim}
    return {"claim": claim, "log": state["log"] + [entry]}


# --- Node 2: researcher finds a page in the snapshot ------------------------
RESEARCHER_PROMPT = """You are the researcher. Your only source is the AWS official source snapshot below.
Find the ONE snapshot page that best states the facts in the claim (the service, what happened, where).
Copy the sentences that bear on the claim from that page's body_text, character for character.
Never paraphrase, never use your own knowledge, never cite a page that is not in the snapshot.
If no snapshot page covers the claimed service, answer with page_id "no match".

Reply with only this JSON:
{"page_id": "<AWS-SRC-...> or no match", "url": "<that page's url> or no match",
 "captured_at": "<that page's captured_at> or no match",
 "quotes": ["<sentence copied word for word>", ...],
 "why_this_page": "<one line>"}"""


def researcher(state):
    snapshot = load_snapshot()
    user = (f"Claim to research:\n{json.dumps(state['claim'], indent=2)}\n\n"
            f"Snapshot (captured 3 November 2025):\n{json.dumps(list(snapshot.values()), indent=1)}")
    evidence, raw = ask_json(RESEARCHER_PROMPT, user)
    if evidence.get("page_id") not in snapshot:
        evidence = {"page_id": NO_MATCH, "url": NO_MATCH, "captured_at": NO_MATCH,
                    "quotes": [], "why_this_page": evidence.get("why_this_page", NO_MATCH)}

    # Code check, independent of the model: does every quote appear word for
    # word in that page's body_text, and do the url and captured_at match?
    page = snapshot.get(evidence["page_id"])
    if page:
        quote_check = {
            "url_matches_page_id": evidence.get("url") == page["url"],
            "captured_at_matches": evidence.get("captured_at") == page["captured_at"],
            "quotes": [{"quote": q, "word_for_word": q in page["body_text"]}
                       for q in evidence.get("quotes", [])],
        }
        quote_check["all_quotes_match"] = bool(quote_check["quotes"]) and all(
            q["word_for_word"] for q in quote_check["quotes"])
    else:
        quote_check = {"all_quotes_match": NO_MATCH, "quotes": []}

    entry = {"node": "researcher", "got": state["claim"], "gave_fact_checker": evidence,
             "quote_check_by_code": quote_check, "raw_model_reply": raw}
    return {"evidence": evidence, "quote_check": quote_check, "log": state["log"] + [entry]}


# --- Node 3: fact-checker answers the checks from confirm_rule.md ----------
FACT_CHECKER_FORMAT = """Reply with only this JSON:
{"check_1": "yes" or "no", "check_1_why": "<one line>",
 "check_2": "yes" or "no", "check_2_why": "<one line>",
 "check_3": "yes" or "no", "check_3_why": "<one line>",
 "verdict": "confirmed" or "rejected",
 "reason": "<one line>"}"""


def fact_checker(state):
    with open(RULE_FILE, encoding="utf-8") as f:
        rule = f.read()
    system = ("You are the fact-checker. Follow this rule card exactly. Use only the researcher's "
              "page and quotes; never use your own knowledge.\n\n" + rule + "\n\n" + FACT_CHECKER_FORMAT)
    user = (f"Claim:\n{json.dumps(state['claim'], indent=2)}\n\n"
            f"Researcher's evidence:\n{json.dumps(state['evidence'], indent=2)}")
    checks, raw = ask_json(system, user)
    answers = [checks.get(f"check_{i}") for i in (1, 2, 3)]
    checks["verdict_follows_checks"] = (
        checks.get("verdict") == ("confirmed" if answers == ["yes"] * 3 else "rejected"))
    entry = {"node": "fact_checker", "got": {"claim": state["claim"], "evidence": state["evidence"]},
             "rule_file": "confirm_rule.md", "gave": checks, "raw_model_reply": raw}
    return {"checks": checks, "log": state["log"] + [entry]}


graph = StateGraph(State)
graph.add_node("lead", lead)
graph.add_node("researcher", researcher)
graph.add_node("fact_checker", fact_checker)
graph.add_edge(START, "lead")
graph.add_edge("lead", "researcher")
graph.add_edge("researcher", "fact_checker")
graph.add_edge("fact_checker", END)
app = graph.compile()


def share(run_id):
    """Make one run's LangSmith trace public; retry while it is still being ingested."""
    ls = Client()
    for _ in range(10):
        try:
            return ls.share_run(run_id)
        except Exception:
            time.sleep(3)
    return f"not shared (run {run_id})"


def cell(value):
    text = str(value).replace("|", "\\|").replace("\n", " ").strip()
    return text or NO_MATCH


def write_results(rows):
    lines = [
        "# Results",
        "",
        f"Pipeline: `pipeline.py` (LangGraph: lead -> researcher -> fact_checker), model `{MODEL_ID}` via OpenRouter. "
        "The fact-checker's rule is read from `confirm_rule.md`. Sources: `data/aws_official_source_snapshot.json`. "
        "\"Quotes match snapshot\" is checked by code, not by the model: every quote must appear word for word "
        "in that page's body_text.",
        "",
        "| Candidate | Claim | Page | Check 1 | Check 2 | Check 3 | Verdict | Reason | Quotes match snapshot | Trace | Log |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        ev, qc, ch = r["evidence"], r["quote_check"], r["checks"]
        page = NO_MATCH if ev["page_id"] == NO_MATCH else f"{ev['page_id']}: {ev['url']}"
        match = qc["all_quotes_match"]
        match = NO_MATCH if match == NO_MATCH else ("yes" if match else "no")
        lines.append("| " + " | ".join(cell(v) for v in [
            r["candidate_id"], r["claim"]["claim_text"], page,
            ch.get("check_1"), ch.get("check_2"), ch.get("check_3"),
            ch.get("verdict"), ch.get("reason"), match,
            f"[trace]({r['trace_url']})", f"[log](logs/{r['candidate_id']}.json)",
        ]) + " |")
    with open(RESULTS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    ids = sys.argv[1:] or list(load_candidates())
    os.makedirs(LOG_DIR, exist_ok=True)
    runs = []
    for cid in ids:
        run_id = uuid.uuid4()
        started = datetime.now(timezone.utc).isoformat()
        state = app.invoke({"candidate_id": cid, "log": []},
                           config={"run_id": run_id, "run_name": f"pipeline {cid}", "tags": [cid]})
        runs.append((cid, run_id, started, state))
        print(f"{cid}: {state['checks'].get('verdict')} | page {state['evidence']['page_id']} | "
              f"quotes match: {state['quote_check']['all_quotes_match']}")

    wait_for_all_tracers()
    rows = []
    for cid, run_id, started, state in runs:
        trace_url = share(run_id)
        record = {"candidate_id": cid, "model": MODEL_ID, "run_id": str(run_id), "started_at": started,
                  "trace_url": trace_url, **state}
        with open(os.path.join(LOG_DIR, f"{cid}.json"), "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        rows.append(record)
    write_results(rows)
    print(f"Wrote {RESULTS_MD} and {len(rows)} logs in {LOG_DIR}")
