"""Three-node LangGraph pipeline: lead -> researcher -> fact_checker.

Usage: python pipeline.py              (runs every candidate, writes results.md and logs/)
       python pipeline.py <candidate_id> ...  (runs only those candidates)

Inputs:  data/aws_reinvent_candidate_items.csv   (the claims)
         data/aws_official_source_snapshot.json  (the 40 official AWS pages)
         confirm_rule.md                         (the fact-checker's rule, read from file)
All keys and the model id are read from .env -- nothing is typed in here.
"""
import csv
import html as html_lib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import TypedDict
from urllib.parse import urlparse

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

# The batch, snapshot and output folder can be changed with environment variables.
CANDIDATES_CSV = os.path.join(ROOT, os.environ.get("CANDIDATES_CSV", "data/aws_reinvent_candidate_items_holdout.csv"))
SNAPSHOT_JSON = os.path.join(ROOT, os.environ.get("SNAPSHOT_JSON", "data/aws_official_source_snapshot_refresh.json"))
RULE_FILE = os.path.join(ROOT, "confirm_rule.md")
OUT_DIR = os.path.join(ROOT, os.environ.get("OUT_DIR", "final"))
LOG_DIR = os.path.join(OUT_DIR, "logs")
RESULTS_MD = os.path.join(OUT_DIR, "results.md")
BRIEFING_HTML = os.path.join(ROOT, "briefing.html")
NO_MATCH = "no match"

client = wrap_openai(
    OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
)


def say(text=""):
    """Print each line with a UTC timestamp, so the saved run output proves the order of steps."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    for line in str(text).splitlines() or [""]:
        print(f"[{stamp}] {line}", flush=True)


def load_candidates():
    with open(CANDIDATES_CSV, encoding="utf-8-sig", newline="") as f:
        return {row["candidate_id"]: row for row in csv.DictReader(f)}


def load_snapshot():
    with open(SNAPSHOT_JSON, encoding="utf-8") as f:
        return {page["page_id"]: page for page in json.load(f)}


def ask_json(system, user):
    """Ask the model and parse the JSON object in its reply; retry with the parse error."""
    messages = [{"role": "system", "content": system + "\nReturn valid JSON: escape any double quote inside a string as \\\"."},
                {"role": "user", "content": user}]
    for attempt in range(3):
        response = client.chat.completions.create(model=MODEL_ID, max_tokens=1000, messages=messages)
        text = response.choices[0].message.content or ""  # an empty reply is retried like bad JSON
        try:
            return json.loads(text[text.find("{"): text.rfind("}") + 1]), text
        except json.JSONDecodeError as err:
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": f"That was not valid JSON ({err}). Reply again with only valid JSON."}]
    raise ValueError(f"No valid JSON after 3 attempts: {text}")


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
# Checks 1 and 2 are mechanical, so code answers them. Check 3 needs judgment,
# so the model matches every fact in the claim to the quote that backs it, and
# code confirms each backing quote is one of the researcher's quotes. The
# verdict is computed from the three answers: confirmed only if all are yes.
FACT_CHECKER_FORMAT = """Answer check 3 only. Split the claim into every separate fact it states
(the service, what happened or its status, where, and any other detail).
For each fact, give the number of the one quote in the researcher's numbered list that backs it,
or 0 if no quote states that fact. A quote that is only related or background does not back a fact.
"Backed" means the quote states the same fact in meaning; the claim may use different words with the
same meaning. Word-for-word copying applies to the quotes, which is check 2, not to the claim's wording.
A quote does NOT back a fact if it states a different status or stage, a narrower place or scope,
or does not mention that detail at all.

Reply with only this JSON:
For every fact that is not backed, also write "sentence": one short plain sentence a solutions architect
could say to a customer, stating what the claim says and what the AWS page says instead.
No labels, tags, brackets or quote numbers. For a backed fact, "sentence" is "".

