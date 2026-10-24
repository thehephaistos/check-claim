# check_claim

Asks Claude to fact-check one rumour (C-02) and traces the call in LangSmith.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # then type your own keys and model id into .env
.venv/bin/python check_claim.py
```

All keys and the model id are read from `.env`, which is git-ignored.

## Result

**Model id:** `MODEL_ID_HERE`

**Answer for C-02:**

```
ANSWER_HERE
```

**Did it name an aws.amazon.com page?** YES_OR_NO_HERE

**Public LangSmith trace:** TRACE_LINK_HERE
