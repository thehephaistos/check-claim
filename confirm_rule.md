# Confirm rule

A candidate claim from `data/aws_reinvent_candidate_items.csv` is CONFIRMED only when the fact-checker answers YES to all three checks below. Each check is answered on its own, as YES or NO. The sources are the official AWS pages in `data/aws_official_source_snapshot.json` (captured 3 November 2025).

## The three checks

```text
Check 1. Source: Is the source an aws.amazon.com page?
Check 2. Quote: Is every quoted sentence copied word for word from that page?
Check 3. Facts: Is every fact in the claim backed by a quoted sentence?
```

Any NO means the claim is REJECTED, with a one-line reason why.

## Who does what

| Role | Job |
|---|---|
| Lead agent | Hands out claims: reads each candidate row from `data/aws_reinvent_candidate_items.csv` and gives its claim text, word for word, to the researcher. |
| Researcher | Finds a page: searches the snapshot for the claim's service and returns the aws.amazon.com page URL with its sentences copied word for word. |
| Fact-checker | Answers the checks: answers checks 1, 2 and 3 as YES or NO, using only the researcher's page and quotes, and gives the verdict, with a one-line reason if REJECTED. |

## Example: C-01

**Claim:** Amazon Bedrock AgentCore is now generally available for building and running AI agents at scale.

https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-agentcore-available/ (snapshot page AWS-SRC-019, published 2025-10-13)

> Amazon Bedrock AgentCore is now generally available.
>
> AgentCore is an agentic platform to build, deploy and operate AI agents securely at scale, using any framework and any foundation model.

- Check 1, source: YES. The page is on aws.amazon.com.
- Check 2, quote: YES. Both sentences are copied word for word from the page.
- Check 3, facts: YES. "Generally available" is backed by the first sentence; "building and running AI agents at scale" is backed by "build, deploy and operate AI agents securely at scale".

**Verdict: CONFIRMED.** Reason: an aws.amazon.com What's New page states, word for word, that Amazon Bedrock AgentCore is generally available for building and operating AI agents at scale.

## Example: C-05

**Claim:** Amazon S3 Vectors is now GA and lets you store and query vector embeddings natively in S3 at massive scale.

https://aws.amazon.com/about-aws/whats-new/2025/07/amazon-s3-vectors-preview-native-support-storing-querying-vectors/ (snapshot page AWS-SRC-014, published 2025-07-15)

> Amazon S3 Vectors is now available in preview.
>
> S3 Vectors is the first cloud object store with native support to store and query vectors, and can reduce the cost of uploading, storing and querying vectors by up to 90%.

https://aws.amazon.com/s3/features/vectors/ (snapshot page AWS-SRC-015, published 2025-07-15)

> Amazon S3 Vectors is in preview and is available in five AWS Regions.

- Check 1, source: YES. Both pages are on aws.amazon.com.
- Check 2, quote: YES. All three sentences are copied word for word from their pages.
- Check 3, facts: NO. The claim says "now GA", but both pages say S3 Vectors is in preview, and a preview does not back up generally available.

**Verdict: REJECTED.** Reason: check 3 is NO, because the AWS pages say S3 Vectors is in preview, which does not back up the claim that it is generally available.
