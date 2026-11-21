# Outrigger Protocol (OPS-1)

[![Python 3.12](https://img.shields.io/badge/python-3.12%20stdlib-blue.svg)](https://github.com/woodyardae/outrigger-protocol)
[![Dependencies](https://img.shields.io/badge/dependencies-0%20external-success.svg)](./pyproject.toml)
[![v0.2.0 Tests](https://img.shields.io/badge/v0.2.0%20tests-40%2F40%20passing-brightgreen.svg)](./tests)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](./LICENSE)

Deterministic Git diff scope gates, OPS-1 manifest verification, and credential-leak checks for autonomous coding workflows. See [`THREAT_MODEL.md`](./THREAT_MODEL.md) for OWASP Top 10 for LLMs mappings, NIST AI RMF alignment, and known non-goals.

## Shipped vs. Planned Architecture Boundary

| Component / Milestone | Status | Scope & Capability |
| :--- | :--- | :--- |
| **`v0.2.0`** | Shipped | Zero-dependency Python 3.12 stdlib CLI (`outrigger check`, `outrigger verify`, 40/40 tests passing) and composite GitHub Action enforcing fail-closed Git diff and OPS-1 manifest scope gates. Operates strictly as an application-level policy boundary, never an OS or kernel sandbox. |
| **`Harbormaster`** | Live Reference Runtime | Runs live line-delimited JSON-RPC 2.0 `stdio` path-containment interception (`ensure_within_scope`, rejecting path traversal with `-32602`) in `mcp_server.py` (719 tests passing). |
| **`v0.3.0`** | Planned Extraction | Scheduled standalone extraction of Harbormaster's MCP `stdio` security proxy into Outrigger Protocol (initial module staged on `main` in `src/outrigger_protocol/proxy.py`). |

## 30-Second Reproducible Verification & Containment Trace

### 1. Post-Execution CLI Scope Gate (`outrigger verify`, Shipped `v0.2.0`)

Outrigger `v0.2.0` fails closed whenever a task report, manifest path, or Git diff violates OPS-1 rules. Exit code `0` indicates `PASS`. Exit code `1` (`FAIL`) halts structural, secret-leak, report-binding, or unsafe `..` path errors. Exit code `2` (`BLOCKED`) halts out-of-scope file modifications. Both non-zero codes fail CI builds immediately.

Run this self-contained check with Python 3.12 standard library only:

```bash
# 1. Verify an unsafe parent-traversal scope entry fails closed with exit code 1 (FAIL)
python -c '
import json, pathlib, tempfile
from cli import outrigger

with tempfile.TemporaryDirectory() as tmp:
    p = pathlib.Path(tmp)
    manifest = {
        "protocol": "OPS-1", "task_id": "TASK-001", "objective": "Scope test",
        "writable_scope": ["../etc/passwd"], "branch": "main",
        "acceptance_criteria": [], "validation_commands": ["git diff --name-only HEAD~1 HEAD"],
        "forbidden_actions": [], "handoff_path": ".outrigger/report.md"
    }
    (p / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (p / "report.md").write_text(pathlib.Path(".outrigger/report.md").read_text(encoding="utf-8"), encoding="utf-8")
    code = outrigger.main(["verify", str(p / "report.md"), "--manifest", str(p / "manifest.json"), "--json"])
    raise SystemExit(code)
'
```

Output (`exit_code: 1`):

```json
{
  "status": "FAIL",
  "violations": [
    "unsafe repository-relative path: ../etc/passwd"
  ],
  "exit_code": 1
}
```

When a valid manifest restricts `writable_scope` to `["src/"]` and `git diff --name-only BASE HEAD` includes an out-of-scope edit such as `SPEC.md`, `outrigger verify report.md --manifest manifest.json --json` (and `outrigger check --manifest manifest.json --json`) rejects the diff with non-zero exit code `2`:

```json
{
  "status": "BLOCKED",
  "violations": [
    "outside writable scope: SPEC.md"
  ],
  "exit_code": 2
}
```

### 2. Illustrative JSON-RPC 2.0 `stdio` Containment Trace (Harbormaster `ensure_within_scope` Control Plane)

The trace below illustrates the live line-delimited JSON-RPC 2.0 `stdio` control plane currently running in Harbormaster (`mcp_server.py`, `ensure_within_scope`, 719 tests passing) and scheduled for standalone extraction in Outrigger Protocol `v0.3.0`:

```json
// Inbound MCP stdio frame (agent requests out-of-scope path traversal)
{"jsonrpc":"2.0","id":42,"method":"tools/call","params":{"name":"read_file","arguments":{"path":"../../etc/passwd"}}}

// Outbound stdio rejection from ensure_within_scope (downstream tool is never invoked)
{"jsonrpc":"2.0","id":42,"error":{"code":-32602,"message":"Outrigger boundary violation: path escapes configured workspace roots: ../../etc/passwd"}}
```

## Installation

```bash
pip install git+https://github.com/woodyardae/outrigger-protocol.git@v0.2.0
```

## CLI & GitHub Action Usage

```bash
# Scaffold .outrigger/ templates and generate an OPS-1 task manifest
outrigger init
outrigger new task-001 > .outrigger/manifest.json

# Check Git diff paths against the manifest writable_scope / forbidden_patterns
outrigger check --manifest .outrigger/manifest.json --base HEAD~1 --json

# Verify an OPS-1 Hub Report, secret-leak rules, and Git diff scope binding
outrigger verify .outrigger/report.md --manifest .outrigger/manifest.json --json

# Verify secret presence in GitHub Actions without reading secret values
outrigger auth-gate --secret DEPLOY_TOKEN --json

# Render chronological batch handoff status
outrigger ledger --dir .outrigger/handoffs
```

Composite GitHub Action (`action.yml`, Python 3.12 default):

```yaml
- uses: woodyardae/outrigger-protocol@v0.2.0
  with:
    manifest: '.outrigger/manifest.json'
    python-version: '3.12'
```

## Local Test Verification

```bash
# Run the v0.2.0 stdlib test suite (40 tests)
python -m unittest tests/test_outrigger.py tests/test_containment_scope.py tests/test_secret_gate.py -v

# Run full repository discovery (includes staged v0.3.0 stdio proxy tests)
python -m unittest discover -s tests -v
```

## Security Documentation

Read [`THREAT_MODEL.md`](./THREAT_MODEL.md) and [`SPEC.md`](./SPEC.md) for protocol invariants, threat mappings, and application-boundary limits.
