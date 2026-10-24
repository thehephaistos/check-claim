"""Ask Claude (through OpenRouter) to fact-check one rumour and print its answer.

Usage: python check_claim.py [CANDIDATE_ID]   (default: C-02)

The rumour is read from data/aws_reinvent_candidate_items.csv.
All keys and the model id are read from .env -- nothing is typed in here.
"""
import csv
import os
import sys

from dotenv import load_dotenv
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Every setting comes from .env.
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
MODEL_ID = os.environ["OPENROUTER_MODEL"]  # an OpenRouter id, e.g. anthropic/...
if not MODEL_ID.startswith("anthropic/"):
    sys.exit(f"OPENROUTER_MODEL must be an anthropic/ id, got {MODEL_ID!r}")
# LangSmith reads LANGSMITH_API_KEY, LANGSMITH_TRACING and LANGSMITH_PROJECT
# from the environment itself; we only check they are present.
for name in ("LANGSMITH_API_KEY", "LANGSMITH_PROJECT"):
    if not os.environ.get(name):
        sys.exit(f"Missing {name} in .env")

client = wrap_openai(
    OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
)

PROMPT = """You are a careful fact-checker. Evaluate this rumour:

"{claim}"

Reply with:
1. Verdict: TRUE, FALSE, or UNVERIFIED.
2. A two-sentence explanation.
3. The single best official source URL that supports your verdict, or "none" if you are not sure one exists. Do not invent URLs."""


CANDIDATES_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "aws_reinvent_candidate_items.csv"
)


def load_candidate(candidate_id):
    """Return the full CSV row for one candidate_id."""
    with open(CANDIDATES_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["candidate_id"] == candidate_id:
                return row
    sys.exit(f"{candidate_id} not found in {CANDIDATES_CSV}")


# The whole CSV row is the traced input, so the trace shows exactly which
# candidate row the model was asked about.
@traceable(name="check_claim")
def check_claim(candidate):
    response = client.chat.completions.create(
        model=MODEL_ID,
        max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT.format(claim=candidate["claim_text"])}],
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    candidate_id = sys.argv[1] if len(sys.argv) > 1 else "C-02"
    candidate = load_candidate(candidate_id)
    print(f"Model: {MODEL_ID}")
    print(f"Source: data/aws_reinvent_candidate_items.csv, row {candidate_id}")
    print(f"Claim: {candidate['claim_text']}\n")
    print(check_claim(candidate))
