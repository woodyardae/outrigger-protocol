# Outrigger Protocol (OPS-1) Threat Model

## 1. System Scope and Security Posture

Outrigger Protocol `v0.2.0` is a zero-dependency Python 3.12 standard-library CLI and composite GitHub Action (`outrigger check`, `outrigger verify`, 40/40 core tests passing). It enforces fail-closed Git diff scope checks, OPS-1 manifest validation, secret-presence checks, and credential-leak scanning in local hooks and CI pipelines.

Outrigger operates strictly as an application-level policy boundary. It never acts as an operating-system sandbox, container runtime, or kernel isolation layer.

Live line-delimited JSON-RPC 2.0 `stdio` path-containment interception (`ensure_within_scope`, rejecting path traversal with error `-32602`) currently runs in the Harbormaster MCP control plane (`mcp_server.py`, 719 tests passing). That runtime control plane is scheduled for standalone extraction and release in Outrigger Protocol `v0.3.0`. An initial standalone proxy module (`src/outrigger_protocol/proxy.py`) and 7 proxy unit tests are staged on `main` ahead of the `v0.3.0` release cut.

---

## 2. Shipped vs. Planned Boundary

| Component / Milestone | Status | Enforcement Point | Scope and Failure Behavior |
| :--- | :--- | :--- | :--- |
| **Outrigger Protocol `v0.2.0`** | Shipped (`v0.2.0` tag, 40/40 tests passing) | Pre-commit / CI post-execution gate (`cli/outrigger.py`, `action.yml`) | Zero-dependency Python 3.12 stdlib CLI (`outrigger check`, `outrigger verify`, `outrigger auth-gate`, `outrigger ledger`) and composite GitHub Action. Compares `git diff --name-only` paths against OPS-1 `writable_scope` / `writable_paths` and `forbidden_patterns`. Scans reports and manifests for token signatures. Exits `2` (`BLOCKED`) on out-of-scope edits or missing required secrets, and exits `1` (`FAIL`) on unsafe `..` paths, credential leaks, or manifest-report mismatches. |
| **Harbormaster MCP Control Plane** | Live Reference Runtime (`mcp_server.py`, 719 tests passing) | Pre-dispatch JSON-RPC 2.0 `stdio` gate (`ensure_within_scope`) | Evaluates path parameters on mutating `tools/call` frames over line-delimited JSON-RPC 2.0 `stdio` before adapter execution. Rejects empty inputs, null bytes, `..` traversal segments, and canonical paths resolving outside `allowed_roots` with JSON-RPC error `-32602` (`Invalid params`). Rejected frames are never forwarded to downstream tools. |
| **Outrigger Protocol `v0.3.0`** | Scheduled Extraction (staged on `main` in `src/outrigger_protocol/proxy.py`) | Standalone MCP `stdio` wrapper (`outrigger proxy`) | Extracts Harbormaster's in-flight `stdio` path-containment and payload secret inspection gate into a standalone zero-dependency CLI wrapper for arbitrary MCP servers. |

---

## 3. OWASP Top 10 for LLM Applications Mapping

Outrigger `v0.2.0` and the Harbormaster `ensure_within_scope` reference gate address three categories in the OWASP Top 10 for LLM Applications (2025 taxonomy):

### LLM06: Excessive Agency
* **Attack Vector:** An autonomous coding agent with workspace write permissions modifies `.github/workflows/`, build scripts, environment files, or sibling directories outside its assigned task boundary.
* **Outrigger `v0.2.0` Control:** `check_git_diff_scope()` runs `git diff --name-only <base>` and passes every modified file through `collect_scope_violations()`. Any file outside `writable_scope` / `writable_paths` or matching `forbidden_patterns` (such as `**/*.pem` or `.env*`) halts CI with status `BLOCKED` and exit code `2`.
* **Harbormaster Live `stdio` Control:** `_enforce_outrigger_scope()` inspects path arguments (`path`, `target_path`, `output_dir`, `vault_path`) on mutating MCP `tools/call` requests via `ensure_within_scope()` prior to router dispatch. Out-of-bounds targets fail immediately with JSON-RPC error `-32602`.