{"facts": [{"fact": "<fact from the claim>", "backing_quote_number": <number, or 0>,
            "backed": "yes" or "no", "why": "<a few words>", "sentence": "<plain sentence, or empty>"}],
 "check_3_why": "<one line>"}"""


def check_1_source(evidence, page):
    """Yes only if the page is in the snapshot, its host is exactly aws.amazon.com,
    and the researcher's url and captured_at match that snapshot page."""
    if page is None:
        return "no", f"No snapshot page was cited (page_id: {evidence.get('page_id', NO_MATCH)})."
    host = urlparse(evidence.get("url", "")).hostname
    if host != "aws.amazon.com":
        return "no", f"The cited host is {host}, not aws.amazon.com."
    if evidence.get("url") != page["url"] or evidence.get("captured_at") != page["captured_at"]:
        return "no", f"The cited url or captured_at does not match snapshot page {page['page_id']}."
    return "yes", f"Snapshot page {page['page_id']} on aws.amazon.com, captured {page['captured_at']}."


def check_2_quotes(evidence, page):
    """Yes only if there is at least one quote and every quote is in the page's body_text."""
    quotes = evidence.get("quotes", [])
    if page is None or not quotes:
        return "no", "There are no quotes from a snapshot page."
    missing = [q for q in quotes if q not in page["body_text"]]
    if missing:
        return "no", f"Not word for word on {page['page_id']}: {missing[0]!r}"
    return "yes", f"All {len(quotes)} quotes appear word for word on {page['page_id']}."


