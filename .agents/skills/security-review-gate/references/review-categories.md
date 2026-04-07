# Review Categories

## Vulnerability Classes
- injection risks
- cross-site scripting and output encoding failures
- SSRF and unsafe outbound requests
- broken authorization
- insecure crypto and token handling
- secret leakage
- insecure file and path handling
- unsafe deserialization or dynamic execution

## Reporting Rubric
- `evidence`: what was seen in code or configuration
- `risk`: why it matters
- `failure_or_exploit_scenario`: how the issue can fail in practice
- `recommendation`: the smallest useful fix
- `verification`: how to prove the fix works

## Review Guidance
- Prioritize exploitable or high-impact findings first.
- Separate confirmed issues from lower-confidence concerns.
- If code context is incomplete, say what was not reviewed.
