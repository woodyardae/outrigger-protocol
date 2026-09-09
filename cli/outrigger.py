"""Standard-library command line tools for the Outrigger protocol."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


PROTOCOL = "OPS-1"
VERDICTS = {"PASS", "FAIL", "BLOCKED"}
MANIFEST_FIELDS = (
    "protocol",
    "task_id",
    "objective",
    "writable_scope",
    "branch",
    "acceptance_criteria",
    "validation_commands",
    "forbidden_actions",
    "handoff_path",
)
REPORT_FIELDS = (
    "protocol",
    "task_id",
    "verdict",
    "summary",
    "branch",
    "HEAD_SHA",
    "commits",
    "files_changed",
    "commands",
    "validation",
    "evidence",
    "risks",
    "blockers",
    "attempt",
    "caveats",
)
LEAK_PATTERNS = (
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[a-zA-Z]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN(?: [A-Z0-9]+)* PRIVATE KEY-----"),
)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class OutriggerError(ValueError):
    """An input could not be verified safely."""


def _run_git(*args: str, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    if not slug or slug in {".", ".."}:
        raise OutriggerError("unit-name must contain a letter or number")
    return slug


def _default_manifest(unit_name: str, cwd: Path) -> dict[str, Any]:
    base = _run_git("rev-parse", "HEAD", cwd=cwd)
    branch = _run_git("branch", "--show-current", cwd=cwd)
    unit = _slug(unit_name)
    return {
        "protocol": PROTOCOL,
        "task_id": unit_name,
        "objective": "",
        "writable_scope": [],
        "branch": branch,
        "acceptance_criteria": [],
        "validation_commands": [f"git diff --name-only {base} HEAD"],
        "forbidden_actions": [],
        "handoff_path": f".outrigger/handoffs/{unit}-hub-report.md",
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OutriggerError(f"cannot read JSON manifest: {path}") from exc


def _validate_manifest_shape(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise OutriggerError("manifest must be a JSON object")
    actual = set(manifest)
    expected = set(MANIFEST_FIELDS)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        detail = []
        if missing:
            detail.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            detail.append(f"unknown fields: {', '.join(unknown)}")
        raise OutriggerError("; ".join(detail))
    if manifest["protocol"] != PROTOCOL:
        raise OutriggerError("manifest protocol must be OPS-1")
    for field in (
        "writable_scope",
        "acceptance_criteria",
        "validation_commands",
        "forbidden_actions",
    ):
        if not isinstance(manifest[field], list) or not all(
            isinstance(item, str) for item in manifest[field]
        ):
            raise OutriggerError(f"manifest {field} must be an array of strings")
    for field in ("task_id", "objective", "branch", "handoff_path"):
        if not isinstance(manifest[field], str):
            raise OutriggerError(f"manifest {field} must be a string")
    return manifest


def command_init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    (root / ".outrigger" / "handoffs").mkdir(parents=True, exist_ok=True)
    destination = root / ".outrigger" / "templates"
    destination.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parent.parent / "templates"
    if not source.is_dir():
        raise OutriggerError(f"bundled templates directory is unavailable: {source}")
    copied = 0
    for template in sorted(source.glob("*.md")):
        target = destination / template.name
        if not target.exists():
            target.write_bytes(template.read_bytes())
            copied += 1
    print(f"Initialized .outrigger ({copied} template(s) copied)")
    return 0


def command_new(args: argparse.Namespace) -> int:
    manifest = _default_manifest(args.unit_name, Path.cwd())
    if args.template:
        template = _validate_manifest_shape(_load_json(Path(args.template)))
        manifest.update(template)
        generated = _default_manifest(args.unit_name, Path.cwd())
        manifest["protocol"] = PROTOCOL
        manifest["task_id"] = args.unit_name
        manifest["branch"] = generated["branch"]
        manifest["validation_commands"] = generated["validation_commands"]
        manifest["handoff_path"] = generated["handoff_path"]
    print(json.dumps(_validate_manifest_shape(manifest), indent=2))
    return 0


def command_auth_gate(args: argparse.Namespace) -> int:
    command = ["gh", "secret", "list", "--json", "name"]
    if args.repo:
        command.extend(["--repo", args.repo])
    names: set[str] = set()
    gh_failed = False
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            gh_failed = True
        else:
            payload = json.loads(result.stdout)
            names = {
                item.get("name")
                for item in payload
                if isinstance(item, dict) and item.get("name")
            }
    except (OSError, json.JSONDecodeError):
        gh_failed = True

    secrets: list[str] = args.secret
    if len(secrets) == 1:
        present = not gh_failed and secrets[0] in names
        print("PRESENT" if present else "ABSENT")
        return 0 if present else 2

    all_present = True
    for secret in secrets:
        present = not gh_failed and secret in names
        all_present = all_present and present
        print(f"{secret}: {'PRESENT' if present else 'ABSENT'}")
    return 0 if all_present else 2


def parse_markdown_sections(text: str) -> list[tuple[str, str]]:
    matches = list(HEADING_RE.finditer(text))
    return [
        (
            match.group(1).strip(),
            text[match.end() : matches[index + 1].start()].strip()
            if index + 1 < len(matches)
            else text[match.end() :].strip(),
        )
        for index, match in enumerate(matches)
    ]


def _report_values(text: str) -> dict[str, str]:
    sections = parse_markdown_sections(text)
    names = [name for name, _ in sections]
    if names != list(REPORT_FIELDS):
        missing = [field for field in REPORT_FIELDS if field not in names]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        messages = ["report headings must exactly match OPS-1 order"]
        if missing:
            messages.append(f"missing: {', '.join(missing)}")
        if duplicates:
            messages.append(f"duplicate: {', '.join(duplicates)}")
        raise OutriggerError("; ".join(messages))
    values = dict(sections)
    if values["protocol"].strip() != PROTOCOL:
        raise OutriggerError("report protocol must be OPS-1")
    verdict = values["verdict"].strip()
    if verdict not in VERDICTS:
        raise OutriggerError("report verdict must be PASS, FAIL, or BLOCKED")
    return values


def find_leaks(text: str) -> list[str]:
    labels = ("ghp_", "github_pat_", "xox token", "private key")
    return [
        label
        for label, pattern in zip(labels, LEAK_PATTERNS)
        if pattern.search(text)
    ]


def _extract_diff_endpoints(manifest: dict[str, Any]) -> tuple[str, str]:
    explicit_base = manifest.get("BASE") or manifest.get("base")
    explicit_head = manifest.get("HEAD") or manifest.get("head")
    if explicit_base:
        return str(explicit_base), str(explicit_head or "HEAD")
    pattern = re.compile(r"^git diff --name-only\s+(\S+)\s+(\S+)$")
    for command in manifest.get("validation_commands", []):
        match = pattern.match(command.strip())
        if match:
            return match.group(1), match.group(2)
    raise OutriggerError(
        "manifest validation_commands must include "
        "'git diff --name-only BASE HEAD'"
    )


def _normal_path(value: str, *, directory: bool = False) -> str:
    value = value.replace("\\", "/")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise OutriggerError(f"unsafe repository-relative path: {value}")
    normalized = str(pure)
    if normalized in {"", "."}:
        raise OutriggerError("empty scope paths are not allowed")
    if directory and value.endswith("/"):
        normalized += "/"
    return normalized


def path_is_allowed(path: str, scopes: Sequence[str]) -> bool:
    candidate = _normal_path(path)
    for raw_scope in scopes:
        scope = _normal_path(raw_scope, directory=True)
        if scope.endswith("/"):
            if candidate.startswith(scope):
                return True
        elif candidate == scope:
            return True
    return False


def _read_manifest_for_verify(path: Path) -> dict[str, Any]:
    manifest = _load_json(path)
    # Operational BASE/HEAD keys are accepted for compatibility, but a
    # generated OPS-1 manifest stores the exact command in validation_commands.
    if isinstance(manifest, dict) and set(manifest) <= set(MANIFEST_FIELDS):
        return _validate_manifest_shape(manifest)
    if not isinstance(manifest, dict):
        raise OutriggerError("manifest must be a JSON object")
    allowed = set(MANIFEST_FIELDS) | {"BASE", "HEAD", "base", "head", "WRITABLE_SCOPE"}
    unknown = set(manifest) - allowed
    if unknown:
        raise OutriggerError(f"unknown fields: {', '.join(sorted(unknown))}")
    if "WRITABLE_SCOPE" in manifest and "writable_scope" not in manifest:
        manifest["writable_scope"] = manifest["WRITABLE_SCOPE"]
    return manifest


def _check_manifest_report_binding(
    manifest: dict[str, Any], report_values: dict[str, str]
) -> list[str]:
    """Cross-checks a manifest and its Hub Report agree on task identity.

    Confirms task_id and branch match between the manifest that authorized
    the work and the report that claims to account for it, so a report
    cannot be silently swapped onto an unrelated manifest.
    """
    problems = []
    manifest_task_id = str(manifest.get("task_id", "")).strip()
    report_task_id = report_values.get("task_id", "").strip()
    if manifest_task_id and report_task_id and manifest_task_id != report_task_id:
        problems.append(
            f"manifest task_id ({manifest_task_id!r}) does not match "
            f"report task_id ({report_task_id!r})"
        )
    manifest_branch = str(manifest.get("branch", "")).strip()
    report_branch = report_values.get("branch", "").strip()
    if manifest_branch and report_branch and manifest_branch != report_branch:
        problems.append(
            f"manifest branch ({manifest_branch!r}) does not match "
            f"report branch ({report_branch!r})"
        )
    return problems


def _commit_exists(sha: str) -> bool:
    try:
        _run_git("cat-file", "-e", f"{sha}^{{commit}}")
        return True
    except subprocess.CalledProcessError:
        return False


def command_verify(args: argparse.Namespace) -> int:
    report_path = Path(args.report)
    try:
        text = report_path.read_text(encoding="utf-8")
        problems = [f"possible secret material: {label}" for label in find_leaks(text)]
        report_values: dict[str, str] = {}
        if not problems:
            report_values = _report_values(text)
        if args.manifest:
            manifest_text = Path(args.manifest).read_text(encoding="utf-8")
            problems.extend(
                f"possible secret material in manifest: {label}"
                for label in find_leaks(manifest_text)
            )
            manifest = _read_manifest_for_verify(Path(args.manifest))
            if report_values:
                problems.extend(_check_manifest_report_binding(manifest, report_values))
            if not args.no_git:
                base, head = _extract_diff_endpoints(manifest)
                changed = _run_git("diff", "--name-only", base, head).splitlines()
                scopes = manifest.get("writable_scope", [])
                outside = [path for path in changed if not path_is_allowed(path, scopes)]
                if outside:
                    problems.append(
                        "changed paths outside WRITABLE_SCOPE: " + ", ".join(outside)
                    )
                if report_values:
                    head_sha = report_values["HEAD_SHA"].strip()
                    if head_sha and not _commit_exists(head_sha):
                        problems.append(
                            f"report HEAD_SHA does not resolve to a known commit: {head_sha}"
                        )
    except (OSError, UnicodeError, subprocess.CalledProcessError, OutriggerError) as exc:
        problems = [str(exc)]
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    print("PASS")
    return 0


def _first_line(value: str, default: str = "-") -> str:
    for line in value.splitlines():
        clean = line.strip().strip("`").lstrip("- ").strip()
        if clean:
            return clean
    return default


def _batch_number(path: Path, sections: dict[str, str]) -> int:
    candidates = (path.stem, sections.get("batch", ""), sections.get("task_id", ""))
    for candidate in candidates:
        match = re.search(r"\bbatch[-_ ]?(\d+)\b", candidate, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def command_ledger(args: argparse.Namespace) -> int:
    directory = Path(args.dir)
    rows: list[tuple[int, str, str, str, str]] = []
    for report in directory.glob("*.md"):
        try:
            sections = {
                name.lower(): value
                for name, value in parse_markdown_sections(
                    report.read_text(encoding="utf-8")
                )
            }
        except (OSError, UnicodeError):
            continue
        batch = _batch_number(report, sections)
        rows.append(
            (
                batch,
                _first_line(sections.get("unit", sections.get("task_id", "-"))),
                _first_line(sections.get("agent", "-")),
                _first_line(sections.get("status", "-")),
                _first_line(sections.get("verdict", "-")),
            )
        )
    rows.sort(key=lambda row: row[0])
    next_batch = max((row[0] for row in rows), default=0) + 1
    if args.json:
        payload = {
            "batches": [
                {
                    "batch": batch,
                    "unit": unit,
                    "agent": agent,
                    "status": status,
                    "verdict": verdict,
                }
                for batch, unit, agent, status, verdict in rows
            ],
            "next_expected_batch": next_batch,
        }
        print(json.dumps(payload, indent=2))
        return 0
    print("| Batch | Unit | Agent | Status | Verdict |")
    print("|---:|---|---|---|---|")
    for batch, unit, agent, status, verdict in rows:
        print(f"| {batch or '-'} | {unit} | {agent} | {status} | {verdict} |")
    print(f"\nNext expected batch: {next_batch}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="outrigger")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.set_defaults(handler=command_init)

    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("unit_name")
    new_parser.add_argument("--template")
    new_parser.set_defaults(handler=command_new)

    auth_parser = subparsers.add_parser("auth-gate")
    auth_parser.add_argument("--secret", required=True, nargs="+")
    auth_parser.add_argument("--repo")
    auth_parser.set_defaults(handler=command_auth_gate)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("report")
    verify_parser.add_argument("--manifest")
    verify_parser.add_argument("--no-git", action="store_true")
    verify_parser.set_defaults(handler=command_verify)

    ledger_parser = subparsers.add_parser("ledger")
    ledger_parser.add_argument("--dir", default=".outrigger/handoffs")
    ledger_parser.add_argument("--json", action="store_true")
    ledger_parser.set_defaults(handler=command_ledger)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (OutriggerError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
