# Show HN: Outrigger Protocol – Zero-Dependency Agent Containment & Handoffs

When delegating development to autonomous coding agents (Claude Code, Cursor) or external scripts, conversational "done" states fail silently: changes leak outside intended directories, ambient keys risk exfiltration, and downstream agents receive broken baselines.

Outrigger is an open specification (OPS-1) and zero-dependency Python CLI (CPython 3.10+ stdlib only). It replaces ambiguous LLM outputs with machine-checked operational boundaries:

1. **Explicit Scope:** Restricts file writes strictly to paths defined in a JSON Task Manifest.
2. **Zero-Knowledge Auth Gating:** Verifies token presence using local CLI utilities without passing credentials into agent contexts.
3. **Leak Scanning:** Rejects execution records carrying private key headers, Slack tokens, or GitHub PAT signatures.
4. **Deterministic Exit States:** Enforces hard verdicts (PASS, FAIL, BLOCKED). No soft middle ground.
5. **Deterministic Relays:** Generates structured Hub Reports that serve as verifiable inputs for subsequent agents in a pipeline.

Repo: https://github.com/woodyardae/outrigger-protocol
Composite Action: `uses: woodyardae/outrigger-protocol@v1`

We dogfood this across internal multi-repo pipelines to prevent runaway agent modifications. We are looking for maintainers running local or multi-agent test loops to audit the containment verifier and surface edge cases.
