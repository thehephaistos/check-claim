# Spot check

One row per **confirmed** item on `briefing.html`. Every row is checked against the **snapshot refresh** (`data/aws_official_source_snapshot_refresh.json`, Official AWS Source Snapshot Refresh, 3 November 2025), not against the candidate's own source link.

How each row is checked:

1. The claim is copied word for word from `data/aws_reinvent_candidate_items_holdout.csv`.
2. The page is found in the snapshot refresh by its page ID.
3. The quote shown on the briefing must appear word for word in that page's `body_text`.
4. Each fact in the claim is listed with the exact words **inside that quote** that back it. A fact is backed only if those words state the same thing (same status, scope, numbers and dates).
5. The row passes only if every fact is backed.

Steps 3 and 4 were checked by script: the quote against the refresh `body_text`, and each backing phrase against the quote.

| Candidate | Claim | Snapshot refresh page | Quote shown on the briefing | Quote word for word in the refresh? | Fact → exact words in the quote → backed? | Result |
|---|---|---|---|---|---|---|
| RIV-HO-01 | Amazon Quick Suite is now generally available, giving business users one agentic workspace for research, business intelligence and workflow automation. | AWSPG-R07: https://aws.amazon.com/quicksuite/ | "Amazon Quick Suite is now generally available, giving business users one agentic workspace for research, business intelligence and workflow automation." | yes | Service: Amazon Quick Suite → "Amazon Quick Suite" → yes<br>Status: now generally available → "is now generally available" → yes<br>Audience: business users → "giving business users" → yes<br>One agentic workspace → "one agentic workspace" → yes<br>For research → "for research" → yes<br>For business intelligence → "business intelligence" → yes<br>For workflow automation → "workflow automation" → yes | Pass: the quote backs every fact. |
| RIV-HO-02 | Anthropic's Claude Sonnet 4.5 is now available in Amazon Bedrock, supporting long-running agent tasks and complex coding workloads for enterprise builders. | AWSPG-R08: https://aws.amazon.com/bedrock/anthropic/ | "Anthropic's Claude Sonnet 4.5 is now available in Amazon Bedrock, with support for long-running agent tasks and complex coding workloads for enterprise builders." | yes | Model: Anthropic's Claude Sonnet 4.5 → "Anthropic's Claude Sonnet 4.5" → yes<br>Status: now available → "is now available" → yes<br>Place: in Amazon Bedrock → "in Amazon Bedrock" → yes<br>Supports long-running agent tasks → "with support for long-running agent tasks" → yes<br>Supports complex coding workloads → "complex coding workloads" → yes<br>For enterprise builders → "for enterprise builders" → yes | Pass: the quote backs every fact. Claim says "supporting", the quote says "with support for": same meaning. |
| RIV-HO-03 | Starting 15 July 2025 new AWS customers receive $100 in AWS Free Tier credits at sign-up and can earn up to $100 more by exploring key services. | AWSPG-R09: https://aws.amazon.com/free/ | "Starting July 15, 2025, new AWS customers receive $100 in AWS Free Tier credits at sign-up and can earn up to $100 more by exploring key AWS services." | yes | Start date: 15 July 2025 → "Starting July 15, 2025" → yes<br>Who: new AWS customers → "new AWS customers" → yes<br>Receive $100 in AWS Free Tier credits → "receive $100 in AWS Free Tier credits" → yes<br>When: at sign-up → "at sign-up" → yes<br>Can earn up to $100 more → "can earn up to $100 more" → yes<br>By exploring key services → "by exploring key AWS services" → yes | Pass: the quote backs every fact. Claim writes "15 July 2025" and "key services", the quote says "July 15, 2025" and "key AWS services": same date and meaning. |

## Link check (logged out)

Each link on the live briefing was opened logged out (no cookies, no LangSmith key) after the final deploy. For each trace, the run data was loaded through LangSmith's public API and its verdict compared with the page's badge.

| Link | URL | Checked at | Result |
|---|---|---|---|
| Live briefing | https://thehephaistos.github.io/check-claim/briefing.html | 2026-11-16 11:58:13 UTC | Loads; identical to `briefing.html` in the repo: yes |
| RIV-HO-01 trace | https://smith.langchain.com/public/fae79afc-04a7-4ff8-aeed-092dc1ed41f7/r | 2026-11-16 11:58:14 UTC | Page 200; run `pipeline RIV-HO-01` loads without login, verdict confirmed, matches the Confirmed badge: yes |
| RIV-HO-02 trace | https://smith.langchain.com/public/eefce80a-4e66-4fb3-91f1-70ebd08789a3/r | 2026-11-16 11:58:17 UTC | Page 200; run `pipeline RIV-HO-02` loads without login, verdict confirmed, matches the Confirmed badge: yes |
| RIV-HO-03 trace | https://smith.langchain.com/public/453031d0-c17d-464a-b4ec-78a44c78b10c/r | 2026-11-16 11:58:18 UTC | Page 200; run `pipeline RIV-HO-03` loads without login, verdict confirmed, matches the Confirmed badge: yes |
| RIV-HO-04 trace | https://smith.langchain.com/public/1f529274-fb29-4120-bf9c-d4c7b435c618/r | 2026-11-16 11:58:20 UTC | Page 200; run `pipeline RIV-HO-04` loads without login, verdict rejected, matches the Rejected badge: yes |
| RIV-HO-05 trace | https://smith.langchain.com/public/86981086-1128-4527-b31e-c3323573c5cd/r | 2026-11-16 11:58:23 UTC | Page 200; run `pipeline RIV-HO-05` loads without login, verdict rejected, matches the Rejected badge: yes |
