# Outrigger Protocol (OPS-1)

Deterministic process containment, secret gating, and agent boundary verification for autonomous coding workflows.

## Shipped vs. Planned Architecture Boundary

| Component / Milestone | Status | Scope & Capability |
| :--- | :--- | :--- |
| **`v0.2.0`** | Shipped | Zero-dependency Python 3.10+ stdlib CLI (`outrigger check` / `outrigger verify`) and composite GitHub Action enforcing fail-closed Git diff and OPS-1 manifest scope gates. Application-level policy boundary (not an OS/kernel sandbox). |
| **`Harbormaster`** | Live Reference Runtime | Houses the active JSON-RPC 2.0 `stdio` (NDJSON) path-containment interceptor (`ensure_within_scope`, error `-32602`). |
| **`v0.3.0`** | Planned Extraction | Standalone MCP `stdio` security proxy extraction from Harbormaster. |

## Installation

pip install git+https://github.com/woodyardae/outrigger-protocol.git

## Usage

git diff HEAD~1 | outrigger verify - --fail-closed
