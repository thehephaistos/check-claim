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

**What the UNVERIFIED verdict rests on:** only the model's existing knowledge and its own reasoning that AWS Regions are geographic footprints, not technology-specific offerings. The script gives the model no web access, so it checked no live source, and none of the aws.amazon.com pages it named confirms or denies the rumour.

**Did it name an aws.amazon.com page?** Yes, it named https://aws.amazon.com/braket/ as background on AWS's existing quantum service and two AWS news feeds as places to check, but none of them as proof that C-02 is a real launch.

**Public LangSmith trace:** https://smith.langchain.com/public/4a64267d-be97-43ea-9857-9f407de8deab/r

## Next step: what "confirmed" means

[confirm_rule.md](confirm_rule.md) sets the three YES/NO checks (source, quote, facts) a claim must pass to be CONFIRMED, what the lead agent, researcher and fact-checker each do, and worked examples for C-01 (CONFIRMED) and C-05 (REJECTED) quoted word for word from `data/aws_official_source_snapshot.json`, the official AWS source snapshot captured 3 November 2025.

## Stage 3: agent team pipeline

`pipeline.py` is a LangGraph graph with exactly three nodes that run in order: **lead** (reads the candidate row from the CSV and hands out the claim), **researcher** (finds one page in `data/aws_official_source_snapshot.json` and copies its sentences word for word, or returns "no match"), and **fact_checker** (reads its rule from `confirm_rule.md` at run time and answers the three checks). Code, not the model, checks that every quote appears word for word in the page's `body_text`.

```bash
.venv/bin/python pipeline.py        # runs all five candidates
```

[results.md](results.md) has one row per candidate with its checks, verdict, reason, public LangSmith trace and the log of that run (`logs/C-0X.json`, which records what each node got and gave back). Model: `anthropic/claude-haiku-5.5` via OpenRouter.

## Stage 4: audit and fix

[audit.md](audit.md) checks each first-run verdict against `confirm_rule.md`, names the agent at fault (the fact-checker, for a wrong check 2 on C-05), describes the fix in `pipeline.py`, and links the five new LangSmith traces with each quote copied word for word from the snapshot. [results.md](results.md) and `logs/` hold the new run.

## Stage 5: safety gate

At the end of `pipeline.py` the lead sorts the results into confirmed and rejected lists (`briefing_lists.json`). `tests/test_safety.py` checks both lists (`python -m pytest`), and the pipeline stops before writing the lists if either check fails. [checks.md](checks.md) holds a passing run and a stopped run with one planted bad item (a confirmed item citing a blog URL), since removed.

## Final: live briefing

**Live briefing page:** https://thehephaistos.github.io/check-claim/briefing.html

Built by `pipeline.py` from `data/aws_reinvent_candidate_items_holdout.csv` (the 3 November 2025 batch), checked against `data/aws_official_source_snapshot_refresh.json`. The page only shows items that passed the safety gate and `tests/test_safety.py`; each item has its badge, its AWS link and quote (confirmed) or reason (rejected), and its public LangSmith trace.

- [final/run_output.txt](final/run_output.txt): the final run's output; the safety checks pass before the line that builds `briefing.html`.
- [final/results.md](final/results.md), `final/logs/`, `final/briefing_lists.json`: the final run's results, per-claim logs and lists.
- [spotcheck.md](spotcheck.md): one row per confirmed item, naming the exact words on the AWS page that back each fact.
