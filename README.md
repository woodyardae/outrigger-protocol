# Outrigger Protocol

[![Namespace](https://img.shields.io/badge/namespace-woodyardae-1B4F72)](https://alanwoodyard.com)
[![Stack](https://img.shields.io/badge/stack-Python_stdlib_OPS--1-1A5276)](https://alanwoodyard.com)
[![IP](https://img.shields.io/badge/IP-permissive__open_%7C_MIT-196F3D)](https://alanwoodyard.com)

[Alan Woodyard](https://alanwoodyard.com)

## System Role

Outrigger is the sovereign containment harness and execution sandbox for autonomous coding agents. It implements the OPS-1 specification: a unit of work does not run until a manifest is verified, an auth gate passes, and the handoff ledger records the result.

Registered tagline: zero-dependency POSIX agent-containment harness and OPS-1 gate. Package version 0.2.0. Console script: `outrigger` → `cli.outrigger:main`. Harvest maturity: working core (836 implementation LOC, 693 test LOC). Specification text: `SPEC.md`.

## Audited Architecture & Runtime

Pure Python standard library. Hatchling build. No third-party imports were harvested.

| Path | Role |
| --- | --- |
| `cli/outrigger.py` | CLI and gate implementation |
| `SPEC.md` | OPS-1 specification |
| `templates/` | Unit templates for `outrigger new` |
| `examples/` | Example manifests |
| `tests/` | Gate and ledger tests |
| `integrations/hf-space/app.py` | Optional demo front end, not the gate |
| `install.ps1` | Local install helper |
| `docs/SHOW_HN_OUTRIGGER.md` | Public explanation |

STAX Streamer emits task manifests toward this harness (`emits_task_manifests`). Outrigger is the authority that accepts or refuses them. The catalog names `outrigger-gate.py` as the historical gate file. The packaged entry today is `cli/outrigger.py`.

## CLI / API Surface

```text
outrigger init [--json]
outrigger new <unit_name> [--template <name>] [--json]
outrigger auth-gate --secret <secret>... [--repo <path>] [--json]
outrigger verify <report> [--manifest <path>] [--no-git] [--json]
outrigger check --manifest <path> [--base <rev>] [--json]
outrigger ledger [--dir .outrigger/handoffs] [--json]
```

`init` lays down the local harness. `new` creates a contained work unit from a template. `auth-gate` requires one or more `--secret` values and refuses to proceed without them. `verify` checks a report against a manifest and can skip git inspection with `--no-git`. `check` evaluates a manifest against an optional git base. `ledger` reads `.outrigger/handoffs` by default. `--json` on each command emits a machine-readable result.

There is no HTTP API on the gate. `integrations/hf-space/app.py` is a separate demo process.

## Operational Boundaries

Permissive open source, MIT, public. The containment boundary is POSIX and local: manifests, secrets passed on the command line, and the handoff directory live in the repository the operator pointed at.

`auth-gate` does not store a secret catalog in this repository. Callers pass secrets at invocation time. A manifest that fails `verify` or `check` is not an execution permit. Streamer, and any other emitter, stops at the manifest. The agent runs only after this CLI says the gate passed.

Local-first rule: `--no-git` weakens verification on purpose and must be an explicit flag. The default path inspects git.