def fact_checker(state):
    with open(RULE_FILE, encoding="utf-8") as f:
        rule = f.read()
    evidence = state["evidence"]
    page = load_snapshot().get(evidence.get("page_id"))
    check_1, check_1_why = check_1_source(evidence, page)
    check_2, check_2_why = check_2_quotes(evidence, page)

    raw = None
    facts = []
    if evidence.get("quotes"):
        system = ("You are the fact-checker. Follow this rule card exactly. Use only the researcher's "
                  "quotes; never use your own knowledge.\n\n" + rule + "\n\n" + FACT_CHECKER_FORMAT)
        user = (f"Claim:\n{state['claim']['claim_text']}\n\n"
                "Researcher's quotes:\n" + "\n".join(f"{n}. {q}" for n, q in enumerate(evidence["quotes"], 1)))
        answer, raw = ask_json(system, user)
        facts = answer.get("facts", [])
        check_3_why = answer.get("check_3_why", "")
    # Every fact must be backed by a quote that really is one of the researcher's quotes.
    quotes = evidence.get("quotes", [])
    for fact in facts:
        n = fact.get("backing_quote_number")
        fact["backing_quote"] = quotes[n - 1] if isinstance(n, int) and 1 <= n <= len(quotes) else "none"
        fact["backed_by_researcher_quote"] = fact["backing_quote"] in quotes
    backed = bool(facts) and all(
        f.get("backed") == "yes" and f["backed_by_researcher_quote"] for f in facts)
    check_3 = "yes" if backed else "no"
    if not facts:
        check_3_why = "There are no quotes to back the claim's facts."
    elif not backed:
        unbacked = [f for f in facts if not (f.get("backed") == "yes" and f["backed_by_researcher_quote"])]
        check_3_why = "Not backed by any quote: " + "; ".join(
            f"{f.get('fact')} ({f.get('why', '').strip()})" for f in unbacked)

    answers = {1: (check_1, check_1_why), 2: (check_2, check_2_why), 3: (check_3, check_3_why)}
    failed = [n for n, (a, _) in answers.items() if a == "no"]
    verdict = "rejected" if failed else "confirmed"
    reason = (f"Check {failed[0]} failed: {answers[failed[0]][1]}" if failed
              else f"All three checks passed: {check_3_why}")
    checks = {"check_1": check_1, "check_1_why": check_1_why,
              "check_2": check_2, "check_2_why": check_2_why,
              "check_3": check_3, "check_3_why": check_3_why,
              "facts": facts, "verdict": verdict, "reason": reason}
    entry = {"node": "fact_checker", "got": {"claim": state["claim"], "evidence": evidence},
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
        f"The fact-checker's rule is read from `confirm_rule.md`. Sources: `{os.path.relpath(SNAPSHOT_JSON, ROOT)}`. "
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


# --- Lead's last step: sort results into confirmed and rejected lists -------
LISTS_JSON = os.path.join(OUT_DIR, "briefing_lists.json")
PUBLIC_TRACE_PREFIX = "https://smith.langchain.com/public/"


def load_records():
    """Every run record in logs/, one per candidate."""
    return [json.load(open(os.path.join(LOG_DIR, name), encoding="utf-8"))
            for name in sorted(os.listdir(LOG_DIR)) if name.endswith(".json")]


def readable_reason(record):
    """Turn the fact-checker's output into one sentence a reader can repeat, with no
    internal references such as quote numbers or check numbers."""
    evidence, checks = record["evidence"], record["checks"]
    quotes = evidence.get("quotes", [])
    if evidence.get("page_id") == NO_MATCH:
        return "No official AWS page in the snapshot states this claim."
    if checks.get("check_1") == "no":
        return "The cited source is not an aws.amazon.com page in the snapshot."
    if checks.get("check_2") == "no":
        return "A quoted sentence does not appear word for word on the AWS page."

    seen = set()

    def resolve(text):  # "quote 2" -> the sentence itself the first time, "that sentence" after
        def sub(m):
            n = int(m.group(1))
            if not 0 < n <= len(quotes):
                return "the page"
            if n in seen:
                return "that sentence"
            seen.add(n)
            return f'the page sentence "{quotes[n - 1]}"'
        return re.sub(r"\b[Qq]uote (\d+)", sub, text).strip().rstrip(".")

    unbacked = [f for f in checks.get("facts", []) if f.get("backed") != "yes"]
    sentences = [str(f.get("sentence", "")).strip() for f in unbacked]
    if unbacked and all(sentences):  # the fact-checker's plain sentence for each failed fact
        return " ".join(x if x.endswith(".") else x + "." for x in sentences)
    if not unbacked:
        return resolve(checks.get("check_3_why", "The AWS page does not back the claim")) + "."
    return "The AWS page does not back " + "; ".join(
        f'"{f.get("fact")}" ({resolve(f.get("why", ""))})' for f in unbacked) + "."


def sort_results(records):
    confirmed, rejected = [], []
    for r in records:
        if r["checks"]["verdict"] == "confirmed":
            confirmed.append({"candidate_id": r["candidate_id"], "claim": r["claim"]["claim_text"],
                              "url": r["evidence"]["url"], "quotes": r["evidence"]["quotes"],
                              "trace_url": r["trace_url"]})
        else:
            item = {"candidate_id": r["candidate_id"], "claim": r["claim"]["claim_text"],
                    "reason": readable_reason(r), "trace_url": r["trace_url"]}
            if r["evidence"].get("page_id") != NO_MATCH:  # the AWS page the researcher found and checked
                item["url"] = r["evidence"]["url"]
            rejected.append(item)
    return confirmed, rejected


def check_confirmed(items):
    """Every confirmed item needs an aws.amazon.com snapshot link, quotes found word for
    word on that page, and a public trace link. Returns the problems found."""
    pages = {p["url"]: p for p in load_snapshot().values()}
    problems = []
    for item in items:
        cid, url = item.get("candidate_id"), item.get("url", "")
        if urlparse(url).hostname != "aws.amazon.com":
            problems.append(f"{cid}: confirmed with a non-aws.amazon.com link: {url}")
        elif url not in pages:
            problems.append(f"{cid}: confirmed with a link that is not a snapshot page: {url}")
        if not item.get("quotes"):
            problems.append(f"{cid}: confirmed with no quote")
        for q in item.get("quotes", []):
            if url in pages and q not in pages[url]["body_text"]:
                problems.append(f"{cid}: quote not word for word on {url}: {q!r}")
        if not str(item.get("trace_url", "")).startswith(PUBLIC_TRACE_PREFIX):
            problems.append(f"{cid}: no public trace link")
    return problems


def check_rejected(items):
    """Every rejected item needs a readable reason (no internal quote or check numbers),
    an aws.amazon.com link if it cites a page, and a public trace link."""
    problems = []
    for item in items:
        cid = item.get("candidate_id")
        reason = str(item.get("reason", "")).strip()
        if not reason:
            problems.append(f"{cid}: rejected with no reason")
        if re.search(r"\b([Qq]uote|[Cc]heck) \d", reason):
            problems.append(f"{cid}: reason points to an internal quote or check number: {reason!r}")
        if "url" in item and urlparse(item["url"]).hostname != "aws.amazon.com":
            problems.append(f"{cid}: rejected item links a non-aws.amazon.com page: {item['url']}")
        if not str(item.get("trace_url", "")).startswith(PUBLIC_TRACE_PREFIX):
            problems.append(f"{cid}: no public trace link")
    return problems


def build_lists():
    """Sort, run both safety checks, and stop before writing if either fails."""
    confirmed, rejected = sort_results(load_records())
    problems = check_confirmed(confirmed) + check_rejected(rejected)
    if problems:
        say("STOPPED: safety gate failed; briefing lists not written.")
        for p in problems:
            say(f"  - {p}")
        sys.exit(1)
    with open(LISTS_JSON, "w", encoding="utf-8") as f:
        json.dump({"confirmed": confirmed, "rejected": rejected}, f, indent=2, ensure_ascii=False)
    say(f"PASSED: safety gate; {len(confirmed)} confirmed, {len(rejected)} rejected -> {os.path.relpath(LISTS_JSON, ROOT)}")


def run_safety_tests():
    """Run the pytest safety checks; stop before the page is built if any fails."""
    say("$ python -m pytest tests/test_safety.py -v")
    test = subprocess.run([sys.executable, "-m", "pytest", "tests/test_safety.py", "-v", "-p", "no:warnings"],
                          cwd=ROOT, capture_output=True, text=True)
    say("\n".join(l for l in test.stdout.splitlines() if "::" in l or "passed" in l or "failed" in l))
    if test.returncode != 0:
        say("STOPPED: safety checks failed; briefing.html not built.")
        sys.exit(1)


def build_page():
    """Write briefing.html from the lists that passed the safety gate."""
    with open(LISTS_JSON, encoding="utf-8") as f:
        lists = json.load(f)
    items = sorted([dict(i, status="confirmed") for i in lists["confirmed"]] +
                   [dict(i, status="rejected") for i in lists["rejected"]], key=lambda i: i["candidate_id"])
    cards = []
    for i in items:
        if i["status"] == "confirmed":
            body = (f'<p class="src">Source: <a href="{esc(i["url"])}">{esc(i["url"])}</a></p>'
                    + "".join(f"<blockquote>{esc(q)}</blockquote>" for q in i["quotes"]))
        else:
            body = f'<p class="reason"><strong>Why rejected:</strong> {esc(i["reason"])}</p>'
            if i.get("url"):
                body += f'<p class="src">AWS page checked: <a href="{esc(i["url"])}">{esc(i["url"])}</a></p>'
        cards.append(
            f'<article class="{i["status"]}"><header><span class="badge">{i["status"].capitalize()}</span>'
            f'<span class="id">{esc(i["candidate_id"])}</span></header>'
            f'<p class="claim">{esc(i["claim"])}</p>{body}'
            f'<p class="trace"><a href="{esc(i["trace_url"])}">How this was judged (LangSmith trace)</a></p></article>')
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    n_ok = len(lists["confirmed"])
    html = PAGE_TEMPLATE.format(cards="\n".join(cards), built=built, n_ok=n_ok,
                                n_no=len(items) - n_ok, snapshot=esc(os.path.basename(SNAPSHOT_JSON)))
    with open(BRIEFING_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    say(f"Built {os.path.relpath(BRIEFING_HTML, ROOT)}: {len(items)} items ({n_ok} confirmed, {len(items) - n_ok} rejected)")


def esc(text):
    return html_lib.escape(str(text))


PAGE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>re:Invent Launch Briefing</title>
<style>
:root {{ --bg:#f7f7f5; --card:#fff; --ink:#1d1d1f; --muted:#5f6368; --line:#e3e3e0;
  --ok:#0b6b3a; --ok-bg:#e3f4ea; --no:#9b1c1c; --no-bg:#fbe7e7; --link:#0b57d0; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#121214; --card:#1c1c1f; --ink:#ececec; --muted:#a0a0a8;
  --line:#2e2e33; --ok:#7fd8a4; --ok-bg:#183626; --no:#f2a3a3; --no-bg:#3a1c1c; --link:#8ab4f8; }} }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 system-ui, -apple-system, sans-serif; }}
main {{ max-width:760px; margin:0 auto; padding:32px 16px 48px; }}
h1 {{ font-size:1.6rem; margin:0 0 4px; }} .sub {{ color:var(--muted); margin:0 0 24px; }}
article {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; margin:0 0 14px; }}
header {{ display:flex; align-items:center; gap:10px; margin-bottom:6px; }}
.badge {{ font-size:.78rem; font-weight:700; letter-spacing:.03em; text-transform:uppercase; padding:3px 9px; border-radius:999px; }}
.confirmed .badge {{ color:var(--ok); background:var(--ok-bg); }} .rejected .badge {{ color:var(--no); background:var(--no-bg); }}
.id {{ color:var(--muted); font-size:.85rem; }} .claim {{ font-weight:600; margin:4px 0 10px; }}
blockquote {{ margin:8px 0; padding:6px 12px; border-left:3px solid var(--ok); color:var(--ink); background:var(--ok-bg); border-radius:0 6px 6px 0; }}
a {{ color:var(--link); overflow-wrap:anywhere; }} .src, .reason, .trace {{ margin:6px 0; }} .trace {{ font-size:.9rem; }}
footer {{ color:var(--muted); font-size:.85rem; border-top:1px solid var(--line); padding-top:14px; margin-top:24px; }}
</style></head>
<body><main>
<h1>re:Invent Launch Briefing</h1>
<p class="sub">{n_ok} confirmed, {n_no} rejected. Repeat only the confirmed items: each one is backed by an aws.amazon.com page, quoted word for word.</p>
{cards}
<footer>Built {built}. The safety checks are not vouched for by this page: the timestamped <a href="https://github.com/thehephaistos/check-claim/blob/main/final/run_output.txt">run output</a> shows pytest passing before the line that builds this page.
Sources: official AWS pages saved in {snapshot}. Each item links to the LangSmith trace of the run that judged it.</footer>
</main></body></html>
"""


if __name__ == "__main__":
    if sys.argv[1:] == ["--lists-only"]:  # rebuild the lists from logs/ without calling the model
        build_lists()
        sys.exit(0)
    ids = sys.argv[1:] or list(load_candidates())
    os.makedirs(LOG_DIR, exist_ok=True)
    runs = []
    for cid in ids:
        run_id = uuid.uuid4()
        started = datetime.now(timezone.utc).isoformat()
        state = app.invoke({"candidate_id": cid, "log": []},
                           config={"run_id": run_id, "run_name": f"pipeline {cid}", "tags": [cid]})
        runs.append((cid, run_id, started, state))
        say(f"{cid}: {state['checks'].get('verdict')} | page {state['evidence']['page_id']} | "
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
    say(f"Wrote {os.path.relpath(RESULTS_MD, ROOT)} and {len(rows)} logs in {os.path.relpath(LOG_DIR, ROOT)}")
    build_lists()
    run_safety_tests()
    build_page()
