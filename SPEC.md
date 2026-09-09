# Outrigger Protocol Specification

## OPS-1: Task Execution and Handoff

**Status:** Initial
**Version:** 1.0
**Normative terms:** MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as requirements at their customary levels.

### 1. Purpose

OPS-1 defines a small, auditable protocol for delegating a bounded software task, executing it in isolation, and returning evidence to a coordinating hub.

### 2. Principles

OPS-1 is governed by five named principles:

1. **Explicit Authority** — An executor MUST act only within the permissions, writable scope, and external-action policy stated in the Task Manifest. Secret checks establish presence only; secret values MUST NOT be disclosed.
2. **Scope Isolation** — Each task MUST use its assigned branch and workspace. An executor MUST NOT modify paths outside `writable_scope` or rely on unlisted side effects.
3. **Atomic Delivery** — Changes MUST be logically grouped, reviewable, and committed as an atomic task outcome. Partial delivery MUST be identified explicitly.
4. **Evidence Before Verdict** — Every verdict MUST be supported by reproducible local commands, exit codes, and concise evidence. A claim without evidence MUST NOT be reported as verified.
5. **Transparent Handoff** — The Hub Report MUST state outcomes, risks, blockers, attempts, commits, and caveats factually so the hub can make an independent decision.

### 3. Task Manifest

A Task Manifest is the authoritative task input. It MUST contain exactly these fields:

- `protocol`: string; MUST be `OPS-1`.
- `task_id`: string; stable identifier unique within the coordinating batch.
- `objective`: string; the requested outcome.
- `writable_scope`: array of repository-relative paths or path prefixes; the complete set of allowed project-file writes.
- `branch`: string; the required Git branch.
- `acceptance_criteria`: array of strings; observable completion conditions.
- `validation_commands`: array of strings; local commands expected to produce verification evidence.
- `forbidden_actions`: array of strings; actions that MUST NOT be performed.
- `handoff_path`: string; repository-relative destination for the Hub Report.

Unknown fields MUST be rejected. Missing fields MUST produce a `BLOCKED` verdict unless the omission can be resolved without expanding authority.

### 4. Execution Requirements

1. Inspect repository and branch state before writing.
2. Create or select the manifest branch.
3. Limit writes to `writable_scope`.
4. Perform no forbidden action.
5. Run applicable `validation_commands` and record each command and exit code.
6. Commit implementation changes before generating a report that references the implementation commit.
7. Write the Hub Report to `handoff_path`.
8. Commit the Hub Report separately when its `HEAD_SHA` identifies the implementation commit.
9. Finish with a clean worktree.

### 5. Hub Report

A Hub Report is the authoritative task output. It MUST contain exactly these fields, represented as Markdown section headings in this order:

- `protocol`: the protocol identifier; MUST be `OPS-1`.
- `task_id`: the Task Manifest identifier.
- `verdict`: one value from the verdict enum.
- `summary`: concise factual outcome.
- `branch`: branch used for execution.
- `HEAD_SHA`: full Git SHA of the implementation commit being reported.
- `commits`: ordered list of task commit SHAs and subjects known when the report is written.
- `files_changed`: repository-relative paths with a brief purpose.
- `commands`: exact commands run with integer exit codes.
- `validation`: each acceptance or validation check and its result.
- `evidence`: concrete observations supporting the verdict.
- `risks`: known residual risks, or `None`.
- `blockers`: unresolved blockers, or `None`.
- `attempt`: positive integer identifying the execution attempt.
- `caveats`: qualifications needed to interpret the report, or `None`.

The report MUST NOT include secret values, proprietary identifiers, or machine-specific internal paths. Because a commit cannot contain its own SHA, `HEAD_SHA` MUST identify the implementation commit, not the later report commit.

### 6. Verdict Enum

The only valid verdict values are:

- `PASS` — all acceptance criteria were met and required validation succeeded.
- `FAIL` — execution completed, but one or more acceptance criteria or required validations failed.
- `BLOCKED` — completion could not proceed without missing authority, information, access, or an explicitly prohibited action.

No other verdict value is valid.

### 7. Security and Privacy

Authentication gates MUST verify only whether each required secret is present. Executors MUST NOT print, serialize, compare, transform, or otherwise disclose secret values. Reports and templates MUST use generic identifiers and repository-relative paths.
