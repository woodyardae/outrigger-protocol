from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from cli import outrigger


def hub_report(**overrides: str) -> str:
    values = {
        "protocol": "OPS-1",
        "task_id": "batch-2",
        "verdict": "PASS",
        "summary": "Implemented the requested batch.",
        "branch": "feat/batch-2-engine-and-tests",
        "HEAD_SHA": "a" * 40,
        "commits": "1. `abc` — `feat: example`",
        "files_changed": "- `cli/outrigger.py` — CLI.",
        "commands": "- `python -m unittest` — exit `0`.",
        "validation": "- Tests — PASS.",
        "evidence": "- 10 tests passed.",
        "risks": "None.",
        "blockers": "None.",
        "attempt": "1",
        "caveats": "None.",
    }
    values.update(overrides)
    body = ["# Batch 2 Hub Report", ""]
    for field in outrigger.REPORT_FIELDS:
        body.extend((f"## {field}", "", values[field], ""))
    return "\n".join(body)


@contextlib.contextmanager
def working_directory(path: Path):
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


class MarkdownParsingTests(unittest.TestCase):
    def test_parse_sections_preserves_order_and_content(self):
        sections = outrigger.parse_markdown_sections(
            "# Report\n\n## protocol\n\nOPS-1\n\n## verdict\n\nPASS\n"
        )
        self.assertEqual(
            sections, [("protocol", "OPS-1"), ("verdict", "PASS")]
        )

    def test_report_requires_exact_headers_in_order(self):
        report = hub_report().replace("## summary", "## unexpected", 1)
        with self.assertRaisesRegex(outrigger.OutriggerError, "exactly match"):
            outrigger._report_values(report)

    def test_report_rejects_invalid_verdict(self):
        with self.assertRaisesRegex(outrigger.OutriggerError, "PASS, FAIL"):
            outrigger._report_values(hub_report(verdict="SUCCESS"))


class LeakDetectionTests(unittest.TestCase):
    def test_detects_github_and_slack_token_families(self):
        samples = {
            "ghp_" + "a" * 36: "ghp_",
            "github_pat_" + "a" * 30: "github_pat_",
            "xoxb-" + "1" * 12: "xox token",
            "xoxp-" + "a" * 12: "xox token",
        }
        for secret, label in samples.items():
            with self.subTest(label=label):
                self.assertIn(label, outrigger.find_leaks(secret))

    def test_detects_private_key_block(self):
        text = "-----BEGIN OPENSSH PRIVATE KEY-----\nredacted"
        self.assertEqual(outrigger.find_leaks(text), ["private key"])

    def test_does_not_flag_short_placeholders(self):
        self.assertEqual(
            outrigger.find_leaks("Examples: ghp_redacted, xoxb_example"), []
        )


class ScopeContainmentTests(unittest.TestCase):
    def test_exact_file_scope(self):
        self.assertTrue(
            outrigger.path_is_allowed("cli/outrigger.py", ["cli/outrigger.py"])
        )
        self.assertFalse(
            outrigger.path_is_allowed("cli/other.py", ["cli/outrigger.py"])
        )

    def test_directory_scope_requires_trailing_slash(self):
        self.assertTrue(outrigger.path_is_allowed("cli/deep/file.py", ["cli/"]))
        self.assertFalse(outrigger.path_is_allowed("cli2/file.py", ["cli/"]))
        self.assertFalse(outrigger.path_is_allowed("cli/file.py", ["cli"]))

    def test_rejects_parent_traversal(self):
        with self.assertRaisesRegex(outrigger.OutriggerError, "unsafe"):
            outrigger.path_is_allowed("../SPEC.md", ["cli/"])


