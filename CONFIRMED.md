# What "confirmed" means

The fact checker decides whether a candidate from `data/aws_reinvent_candidate_items.csv` is CONFIRMED by answering three YES/NO questions. The rule below is the exact text to give the fact checker; copy it word for word.

## The rule

```text
RULE: WHAT "CONFIRMED" MEANS

A candidate is CONFIRMED only if all three questions below are answered YES.
If any question is answered NO, the candidate is REJECTED, with a one-line reason.
REJECTED means no AWS page confirms the claim. It does not mean the claim is false.

How to answer
- Check each question on its own, using only the evidence for that question.
- Answer all three questions, even after a NO.
- Every answer is YES or NO. If you are unsure, the answer is NO.
- Every YES needs a quote copied word for word from an aws.amazon.com page, with its URL.
  The quote must be findable on the live page with find-in-page.
  A paraphrase or summary is a NO.
- Every fact in the claim needs its own quote.
- Use only what the page says. Your own knowledge is not evidence.

Q1. Official source: Is the evidence on an aws.amazon.com page that loads?
    YES only if the URL is on aws.amazon.com and the page loads on the day of the check.
    A third-party page (Hacker News, Reddit, a newsletter) is a NO, even if it links to AWS.
    Copy: the URL and the page title, word for word.

Q2. Every fact stated: Does an aws.amazon.com page state every fact in the claim?
    YES only if there is a word-for-word quote for each fact:
    the service, what happened, and where (if the claim names a Region).
    A page that only gives background, or covers a related service, is a NO.
    Copy: one quote per fact.

Q3. Status and date: Does an aws.amazon.com page say the claim has happened, as claimed, with a date?
    YES only if a quote shows the same status as the claim
    (for example "generally available", not "preview"; launched, not planned)
    and the page shows a date on or before the day of the check.
    Copy: the status quote and the date, word for word.

RECORD (fill in every line)
Candidate: <candidate_id>
Claim: <claim_text from data/aws_reinvent_candidate_items.csv, word for word>
Checked on: <YYYY-MM-DD>
Q1 Official source: YES / NO
   URL: <url>
   Title: "<page title, word for word>"
Q2 Every fact stated: YES / NO
   Service: "<quote>"
   What happened: "<quote>"
   Where: "<quote>" or n/a if the claim names no Region
Q3 Status and date: YES / NO
   Status: "<quote>"
   Date: "<quote>"
Verdict: CONFIRMED / REJECTED
Reason: <one line, only if REJECTED>
```

## Who does what

| Role | What it does | What it never does | Hands over |
|---|---|---|---|
| Lead agent | Reads the candidate row from `data/aws_reinvent_candidate_items.csv` by `candidate_id`, gives the claim text word for word to the researcher, passes the researcher's evidence to the fact checker, and records the fact checker's verdict. | Searches for sources or answers any of the three questions. | The CSV row to the researcher; the evidence to the fact checker; the final record to the repo. |
| Researcher | Finds aws.amazon.com pages about the claim and returns, for each page, the URL, the page title, and word-for-word quotes for each fact, the status and the date. Reports "none found" when there is nothing. | Answers YES or NO, paraphrases a quote, or offers its own knowledge as evidence. | URLs and quotes to the lead agent. |
| Fact checker | Opens each URL, confirms every quote appears on the page word for word, answers Q1, Q2 and Q3 separately as YES or NO, and gives the verdict with a one-line reason if REJECTED. | Searches for new sources, fixes or rewords a quote, or uses its own knowledge. | The filled-in record to the lead agent. |

## Example: C-02 with the evidence from the first run

The only evidence from the C-02 run in the README is the page the model named, https://aws.amazon.com/braket/.

```text
Candidate: C-02
Claim: AWS will launch a managed quantum computing Region in us-east-1 at re:Invent 2025.
Checked on: 2026-10-30
Q1 Official source: YES
   URL: https://aws.amazon.com/braket/
   Title: "Quantum Cloud Computing Service - Amazon Braket - AWS"
Q2 Every fact stated: NO
   Service: none, the page covers Amazon Braket, not a quantum computing Region
   What happened: none
   Where: none
Q3 Status and date: NO
   Status: none
   Date: none
Verdict: REJECTED
Reason: No aws.amazon.com page found states that AWS launched a managed quantum computing Region in us-east-1.
```
