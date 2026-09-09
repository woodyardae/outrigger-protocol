# Authorization Gate

## Objective

Confirm that required credentials are available before beginning a task.

## Inputs

- Required credential names: `<credential names>`
- Authorized operation: `<operation>`
- Allowed destination: `<destination>`

## Procedure

1. Check whether each required credential is present.
2. Record only `PRESENT` or `MISSING` for each credential name.
3. Continue only when every required credential is `PRESENT` and the operation is authorized.
4. Return `BLOCKED` when a credential is missing or authority is insufficient.

## Safety Rules

- Verify presence only.
- Never print, log, serialize, echo, compare, transform, or disclose credential values.
- Never include credential values in commands, reports, commits, screenshots, or error messages.
- Do not broaden the authorized operation or destination.

## Evidence

- Gate result: `<PASS | BLOCKED>`
- Presence checks: `<credential name: PRESENT | MISSING>`
- Notes: `<non-sensitive observations>`
