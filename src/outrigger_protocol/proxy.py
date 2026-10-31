"""
Outrigger Protocol (OPS-1) - Live In-Flight MCP Stdio Security Proxy
Zero-dependency Python 3.10+ standard library implementation.
Author: Alan Woodyard (https://alanwoodyard.com)
"""

import sys
import json
import subprocess
from pathlib import Path
import threading
import urllib.parse
import shlex
import re
from typing import Any

class OutriggerBoundaryError(Exception):
    """Raised when an agent operation attempts to access or mutate paths outside allowed boundaries."""
    pass

PATH_KEYS = {
    "path", "paths", "file_path", "filepath", "source", "destination",
    "dest", "directory", "dir", "cwd", "target_path", "vault_path", "output_dir"
}

COMMAND_KEYS = {"command", "cmd", "script"}

CONTENT_KEYS = {"content", "diff", "patch", "text", "body"}

SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]{10,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{10,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"sk_live_[A-Za-z0-9]{10,}"),
    re.compile(r"rk_live_[A-Za-z0-9]{10,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

def _has_dotdot_segment(path_str: str) -> bool:
    normalized = path_str.replace("\\", "/")
    segments = [seg for seg in normalized.split("/") if seg]
    return ".." in segments or path_str == ".."

def ensure_within_scope(candidate: str | Path, allowed_roots: list[Path]) -> Path:
    if not allowed_roots:
        raise OutriggerBoundaryError("No allowed roots defined for scope containment.")

    raw = str(candidate)

    if "\x00" in raw or "%00" in raw.lower():
        raise OutriggerBoundaryError(f"Null byte detected in path: {raw!r}")

    decoded_pass1 = urllib.parse.unquote(raw)
    decoded = urllib.parse.unquote(decoded_pass1)

    if "\x00" in decoded_pass1 or "%00" in decoded_pass1.lower() or "\x00" in decoded or "%00" in decoded.lower():
        raise OutriggerBoundaryError(f"Null byte detected after URL decoding: {raw!r}")

    if _has_dotdot_segment(raw) or _has_dotdot_segment(decoded_pass1) or _has_dotdot_segment(decoded):
        raise OutriggerBoundaryError(f"Directory traversal '..' detected in path: {raw!r}")

    cand_path = Path(decoded)
    resolved = cand_path.resolve(strict=False)

    resolved_roots = [Path(r).resolve() for r in allowed_roots]
    in_scope = False

    for root in resolved_roots:
        try:
            resolved.relative_to(root)
            in_scope = True
            break
        except ValueError:
            pass

    if not in_scope and not cand_path.is_absolute():
        for root in resolved_roots:
            cand_relative = (root / cand_path).resolve(strict=False)
            try:
                cand_relative.relative_to(root)
                resolved = cand_relative
                in_scope = True
                break
            except ValueError:
                pass

    if not in_scope:
        raise OutriggerBoundaryError(
            f"Path '{raw}' (resolved: '{resolved}') is outside allowed boundaries: {[str(r) for r in resolved_roots]}"
        )

    return resolved

def _scan_secrets(text: str, secret_scanner: Any = None) -> None:
    if not isinstance(text, str):
        return
    if secret_scanner is not None:
        if callable(secret_scanner):
            secret_scanner(text)
        elif hasattr(secret_scanner, "scan"):
            secret_scanner.scan(text)
        return

    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise OutriggerBoundaryError(
                f"Potential secret leaked in payload content matching pattern: {pattern.pattern}"
            )

def _inspect_command_str(cmd_str: str, allowed_roots: list[Path]) -> None:
    if "\x00" in cmd_str or "%00" in cmd_str.lower():
        raise OutriggerBoundaryError(f"Null byte detected in command: {cmd_str!r}")

    try:
        tokens = shlex.split(cmd_str)
    except ValueError as e:
        raise OutriggerBoundaryError(f"Malformed command cannot be parsed: {e}") from e

    for token in tokens:
        if "\x00" in token or "%00" in token.lower():
            raise OutriggerBoundaryError(f"Null byte detected in token: {token!r}")
        if _has_dotdot_segment(token):
            raise OutriggerBoundaryError(f"Directory traversal '..' detected in command token: {token!r}")

        check_paths = []
        if "=" in token and not token.startswith("-"):
            _, val = token.split("=", 1)
            check_paths.append(val)
        elif token.startswith("--") and "=" in token:
            _, val = token.split("=", 1)
            check_paths.append(val)
        else:
            check_paths.append(token)

        for cand in check_paths:
            p = Path(cand)
            if p.is_absolute():
                ensure_within_scope(p, allowed_roots)

def inspect_arguments(payload: Any, allowed_roots: list[Path], secret_scanner: Any = None) -> None:
    if payload is None:
        return

    if isinstance(payload, dict):
        if "params" in payload and isinstance(payload["params"], dict):
            inspect_arguments(payload["params"].get("arguments", {}), allowed_roots, secret_scanner)
            for k, v in payload["params"].items():
                if k != "arguments":
                    inspect_arguments({k: v}, allowed_roots, secret_scanner)
            return

        for k, v in payload.items():
            k_lower = str(k).lower()
            if k_lower in PATH_KEYS:
                if isinstance(v, (str, Path)):
                    ensure_within_scope(v, allowed_roots)
                elif isinstance(v, (list, tuple)):
                    for item in v:
                        if isinstance(item, (str, Path)):
                            ensure_within_scope(item, allowed_roots)
                        elif isinstance(item, (dict, list)):
                            inspect_arguments(item, allowed_roots, secret_scanner)
                elif isinstance(v, dict):
                    inspect_arguments(v, allowed_roots, secret_scanner)
            elif k_lower in COMMAND_KEYS:
                if isinstance(v, str):
                    _inspect_command_str(v, allowed_roots)
                elif isinstance(v, (list, tuple)):
                    for item in v:
                        if isinstance(item, str):
                            _inspect_command_str(item, allowed_roots)
            elif k_lower in CONTENT_KEYS:
                if isinstance(v, str):
                    _scan_secrets(v, secret_scanner)
                elif isinstance(v, (dict, list)):
                    inspect_arguments(v, allowed_roots, secret_scanner)
            else:
                if isinstance(v, (dict, list)):
                    inspect_arguments(v, allowed_roots, secret_scanner)

    elif isinstance(payload, (list, tuple)):
        for item in payload:
            if isinstance(item, (dict, list)):
                inspect_arguments(item, allowed_roots, secret_scanner)

def run_stdio_proxy(target_cmd: list[str], allowed_roots: list[Path], secret_scanner: Any = None) -> int:
    if not target_cmd:
        raise ValueError("Target MCP command cannot be empty.")
    if not allowed_roots:
        raise OutriggerBoundaryError("Allowed roots cannot be empty.")

    proc = subprocess.Popen(
        target_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        encoding="utf-8",
        bufsize=1
    )

    def stdout_forwarder():
        try:
            if proc.stdout:
                for line in proc.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass

    forwarder_thread = threading.Thread(target=stdout_forwarder, daemon=True)
    forwarder_thread.start()

    try:
        for line in sys.stdin:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            try:
                frame = json.loads(line_stripped)
            except json.JSONDecodeError:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.write(line)
                    proc.stdin.flush()
                continue

            method = frame.get("method")
            msg_id = frame.get("id")

            if method == "tools/call":
                params = frame.get("params", {})
                args = params.get("arguments", {})
                try:
                    inspect_arguments(args, allowed_roots, secret_scanner)
                    inspect_arguments(params, allowed_roots, secret_scanner)
                except OutriggerBoundaryError as err:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32602,
                            "message": f"Outrigger Boundary Violation: {err}"
                        }
                    }
                    sys.stdout.write(json.dumps(err_resp) + "\n")
                    sys.stdout.flush()
                    continue

            if proc.stdin and not proc.stdin.closed:
                proc.stdin.write(line if line.endswith("\n") else line + "\n")
                proc.stdin.flush()

    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        if proc.stdin and not proc.stdin.closed:
            try:
                proc.stdin.close()
            except OSError:
                pass
        returncode = proc.wait()
        forwarder_thread.join(timeout=1.0)

    return returncode
