# Atomic Feature Batch

## Task

- Task ID: `<identifier>`
- Objective: `<bounded outcome>`
- Branch: `<task branch>`
- Writable scope: `<repository-relative paths>`
- Acceptance criteria: `<observable criteria>`
- Forbidden actions: `<explicit prohibitions>`
- Handoff path: `<repository-relative path>`

## Delivery Plan

1. Inspect repository and branch state.
2. Implement only the bounded feature.
3. Run the relevant local validations.
4. Review the diff for scope and sensitive data.
5. Commit the implementation as one logical change.
6. Produce the evidence-based handoff.

## Atomicity Rules

- Do not mix unrelated cleanup or refactoring into the batch.
- Do not modify files outside the writable scope.
- Do not report partial work as complete.
- If safe atomic delivery is impossible, stop and report `BLOCKED`.

## Validation Record

- Command: `<exact command>`
- Exit code: `<integer>`
- Result: `<PASS | FAIL>`
- Evidence: `<concise observation>`

## Delivery Record

- Verdict: `<PASS | FAIL | BLOCKED>`
- Implementation commit: `<full Git SHA>`
- Files changed: `<repository-relative paths and purposes>`
- Risks: `<none or factual list>`
- Blockers: `<none or factual list>`
- Caveats: `<none or factual list>`
