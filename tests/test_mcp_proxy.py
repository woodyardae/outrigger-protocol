"""
Outrigger Protocol v0.3.0 - MCP Stdio Proxy Verification Suite
Author: Alan Woodyard (https://alanwoodyard.com)
Zero external dependencies - 100% Python stdlib unittest.
"""

import os
import sys
import json
import unittest
import tempfile
import shutil
import subprocess
from pathlib import Path

# Ensure src/ is on PYTHONPATH so subprocess invocations of -m outrigger_protocol.cli succeed
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
_EXISTING_PP = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = f"{_SRC_DIR}{os.pathsep}{_EXISTING_PP}" if _EXISTING_PP else _SRC_DIR

MOCK_MCP_SERVER_CODE = """
import sys
import json

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    method = msg.get("method")
    msg_id = msg.get("id")
    if method == "initialize":
        res = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mock-mcp-server", "version": "1.0.0"}
            }
        }
        sys.stdout.write(json.dumps(res) + "\\n")
        sys.stdout.flush()
    elif method == "tools/list":
        res = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "write_file",
                        "description": "Write a file",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "content": {"type": "string"}
                            }
                        }
                    }
                ]
            }
        }
        sys.stdout.write(json.dumps(res) + "\\n")
        sys.stdout.flush()
    elif method == "tools/call":
        res = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": "executed_ok"}]
            }
        }
        sys.stdout.write(json.dumps(res) + "\\n")
        sys.stdout.flush()
"""

class TestMcpStdioProxy(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="outrigger_proxy_test_")
        self.scope_dir = Path(self.test_dir) / "scope"
        self.scope_dir.mkdir(parents=True, exist_ok=True)
        self.outside_dir = Path(self.test_dir) / "outside"
        self.outside_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _send_frames(self, frames: list[dict], scope: Path) -> list[dict]:
        cmd = [
            sys.executable, "-m", "outrigger_protocol.cli", "proxy",
            "--scope", str(scope),
            "--", sys.executable, "-c", MOCK_MCP_SERVER_CODE
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )

        input_payload = "\n".join(json.dumps(f) for f in frames) + "\n"
        stdout, _ = proc.communicate(input=input_payload, timeout=5)

        responses = []
        for line in stdout.splitlines():
            line_str = line.strip()
            if line_str:
                try:
                    responses.append(json.loads(line_str))
                except json.JSONDecodeError:
                    pass
        return responses

    def test_proxy_passthrough_initialize_and_tools_list(self):
        frames = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        ]
        responses = self._send_frames(frames, self.scope_dir)
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[0]["id"], 1)
        self.assertIn("serverInfo", responses[0]["result"])
        self.assertEqual(responses[1]["id"], 2)
        self.assertIn("tools", responses[1]["result"])

    def test_proxy_allows_in_scope_tool_call(self):
        target_path = self.scope_dir / "valid_file.txt"
        frame = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "path": str(target_path),
                    "content": "Clean in-scope content"
                }
            }
        }
        responses = self._send_frames([frame], self.scope_dir)
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 10)
        self.assertNotIn("error", responses[0])
        self.assertEqual(responses[0]["result"]["content"][0]["text"], "executed_ok")

    def test_proxy_blocks_dotdot_traversal_with_32602(self):
        frame = {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "path": "../outside.txt",
                    "content": "Drift attempt"
                }
            }
        }
        responses = self._send_frames([frame], self.scope_dir)
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 20)
        self.assertIn("error", responses[0])
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertIn("Outrigger Boundary Violation", responses[0]["error"]["message"])

    def test_proxy_blocks_urlencoded_traversal(self):
        frame_single = {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "path": "%2e%2e%2foutside.txt",
                    "content": "Single urlencode traversal"
                }
            }
        }
        frame_double = {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "path": "%252e%252e%252foutside.txt",
                    "content": "Double urlencode traversal"
                }
            }
        }
        responses = self._send_frames([frame_single, frame_double], self.scope_dir)
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[0]["id"], 30)
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertEqual(responses[1]["id"], 31)
        self.assertEqual(responses[1]["error"]["code"], -32602)

    def test_proxy_blocks_null_byte_injection(self):
        frame_null_raw = {
            "jsonrpc": "2.0",
            "id": 40,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "path": "file\x00escape.txt",
                    "content": "Raw null byte"
                }
            }
        }
        frame_null_encoded = {
            "jsonrpc": "2.0",
            "id": 41,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "path": "file%00escape.txt",
                    "content": "Encoded null byte"
                }
            }
        }
        responses = self._send_frames([frame_null_raw, frame_null_encoded], self.scope_dir)
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[0]["id"], 40)
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertEqual(responses[1]["id"], 41)
        self.assertEqual(responses[1]["error"]["code"], -32602)

    def test_proxy_blocks_out_of_scope_symlink(self):
        secret_file = self.outside_dir / "secret.txt"
        secret_file.write_text("classified_token", encoding="utf-8")
        symlink_path = self.scope_dir / "leak_symlink"
        try:
            symlink_path.symlink_to(secret_file)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not supported without admin privileges on this host.")

        frame = {
            "jsonrpc": "2.0",
            "id": 50,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "path": str(symlink_path),
                    "content": "Symlink traversal"
                }
            }
        }
        responses = self._send_frames([frame], self.scope_dir)
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 50)
        self.assertIn("error", responses[0])
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertIn("Outrigger Boundary Violation", responses[0]["error"]["message"])

    def test_proxy_blocks_in_flight_secret_payload(self):
        target_path = self.scope_dir / "secret_target.txt"
        frame = {
            "jsonrpc": "2.0",
            "id": 60,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "path": str(target_path),
                    "content": "In-flight token leak: ghp_mocktoken0000000000000000000000000000"
                }
            }
        }
        responses = self._send_frames([frame], self.scope_dir)
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 60)
        self.assertIn("error", responses[0])
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertIn("Outrigger Boundary Violation", responses[0]["error"]["message"])

if __name__ == "__main__":
    unittest.main()
