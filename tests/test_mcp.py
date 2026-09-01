import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server.server import (
    list_supported_formats,
    convergent_convert,
    pdf_to_images,
    extract_audio,
    perform_ocr,
    perform_stt,
    combine_files,
    split_file,
)


class TestMCPServer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_list_supported_formats(self):
        res = list_supported_formats()
        self.assertIn("source_formats", res)
        self.assertIn("categories", res)
        self.assertIn("format_mapping", res)
        self.assertIn("JPG", res["source_formats"])
        self.assertIn("PNG", res["format_mapping"]["JPG"])
        self.assertIn("2", res["categories"])  # Image category

    def test_convergent_convert_nonexistent_file(self):
        res = convergent_convert(
            input_path=str(self.dir_path / "nonexistent.jpg"),
            target_format="PNG",
        )
        self.assertFalse(res["success"])
        self.assertIn("Input path does not exist", res["error"])
        self.assertEqual(res["converted_files"], [])

    def test_convergent_convert_success_and_output_relocation(self):
        src_file = self.dir_path / "input.jpg"
        src_file.write_bytes(b"image")
        dest_dir = self.dir_path / "output_folder"

        # Mock conv.process to simulate generating an output file
        dummy_out = self.dir_path / "input.png"
        dummy_out.write_bytes(b"converted_png")

        with patch("mcp_server.server.conv.process") as mock_process:
            mock_process.return_value = [dummy_out]

            res = convergent_convert(
                input_path=str(src_file),
                target_format="PNG",
                output_path=str(dest_dir),
                overwrite=True,
            )

            self.assertTrue(res["success"])
            self.assertEqual(res["count"], 1)
            expected_dest_file = dest_dir / "input.png"
            self.assertTrue(expected_dest_file.exists())
            self.assertEqual(res["converted_files"], [str(expected_dest_file.resolve())])

    def test_pdf_to_images_missing_file(self):
        res = pdf_to_images(pdf_path=str(self.dir_path / "ghost.pdf"))
        self.assertFalse(res["success"])
        self.assertIn("File not found", res["error"])

    def test_extract_audio_missing_file(self):
        res = extract_audio(video_path=str(self.dir_path / "ghost.mp4"))
        self.assertFalse(res["success"])
        self.assertIn("File not found", res["error"])

    def test_perform_ocr_missing_file(self):
        res = perform_ocr(input_path=str(self.dir_path / "ghost.png"))
        self.assertFalse(res["success"])
        self.assertIn("File not found", res["error"])

    def test_perform_stt_missing_file(self):
        res = perform_stt(input_path=str(self.dir_path / "ghost.wav"))
        self.assertFalse(res["success"])
        self.assertIn("File not found", res["error"])

    def test_combine_files_empty_and_unsupported(self):
        # Empty list
        res = combine_files(file_paths=[])
        self.assertFalse(res["success"])
        self.assertIn("No valid existing files", res["error"])

        # Unsupported extension
        unsupported_file = self.dir_path / "data.xyz"
        unsupported_file.write_bytes(b"xyz")
        res2 = combine_files(file_paths=[str(unsupported_file)])
        self.assertFalse(res2["success"])
        self.assertIn("Unsupported file type", res2["error"])

    def test_split_file_missing_and_unsupported(self):
        # Missing file
        res = split_file(file_path=str(self.dir_path / "ghost.pdf"))
        self.assertFalse(res["success"])
        self.assertIn("File not found", res["error"])

        # Unsupported extension
        unsupported_file = self.dir_path / "data.xyz"
        unsupported_file.write_bytes(b"xyz")
        res2 = split_file(file_path=str(unsupported_file))
        self.assertFalse(res2["success"])
        self.assertIn("Unsupported file type", res2["error"])

    def test_console_stderr_mode_enabled(self):
        from customs.console import console
        self.assertEqual(console.file, sys.stderr)

    def test_stdout_cleanliness_during_conversion(self):
        import io
        from customs.console import console

        src_file = self.dir_path / "sample.txt"
        src_file.write_text("Hello MCP")

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("sys.stdout", stdout_buf):
            console.print("Diagnostic test message")
            res = convergent_convert(
                input_path=str(src_file),
                target_format="MD",
                overwrite=True,
            )

        self.assertEqual(stdout_buf.getvalue(), "", "sys.stdout must remain strictly clean for JSON-RPC messages!")

    def test_mcp_stdio_subprocess_handshake_and_tools(self):
        import subprocess
        import json

        server_script = PROJECT_ROOT / "mcp_server" / "server.py"
        proc = subprocess.Popen(
            [sys.executable, str(server_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            # 1. Initialize Handshake
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-suite", "version": "1.0"}
                }
            }
            proc.stdin.write(json.dumps(init_req) + "\n")
            proc.stdin.flush()

            init_line = proc.stdout.readline()
            self.assertTrue(init_line, "Expected JSON-RPC response on stdout")
            init_resp = json.loads(init_line)
            self.assertEqual(init_resp.get("id"), 1)
            self.assertIn("result", init_resp)
            self.assertEqual(init_resp["result"]["serverInfo"]["name"], "Convergent")

            # 2. Initialized Notification
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()

            # 3. tools/list Request
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n")
            proc.stdin.flush()

            tools_line = proc.stdout.readline()
            tools_resp = json.loads(tools_line)
            self.assertEqual(tools_resp.get("id"), 2)
            tool_names = [t["name"] for t in tools_resp["result"]["tools"]]
            self.assertIn("convergent_convert", tool_names)
            self.assertIn("list_supported_formats", tool_names)
            self.assertIn("pdf_to_images", tool_names)
            self.assertIn("perform_ocr", tool_names)
            self.assertIn("perform_stt", tool_names)

            # 4. tools/call Request
            call_req = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "list_supported_formats",
                    "arguments": {}
                }
            }
            proc.stdin.write(json.dumps(call_req) + "\n")
            proc.stdin.flush()

            call_line = proc.stdout.readline()
            call_resp = json.loads(call_line)
            self.assertEqual(call_resp.get("id"), 3)
            self.assertIn("result", call_resp)
        finally:
            if proc.stdin:
                proc.stdin.close()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            proc.terminate()
            proc.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