class AuthGateTests(unittest.TestCase):
    @mock.patch("cli.outrigger.subprocess.run")
    def test_present_secret_returns_zero_without_value_access(self, run):
        run.return_value = mock.Mock(
            returncode=0,
            stdout=json.dumps([{"name": "DEPLOY_TOKEN"}]),
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = outrigger.main(
                ["auth-gate", "--secret", "DEPLOY_TOKEN", "--repo", "o/r"]
            )
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue().strip(), "PRESENT")
        run.assert_called_once_with(
            [
                "gh",
                "secret",
                "list",
                "--json",
                "name",
                "--repo",
                "o/r",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    @mock.patch("cli.outrigger.subprocess.run")
    def test_absent_and_gh_failure_return_two(self, run):
        for result in (
            mock.Mock(returncode=0, stdout="[]"),
            mock.Mock(returncode=1, stdout="", stderr="sensitive error"),
        ):
            with self.subTest(returncode=result.returncode):
                run.return_value = result
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = outrigger.main(
                        ["auth-gate", "--secret", "DEPLOY_TOKEN"]
                    )
                self.assertEqual(code, 2)
                self.assertEqual(output.getvalue().strip(), "ABSENT")

    @mock.patch("cli.outrigger.subprocess.run")
    def test_multi_secret_reports_each_and_exits_zero_when_all_present(self, run):
        run.return_value = mock.Mock(
            returncode=0,
            stdout=json.dumps([{"name": "A"}, {"name": "B"}]),
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = outrigger.main(
                ["auth-gate", "--secret", "A", "B", "--repo", "o/r"]
            )
        self.assertEqual(code, 0)
        lines = output.getvalue().strip().splitlines()
        self.assertEqual(lines, ["A: PRESENT", "B: PRESENT"])
        run.assert_called_once()

    @mock.patch("cli.outrigger.subprocess.run")
    def test_multi_secret_exits_two_when_any_absent(self, run):
        run.return_value = mock.Mock(
            returncode=0,
            stdout=json.dumps([{"name": "A"}]),
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = outrigger.main(["auth-gate", "--secret", "A", "B"])
        self.assertEqual(code, 2)
        lines = output.getvalue().strip().splitlines()
        self.assertEqual(lines, ["A: PRESENT", "B: ABSENT"])


class InitAndNewTests(unittest.TestCase):
    def test_init_is_idempotent_and_does_not_overwrite_templates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with working_directory(root):
                self.assertEqual(outrigger.main(["init"]), 0)
                target = root / ".outrigger" / "templates" / "00-auth-gate.md"
                target.write_text("local customization", encoding="utf-8")
                self.assertEqual(outrigger.main(["init"]), 0)
            self.assertTrue((root / ".outrigger" / "handoffs").is_dir())
            self.assertEqual(target.read_text(encoding="utf-8"), "local customization")
            self.assertEqual(
                len(list((root / ".outrigger" / "templates").glob("*.md"))), 3
            )

    @mock.patch("cli.outrigger._run_git")
    def test_new_emits_exact_manifest_with_base_and_handoff(self, run_git):
        run_git.side_effect = ["b" * 40, "feat/unit"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = outrigger.main(["new", "unit one"])
        manifest = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(set(manifest), set(outrigger.MANIFEST_FIELDS))
        self.assertEqual(manifest["task_id"], "unit one")
        self.assertEqual(manifest["branch"], "feat/unit")
        self.assertEqual(
            manifest["validation_commands"],
            [f"git diff --name-only {'b' * 40} HEAD"],
        )
        self.assertEqual(
            manifest["handoff_path"],
            ".outrigger/handoffs/unit-one-hub-report.md",
        )

    @mock.patch("cli.outrigger._run_git")
    def test_new_uses_template_defaults_but_refreshes_designated_fields(
        self, run_git
    ):
        run_git.side_effect = ["a" * 40, "old", "b" * 40, "current"]
        template = {
            "protocol": "OPS-1",
            "task_id": "old",
            "objective": "Do the bounded task",
            "writable_scope": ["cli/"],
            "branch": "old",
            "acceptance_criteria": ["It works"],
            "validation_commands": ["old command"],
            "forbidden_actions": ["Network"],
            "handoff_path": "old.md",
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(template), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(["new", "new-unit", "--template", str(path)])
        manifest = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(manifest["objective"], "Do the bounded task")
        self.assertEqual(manifest["writable_scope"], ["cli/"])
        self.assertEqual(manifest["branch"], "current")
        self.assertEqual(
            manifest["handoff_path"],
            ".outrigger/handoffs/new-unit-hub-report.md",
        )


class VerifyTests(unittest.TestCase):
    def test_verify_report_without_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.md"
            report.write_text(hub_report(), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(["verify", str(report), "--no-git"])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue().strip(), "PASS")

    def test_verify_rejects_leak(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.md"
            report.write_text(
                hub_report(evidence="ghp_" + "z" * 30), encoding="utf-8"
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(["verify", str(report), "--no-git"])
        self.assertEqual(code, 1)
        self.assertIn("possible secret material", output.getvalue())

    @mock.patch("cli.outrigger._run_git")
    def test_verify_checks_git_diff_containment(self, run_git):
        manifest = {
            "protocol": "OPS-1",
            "task_id": "batch-2",
            "objective": "",
            "writable_scope": ["cli/", "tests/test_outrigger.py"],
            "branch": "feat/batch-2-engine-and-tests",
            "acceptance_criteria": [],
            "validation_commands": ["git diff --name-only base123 HEAD"],
            "forbidden_actions": [],
            "handoff_path": ".outrigger/handoffs/unit-hub-report.md",
        }
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.md"
            manifest_path = Path(temporary) / "manifest.json"
            report.write_text(hub_report(), encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            run_git.side_effect = [
                "cli/outrigger.py\ntests/test_outrigger.py",
                None,
            ]
            self.assertEqual(
                outrigger.main(
                    ["verify", str(report), "--manifest", str(manifest_path)]
                ),
                0,
            )
            run_git.side_effect = ["cli/outrigger.py\nSPEC.md", None]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(
                    ["verify", str(report), "--manifest", str(manifest_path)]
                )
        self.assertEqual(code, 1)
        self.assertIn("SPEC.md", output.getvalue())

    def test_verify_rejects_manifest_report_task_id_mismatch(self):
        manifest = {
            "protocol": "OPS-1",
            "task_id": "batch-9",
            "objective": "",
            "writable_scope": ["cli/"],
            "branch": "feat/batch-2-engine-and-tests",
            "acceptance_criteria": [],
            "validation_commands": [],
            "forbidden_actions": [],
            "handoff_path": ".outrigger/handoffs/batch-9-hub-report.md",
        }
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.md"
            manifest_path = Path(temporary) / "manifest.json"
            report.write_text(hub_report(), encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(
                    [
                        "verify",
                        str(report),
                        "--manifest",
                        str(manifest_path),
                        "--no-git",
                    ]
                )
        self.assertEqual(code, 1)
        self.assertIn("task_id", output.getvalue())

    def test_verify_rejects_manifest_report_branch_mismatch(self):
        manifest = {
            "protocol": "OPS-1",
            "task_id": "batch-2",
            "objective": "",
            "writable_scope": ["cli/"],
            "branch": "feat/other-branch",
            "acceptance_criteria": [],
            "validation_commands": [],
            "forbidden_actions": [],
            "handoff_path": ".outrigger/handoffs/batch-2-hub-report.md",
        }
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.md"
            manifest_path = Path(temporary) / "manifest.json"
            report.write_text(hub_report(), encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(
                    [
                        "verify",
                        str(report),
                        "--manifest",
                        str(manifest_path),
                        "--no-git",
                    ]
                )
        self.assertEqual(code, 1)
        self.assertIn("branch", output.getvalue())

    @mock.patch("cli.outrigger._commit_exists", return_value=False)
    @mock.patch("cli.outrigger._run_git")
    def test_verify_rejects_unresolvable_head_sha(self, run_git, commit_exists):
        manifest = {
            "protocol": "OPS-1",
            "task_id": "batch-2",
            "objective": "",
            "writable_scope": ["cli/"],
            "branch": "feat/batch-2-engine-and-tests",
            "acceptance_criteria": [],
            "validation_commands": ["git diff --name-only base123 HEAD"],
            "forbidden_actions": [],
            "handoff_path": ".outrigger/handoffs/batch-2-hub-report.md",
        }
        run_git.return_value = "cli/"
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.md"
            manifest_path = Path(temporary) / "manifest.json"
            report.write_text(hub_report(), encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(
                    ["verify", str(report), "--manifest", str(manifest_path)]
                )
        self.assertEqual(code, 1)
        self.assertIn("HEAD_SHA", output.getvalue())


class LedgerTests(unittest.TestCase):
    def test_ledger_orders_batches_and_prints_next_expected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "batch-10-hub-report.md").write_text(
                hub_report(task_id="unit-ten", verdict="BLOCKED"),
                encoding="utf-8",
            )
            (directory / "batch-2-hub-report.md").write_text(
                hub_report(task_id="unit-two", verdict="PASS"),
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(["ledger", "--dir", str(directory)])
        rendered = output.getvalue()
        self.assertEqual(code, 0)
        self.assertLess(rendered.index("| 2 |"), rendered.index("| 10 |"))
        self.assertIn("| Batch | Unit | Agent | Status | Verdict |", rendered)
        self.assertIn("Next expected batch: 11", rendered)

    def test_empty_ledger_expects_batch_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(["ledger", "--dir", temporary])
        self.assertEqual(code, 0)
        self.assertIn("Next expected batch: 1", output.getvalue())

    def test_ledger_json_emits_structured_batches_and_next_expected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "batch-2-hub-report.md").write_text(
                hub_report(task_id="unit-two", verdict="PASS"),
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = outrigger.main(
                    ["ledger", "--dir", str(directory), "--json"]
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["next_expected_batch"], 3)
        self.assertEqual(len(payload["batches"]), 1)
        self.assertEqual(payload["batches"][0]["batch"], 2)
        self.assertEqual(payload["batches"][0]["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