### LLM02: Sensitive Information Disclosure
* **Attack Vector:** An agent reads host files outside the repository via relative path traversal (`../../etc/passwd`), prints CI secret values into logs while checking environment state, or writes live API keys into handoff artifacts.
* **Outrigger `v0.2.0` Control:** `find_leaks()` scans OPS-1 Hub Reports and manifests for GitHub tokens (`ghp_`, `github_pat_`), Slack tokens (`xox*`), and PEM private key headers (`-----BEGIN ... PRIVATE KEY-----`), returning status `FAIL` (exit code `1`) on any match. `command_auth_gate()` queries `gh secret list --json name` to confirm secret presence (`PRESENT` / `ABSENT`) without reading or exposing secret values.
* **Harbormaster Live `stdio` Control:** `ensure_within_scope()` rejects `..` segments, null bytes, and canonicalized paths escaping `allowed_roots` with `-32602` before any file read or write adapter executes. Staged `v0.3.0` proxy code extends leak scanning to in-flight `content`, `diff`, `patch`, `text`, and `body` fields.

### LLM05: Improper Output Handling (Tool and Pipeline Arguments)
* **Attack Vector:** Unvalidated model-generated paths, URL-encoded traversal sequences (`%2e%2e%2f`, `%252e%252e%252f`), null-byte injections (`\x00`, `%00`), or mismatched task reports flow directly into downstream automation or multi-agent handoff consumers.
* **Outrigger `v0.2.0` Control:** `_normal_path()` rejects absolute paths and `..` segments in manifest scopes with `OutriggerError` (exit code `1`). `command_verify()` validates strict 15-heading OPS-1 report structure, cross-checks `task_id` and `branch` binding between manifest and report, and confirms `HEAD_SHA` resolves to an existing Git commit via `git cat-file -e`.
* **Harbormaster Live `stdio` Control:** Incoming NDJSON frames undergo parameter validation and canonical path checking via `Path.resolve(strict=False)` and `is_relative_to()` before dispatch, returning structured JSON-RPC `-32602` errors instead of executing malformed tool inputs.

---

## 4. NIST AI Risk Management Framework (AI RMF 1.0) Alignment

| NIST AI RMF Function | Subcategory Focus | Implementation in Outrigger OPS-1 and Harbormaster |
| :--- | :--- | :--- |
| **GOVERN** | `GV 1.2`, `GV 2.1`: Technical policies and explicit authority | Task permissions are declared before execution in version-controlled JSON manifests (`writable_scope`, `forbidden_actions`, `validation_commands`, `acceptance_criteria`). Agents do not self-authorize scope changes. |
| **MAP** | `MP 1.1`, `MP 3.4`: Intended context and blast-radius definition | Each work unit maps its allowed directory prefixes, target Git branch, and base commit SHA upfront, bounding the operational surface of every delegated task. |
| **MEASURE** | `MS 2.5`, `MS 2.6`: Reproducible safety and integrity verification | `outrigger check --json`, `outrigger verify --json`, and `outrigger ledger --json` emit deterministic status payloads (`PASS`, `FAIL`, `BLOCKED`) backed by automated stdlib test suites (40/40 tests in Outrigger `v0.2.0`; 719 tests in Harbormaster). |
| **MANAGE** | `MG 2.2`, `MG 3.1`: Automated containment and fail-closed response | Out-of-scope diffs fail CI pull requests with non-zero exit codes (`1` or `2`). Out-of-scope MCP `stdio` tool calls are dropped pre-execution with JSON-RPC `-32602`. |

---

## 5. Explicit Non-Goals and Known Limits

1. **Application-Level Boundary Only:** Outrigger enforces policy over Git diffs, OPS-1 manifests, and JSON-RPC `stdio` tool arguments in user space. It does not replace OS user accounts, Linux namespaces, containers, microVMs, `seccomp-bpf` filters, AppArmor/SELinux profiles, or Windows Job Objects.
2. **Unproxied Host Execution:** In `v0.2.0`, `outrigger check` and `outrigger verify` evaluate repository state after commands run. If an agent executes direct shell commands or native binaries outside an MCP `stdio` proxy, Outrigger blocks the resulting out-of-scope Git changes from merging in CI, but it cannot block arbitrary host reads or network calls during execution.
3. **OS-Level Symlink TOCTOU Races:** `ensure_within_scope()` resolves paths in user space with `Path.resolve(strict=False)` before a tool runs. Without kernel-enforced directory descriptor flags such as Linux `openat2` (`RESOLVE_BENEATH` and `RESOLVE_NO_SYMLINKS`), a concurrent local process with write access inside an allowed directory could swap a symlink between user-space validation and the downstream `open()` syscall. Multi-tenant or untrusted code execution requires kernel or VM sandboxing underneath Outrigger.
4. **Regex Secret-Scanning Scope:** Built-in leak detection targets known token formats (`ghp_`, `github_pat_`, `xox*`, `sk_live_`, `rk_live_`, `sk-ant-`, PEM private keys). It does not detect arbitrary custom secrets, encrypted payloads, or side-channel exfiltration.
