# Plan Gap Checklist

## Review Categories
- authentication and authorization requirements
- trust boundaries and external integrations
- input validation and output handling expectations
- sensitive data handling and retention
- secret management and configuration flow
- logging, monitoring, and abuse controls
- dependency and supply-chain assumptions

## Output Template
- Summary
- Gaps
- Risk scenarios
- Recommended plan additions
- Coverage note

## Review Guidance
- Start with the most material missing control, not the largest list.
- Tie every suggestion to a concrete failure mode.
- Cross-check the plan against any loaded stack profile so stack-specific controls are not skipped.
- If the plan is strong, say what is already covered before listing gaps.
