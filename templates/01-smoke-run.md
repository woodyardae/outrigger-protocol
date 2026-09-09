# Isolated Smoke Run

## Objective

Verify the smallest representative workflow without affecting shared or production state.

## Isolation Boundary

- Workspace or branch: `<isolated location>`
- Writable scope: `<repository-relative paths>`
- External actions allowed: `<none or explicit list>`
- Cleanup requirement: `<required cleanup>`

## Preconditions

- Authorization gate: `<PASS>`
- Inputs: `<non-sensitive inputs>`
- Expected behavior: `<observable outcome>`

## Procedure

1. Confirm the isolation boundary.
2. Capture the initial repository state.
3. Run the smallest applicable smoke command.
4. Record the exact command, exit code, and concise output evidence.
5. Confirm no state changed outside the isolation boundary.

## Result

- Verdict: `<PASS | FAIL | BLOCKED>`
- Command: `<exact command>`
- Exit code: `<integer>`
- Evidence: `<observable result>`
- Side effects: `<none or factual list>`
- Risks or blockers: `<none or factual list>`
