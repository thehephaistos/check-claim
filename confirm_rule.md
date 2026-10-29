# Rule card: AWS launch claim check

Our agents check launch claims such as "Amazon Bedrock AgentCore is now generally available". Before a claim is reported as confirmed, the fact-checker compares it with the official AWS pages in `data/aws_official_source_snapshot.json` (captured 3 November 2025). The claims come from `data/aws_reinvent_candidate_items.csv`.

## The rule: a claim is confirmed only if every answer is yes

1. Source: Is the source an aws.amazon.com page?
2. Quote: Is every quoted sentence copied word for word from that page?
3. Facts: Is every fact in the claim backed by a quoted sentence?

Each check is answered on its own, as yes or no. If any answer is no, the claim is rejected, with one line saying which check failed and why. If the fact-checker is unsure, the answer is no.

## Who does what

| Agent | Job | Gets | Gives back |
|---|---|---|---|
| Lead agent | Hands out claims | A candidate row from `data/aws_reinvent_candidate_items.csv` | The claim text, word for word, to the researcher |
| Researcher | Finds a page | The claim text | The aws.amazon.com page URL with its sentences copied word for word, or "no page found" |
| Fact-checker | Answers the checks | The claim, the page URL and the quoted sentences | Confirmed or rejected, with a one-line reason |

## Worked example: C-01

Claim: "Amazon Bedrock AgentCore is now generally available for building and running AI agents at scale."

Page the researcher found: https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-agentcore-available/ (snapshot page AWS-SRC-019, published 2025-10-13)

> Amazon Bedrock AgentCore is now generally available.
>
> AgentCore is an agentic platform to build, deploy and operate AI agents securely at scale, using any framework and any foundation model.

| Check | Answer |
|---|---|
| 1. Source | Yes. The page is on aws.amazon.com. |
| 2. Quote | Yes. Both sentences are copied word for word from the page. |
| 3. Facts | Yes. "Now generally available" is backed by the first sentence; "building and running AI agents at scale" is backed by "build, deploy and operate AI agents securely at scale". |

Verdict: confirmed. Reason: "An aws.amazon.com What's New page states word for word that Amazon Bedrock AgentCore is generally available for building and operating AI agents at scale."

## Worked example: C-05

Claim: "Amazon S3 Vectors is now GA and lets you store and query vector embeddings natively in S3 at massive scale."

Pages the researcher found:

https://aws.amazon.com/about-aws/whats-new/2025/07/amazon-s3-vectors-preview-native-support-storing-querying-vectors/ (snapshot page AWS-SRC-014, published 2025-07-15)

> Amazon S3 Vectors is now available in preview.
>
> S3 Vectors is the first cloud object store with native support to store and query vectors, and can reduce the cost of uploading, storing and querying vectors by up to 90%.

https://aws.amazon.com/s3/features/vectors/ (snapshot page AWS-SRC-015, published 2025-07-15)

> Amazon S3 Vectors is in preview and is available in five AWS Regions.

| Check | Answer |
|---|---|
| 1. Source | Yes. Both pages are on aws.amazon.com. |
| 2. Quote | Yes. All three sentences are copied word for word from their pages. |
| 3. Facts | No. The claim says "now GA", but both pages say S3 Vectors is in preview, and a preview does not back up generally available. |

Verdict: rejected. Reason: "Check 3 failed: the AWS pages say S3 Vectors is in preview, which does not back up the claim that it is generally available."
