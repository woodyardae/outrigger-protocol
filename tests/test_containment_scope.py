"""OPS-1 exit-code hardening and git-diff scope containment tests."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cli import outrigger


def _ops1_manifest(**overrides: object) -> dict:
    manifest = {
        "protocol": "OPS-1",
        "task_id": "ops1-scope",
        "objective": "Contain writes",
        "writable_scope": ["cli/", "tests/test_containment_scope.py"],
        "branch": "feat/ops1-exit-code-hardening",
        "acceptance_criteria": [],
        "validation_commands": ["git diff --name-only base123 HEAD"],
        "forbidden_actions": [],
        "handoff_path": ".outrigger/handoffs/ops1-scope-hub-report.md",
    }
    manifest.update(overrides)
    return manifest


def _containment_manifest(**overrides: object) -> dict:
    manifest = {
        "ops_version": "1.0",
        "task_id": "OPS-CHECK-001",
        "authority": {
            "base_commit": "base123",
            "target_branch": "feat/ops1-exit-code-hardening",
        },
        "containment": {
            "writable_paths": ["cli/", "tests/test_containment_scope.py"],
            "forbidden_patterns": ["**/config/secrets.json", "**/*.pem", ".env*"],
        },
        "validation": {
            "commands": ["python -m unittest"],
            "required_verdict": "PASS",
        },
    }
    manifest.update(overrides)
    return manifest


class CollectScopeViolationsTests(unittest.TestCase):
    def test_allowed_writes_produce_no_violations(self):
        violations = outrigger.collect_scope_violations(
            ["cli/outrigger.py", "tests/test_containment_scope.py"],
            ["cli/", "tests/test_containment_scope.py"],
            [],
        )
        self.assertEqual(violations, [])

    def test_outside_writable_scope_is_reported(self):
        violations = outrigger.collect_scope_violations(
            ["cli/outrigger.py", "SPEC.md"],
            ["cli/"],
            [],
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("SPEC.md", violations[0])
        self.assertIn("outside writable scope", violations[0])

    def test_forbidden_pattern_blocks_even_inside_writable_prefix(self):
        violations = outrigger.collect_scope_violations(
            ["cli/config/secrets.json"],
            ["cli/"],
            ["**/config/secrets.json"],
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("forbidden pattern match", violations[0])
        self.assertIn("cli/config/secrets.json", violations[0])

    def test_pem_and_env_forbidden_patterns(self):
        violations = outrigger.collect_scope_violations(
            ["certs/prod.pem", ".env.local"],
            ["certs/", ".env.local"],
            ["**/*.pem", ".env*"],
        )
        self.assertEqual(len(violations), 2)


class CheckCommandExitCodeTests(unittest.TestCase):
    @mock.patch("cli.outrigger._run_git")
    def test_check_pass_exit_zero_with_json(self, run_git):
        run_git.return_value = "cli/outrigger.py\ntests/test_containment_scope.py"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(_containment_manifest()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(
                    ["check", "--manifest", str(path), "--json"]
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["violations"], [])
        run_git.assert_called_with("diff", "--name-only", "base123", cwd=None)

    @mock.patch("cli.outrigger._run_git")
    def test_check_scope_violation_exit_two(self, run_git):
        run_git.return_value = "cli/outrigger.py\nREADME.md"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(_containment_manifest()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(
                    ["check", "--manifest", str(path), "--json"]
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertEqual(payload["exit_code"], 2)
        self.assertTrue(
            any("README.md" in item for item in payload["violations"])
        )

    @mock.patch("cli.outrigger._run_git")
    def test_check_forbidden_file_exit_two(self, run_git):
        run_git.return_value = "cli/config/secrets.json"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(_containment_manifest()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(
                    ["check", "--manifest", str(path), "--json"]
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertTrue(
            any("forbidden" in item for item in payload["violations"])
        )

    def test_check_invalid_manifest_exit_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text("{not-json", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(
                    ["check", "--manifest", str(path), "--json"]
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["exit_code"], 1)
        self.assertTrue(payload["violations"])

    @mock.patch("cli.outrigger._run_git")
    def test_check_ops1_writable_scope_manifest(self, run_git):
        run_git.return_value = "cli/outrigger.py"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(_ops1_manifest()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(
                    ["check", "--manifest", str(path), "--json"]
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "PASS")
        run_git.assert_called_with("diff", "--name-only", "base123", cwd=None)

    @mock.patch("cli.outrigger._run_git")
    def test_check_explicit_base_override(self, run_git):
        run_git.return_value = "cli/outrigger.py"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(_containment_manifest()), encoding="utf-8")
            code = outrigger.main(
                ["check", "--manifest", str(path), "--base", "abc999", "--json"]
            )
        self.assertEqual(code, 0)
        run_git.assert_called_with("diff", "--name-only", "abc999", cwd=None)


class ReturnCodePropagationTests(unittest.TestCase):
    def test_exit_constants(self):
        self.assertEqual(outrigger.EXIT_PASS, 0)
        self.assertEqual(outrigger.EXIT_FAIL, 1)
        self.assertEqual(outrigger.EXIT_BLOCKED, 2)

    def test_scope_violation_error_maps_to_blocked(self):
        exc = outrigger.ScopeViolationError(["outside writable scope: SPEC.md"])
        self.assertIsInstance(exc, outrigger.OutriggerError)
        self.assertEqual(exc.violations, ["outside writable scope: SPEC.md"])


if __name__ == "__main__":
    unittest.main()
