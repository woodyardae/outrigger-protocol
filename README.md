# Outrigger Protocol

Outrigger is a small protocol and standard-library CLI for bounded software work. It makes authority, writable scope, validation, and handoff evidence explicit so a coordinating hub can review an executor's result independently.

## Why this exists

Repositories capsize when delegated work has no stable boundary. Common failure modes are:

- an executor edits unrelated paths or works on the wrong branch;
- credentials are exposed while checking whether they exist;
- a partial implementation is presented as complete;
- a verdict has no reproducible command or exit-code evidence;
- the implementation commit and its handoff report cannot be distinguished;
- concurrent units return inconsistent reports that a hub cannot compare.

The name carries two engineering metaphors. A canoe outrigger places a float away from the hull to resist capsize. A crane outrigger widens the machine's support footprint before load is applied. OPS-1 applies both ideas to repositories: isolated task units provide lateral stability, and explicit authority and evidence widen the support base for a delivery decision.

## Architecture

Outrigger has four components:

1. **OPS-1 specification** — [`SPEC.md`](SPEC.md) defines authority, isolation, atomic delivery, evidence, report fields, and verdicts.
2. **Task inputs** — a strict JSON Task Manifest and the files in `templates/` describe a bounded unit's objective, branch, writable scope, validation, prohibited actions, and handoff destination.
3. **Execution tools** — `cli/outrigger.py` implements the dependency-free local commands; `action.yml` exposes report verification as a composite GitHub Action.
4. **Hub outputs** — OPS-1 Hub Reports in `.outrigger/handoffs/` record commits, commands, exit codes, evidence, risks, blockers, and caveats; the ledger command summarizes them in batch order.

## Quickstart without installation

Python 3.10 or later is required. The CLI itself uses only the Python standard library.

```sh
python3 cli/outrigger.py --help
python3 cli/outrigger.py verify .outrigger/handoffs/batch-2-hub-report.md --no-git
python3 cli/outrigger.py ledger
```

Install an editable development command with pip:

```sh
python -m pip install -e .
outrigger --help
```

Install an isolated command with uv:

```sh
uv tool install .
outrigger --help
```

## CLI

### `init`

```sh
outrigger init
```

Creates `.outrigger/handoffs/` and copies the bundled Markdown templates into `.outrigger/templates/`. Existing templates are not overwritten, so the command is safe to repeat.

### `new`

```sh
outrigger new UNIT_NAME
outrigger new UNIT_NAME --template manifest.json
```

Prints an OPS-1 JSON Task Manifest to standard output. The generated manifest uses the current Git branch and commit, and names `.outrigger/handoffs/<unit-slug>-hub-report.md`. `--template` must point to a JSON object containing exactly the OPS-1 manifest fields; its task ID, branch, base-diff validation command, and handoff path are refreshed for the new unit.

### `auth-gate`

```sh
outrigger auth-gate --secret SECRET_NAME
outrigger auth-gate --secret SECRET_NAME --repo OWNER/REPOSITORY
```

Uses the GitHub CLI to list secret names, never secret values. It prints `PRESENT` and exits `0` when the name exists. Missing credentials, GitHub CLI errors, invalid responses, and an unavailable `gh` executable produce `ABSENT` and exit `2`. This command is the only CLI operation that calls an external executable.

### `verify`

```sh
outrigger verify REPORT
outrigger verify REPORT --manifest MANIFEST
outrigger verify REPORT --manifest MANIFEST --no-git
```

Checks exact OPS-1 report heading order, protocol, verdict, and recognizable secret material. With `--manifest`, it also validates the manifest and, unless `--no-git` is present, checks the manifest's Git diff endpoints against its writable scope. It prints `PASS` and exits `0` on success; otherwise it prints one or more `FAIL:` lines and exits `1`.

### `ledger`

```sh
outrigger ledger
outrigger ledger --dir PATH
```

Reads Markdown reports from `.outrigger/handoffs/` by default, prints a batch-ordered summary table, and reports the next expected batch number. Unreadable report files are skipped.

## GitHub Action

The composite action requires `report-path`; `manifest-path` is optional. It executes the checked-in verifier from the action installation directory, so it does not depend on the caller's checkout containing Outrigger's CLI. The job must provide Python 3.

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: "3.10"
  - uses: woodyardae/outrigger-protocol@v1
    with:
      report-path: .outrigger/handoffs/release-hub-report.md
      manifest-path: .outrigger/release-manifest.json
```

If the verifier fails, its nonzero exit status fails the action step.

## Protocol and license

The normative protocol is [`SPEC.md`](SPEC.md). Outrigger Protocol is available under the [`MIT License`](LICENSE).
