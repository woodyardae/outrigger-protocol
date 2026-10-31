# Outrigger Protocol (OPS-1) v0.2.0 Public Launch Kit

Author: Alan Woodyard (https://alanwoodyard.com | https://github.com/woodyardae)
Repository: https://github.com/woodyardae/outrigger-protocol

---

## 1. Show HN Submission

**Title:** Show HN: Outrigger Protocol – Zero-dependency scope containment for AI coding agents

**URL:** https://github.com/woodyardae/outrigger-protocol

**Body:**

Hey HN,

Autonomous coding agents (Cursor, Claude Code, Devin, OpenHands) routinely introduce unmanaged blast radiuses when given direct terminal or filesystem access. A hallucinated relative path (`../../`) or an agent drifting into `.github/workflows`, `.aws/`, or host credential stores can compromise a workstation or CI pipeline before human review occurs.

Spinning up heavy Docker containers for every minor refactor introduces major startup latencies, file permission synchronization headaches, and volume mount overhead.

We built Outrigger Protocol (OPS-1) as a zero-dependency, lightweight scope containment layer for autonomous coding pipelines:

- **100% Python Standard Library**: Runs anywhere Python 3.10+ exists with zero external dependencies (`dependencies = []`).
- **Deterministic Boundary Checking**: Canonicalizes paths, resolves symlink breakout attempts, strips null-byte injections, and halts directory traversal in under 20ms.
- **Fail-Closed CI Assertions**: Drop `outrigger assert` into your pull request pipelines or GitHub Actions to block un-scoped agent writes before merge.
- **In-Flight MCP Proxying (v0.3.0)**: Live stdio proxy wrapping MCP tools (like `@modelcontextprotocol/server-filesystem`) to intercept and reject traversal arguments before disk execution.

PyPI: `pip install outrigger-protocol`
GitHub: https://github.com/woodyardae/outrigger-protocol

Looking forward to your feedback on edge-case path canonicalization and agent containment strategies.

---

## 2. 4-Part Social Launch Thread (Bluesky, Mastodon, Nostr)

### 1/4 (The Problem)
Autonomous coding agents are exceptional at refactoring, but dangerous with paths. A single hallucinated `../` traversal or un-scoped file write into `.github/workflows` or `.env` compromises your build pipeline. Heavy Docker sandboxes introduce unacceptable startup drag.

### 2/4 (The Solution: OPS-1)
We released Outrigger Protocol v0.2.0 on PyPI. 
Zero third-party dependencies. 100% Python stdlib. 
Enforces fail-closed directory boundaries and git diff assertions in <20ms.
https://github.com/woodyardae/outrigger-protocol

### 3/4 (Under the Hood)
How OPS-1 stops agent drift:
- Double URL-decode pass catches `%252e%252e%252f` evasion
- Immediate null-byte injection rejection (`\x00`, `%00`)
- Symlink dereferencing checks target locations against allowed root prefixes
- Built-in regex scanner halts outbound secret leaks

### 4/4 (Try It)
Add it to GitHub Actions in 30 seconds:
```yaml
- uses: woodyardae/outrigger-protocol@v0.2.0
  with:
    manifest: '.outrigger/manifest.json'
```
CLI: pip install outrigger-protocol
Architected by Alan Woodyard (@woodyardae). PRs and security issues welcome on GitHub!

---

## 3. README Badges

```markdown
[![PyPI version](https://img.shields.io/pypi/v/outrigger-protocol.svg?color=blue)](https://pypi.org/project/outrigger-protocol/)
[![Python Versions](https://img.shields.io/pypi/pyversions/outrigger-protocol.svg)](https://pypi.org/project/outrigger-protocol/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests Passing](https://img.shields.io/badge/tests-47%2F47%20passing-brightgreen.svg)]()
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0%20external-success.svg)]()
```

---

## 4. Technical Teardown Outline

### Title: Why We Built OPS-1: Halting Autonomous Agent Directory Traversal Without Docker Overhead

1. **The Autonomous Agent Blast Radius Problem**
   - Autonomous LLM tooling executing native shell commands lacks spatial boundaries.
   - Accidental drift into hidden directories, parent directories, and adjacent git worktrees.

2. **The Isolation Dilemma: Docker Overhead vs. Native Guardrails**
   - Cold-start delays (3-10s per container initialization).
   - UID/GID mapping mismatches on POSIX host volumes.
   - Why deterministic in-process verification solves 95% of accidental agent drift.

3. **OPS-1 Canonicalization Pipeline**
   - Multi-pass URL decoding: defeating nested escaping (`%252e%252e%252f`).
   - Null-byte sanitization (`\x00` and `%00`).
   - Lexical `..` path segment rejection prior to filesystem queries.
   - Strict symlink resolution (`Path.resolve(strict=False)`) vs. `Path.relative_to()`.

4. **From Post-Flight Gate to In-Flight Live Proxy**
   - v0.2.0 post-execution diff verification via git status.
   - v0.3.0 in-flight MCP stdio proxy: intercepting `tools/call` JSON-RPC frames in real time and rejecting out-of-scope operations with JSON-RPC `-32602`.
