# check_claim

Asks Claude, through OpenRouter, to fact-check one rumour (C-02) and traces the call in LangSmith.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # then type your own keys and model id into .env
.venv/bin/python check_claim.py
```

All keys and the model id are read from `.env`, which is git-ignored.

## Input

The rumours are read from `data/aws_reinvent_candidate_items.csv`, the candidate list collected 27 Oct – 2 Nov 2025, committed exactly as given (sha256 `e2aebcfa1b2a5bf122c73950907a3ae08330bc1e672a02c07af8559ec177da0a`). `check_claim.py` looks up the row by `candidate_id` and sends its `claim_text` to the model. The whole row is recorded as the input in the LangSmith trace.

## Result

**Model id:** `anthropic/claude-opus-5.5` (OpenRouter)

**Claim C-02** (from the CSV): AWS will launch a managed quantum computing Region in us-east-1 at re:Invent 2025.

**Answer for C-02** (printed by `python check_claim.py` on 2026-10-24):

```
**1. Verdict: UNVERIFIED**

**2. Explanation:** I'm not aware of any official AWS announcement of a dedicated "quantum computing Region," and the claim doesn't fit how AWS works: Regions are geographic infrastructure footprints, while quantum computing is offered as a managed service (Amazon Braket) that already runs in existing Regions, including us-east-1. My information may not fully cover re:Invent 2025, so I can't rule out a related announcement, but you should treat the rumour as unsupported until it appears on AWS's official channels.

**3. Source:** https://aws.amazon.com/braket/. This is AWS's official page for its existing managed quantum service. It doesn't confirm or deny the rumour, but it shows how AWS actually delivers quantum computing. To check for a re:Invent 2025 announcement, look at the AWS News Blog (https://aws.amazon.com/blogs/aws/) and the "What's New" feed (https://aws.amazon.com/new/).
```

**Did it name an aws.amazon.com page?** Yes, it named https://aws.amazon.com/braket/ as background on AWS's existing quantum service and two AWS news feeds as places to check, but none of them as proof that C-02 is a real launch.

**Public LangSmith trace:** https://smith.langchain.com/public/4a64267d-be97-43ea-9857-9f407de8deab/r
