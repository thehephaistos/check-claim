"""Ask Claude to fact-check one rumour and print its answer.

Usage: python check_claim.py [CLAIM_ID]   (default: C-02)

All keys and the model id are read from .env -- nothing is typed in here.
"""
import json
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv
from langsmith import traceable
from langsmith.wrappers import wrap_anthropic

load_dotenv()

# Every setting comes from .env.
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL_ID = os.environ["ANTHROPIC_MODEL"]
# LangSmith reads LANGSMITH_API_KEY, LANGSMITH_TRACING and LANGSMITH_PROJECT
# from the environment itself; we only check they are present.
for name in ("LANGSMITH_API_KEY", "LANGSMITH_PROJECT"):
    if not os.environ.get(name):
        sys.exit(f"Missing {name} in .env")

client = wrap_anthropic(Anthropic(api_key=ANTHROPIC_API_KEY))

PROMPT = """You are a careful fact-checker. Evaluate this rumour:

"{claim}"

Reply with:
1. Verdict: TRUE, FALSE, or UNVERIFIED.
2. A two-sentence explanation.
3. The single best official source URL that supports your verdict, or "none" if you are not sure one exists. Do not invent URLs."""


def load_claim(claim_id):
    with open(os.path.join(os.path.dirname(__file__), "claims.json")) as f:
        claims = json.load(f)
    return claims[claim_id]


@traceable(name="check_claim")
def check_claim(claim_id):
    claim = load_claim(claim_id)
    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT.format(claim=claim)}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


if __name__ == "__main__":
    claim_id = sys.argv[1] if len(sys.argv) > 1 else "C-02"
    print(f"Model: {MODEL_ID}")
    print(f"Claim {claim_id}: {load_claim(claim_id)}\n")
    print(check_claim(claim_id))
