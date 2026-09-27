import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import importlib.util
if importlib.util.find_spec("mcp") is None:
    raise unittest.SkipTest("Optional MCP SDK is not installed; run make setup-mcp")

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

    def test_relocation_preserves_existing_file_directory_and_symlink(self):
        for kind in ("file", "directory", "symlink"):
            with self.subTest(kind=kind):
                folder = self.dir_path / kind
                folder.mkdir()
                src = folder / "input.jpg"
                src.touch()
                output = folder / ("input_images" if kind == "directory" else "input.png")
                if kind == "directory":
                    output.mkdir()
                    (output / "page.png").write_bytes(b"new")
                else:
                    output.write_bytes(b"new")
                destination = folder / "dest"
                destination.mkdir()
                existing = destination / output.name
                if kind == "directory":
                    existing.mkdir()
                    (existing / "keep.txt").write_bytes(b"old")
                elif kind == "symlink":
                    existing.symlink_to(folder / "missing.png")
                else:
                    existing.write_bytes(b"old")
                with patch("mcp_server.server.conv.process", return_value=[output]):
                    result = convergent_convert(str(src), "PNG", output_path=str(destination), overwrite=False)
                self.assertFalse(result["success"])
                self.assertIn("Destination already exists", result["error"])
                self.assertTrue(output.exists())
                if kind == "directory":
                    self.assertEqual((existing / "keep.txt").read_bytes(), b"old")
                elif kind == "symlink":
                    self.assertTrue(existing.is_symlink())
                else:
                    self.assertEqual(existing.read_bytes(), b"old")

    def test_explicit_output_filename_respects_overwrite(self):
        src = self.dir_path / "input.jpg"
        src.touch()
        output = src.with_suffix(".png")
        destination = self.dir_path / "chosen.png"
        destination.write_bytes(b"old")
        for overwrite in (False, True):
            output.write_bytes(b"new")
            with patch("mcp_server.server.conv.process", return_value=[output]):
                result = convergent_convert(str(src), "PNG", output_path=str(destination), overwrite=overwrite)
            self.assertEqual(result["success"], overwrite)
            self.assertEqual(destination.read_bytes(), b"new" if overwrite else b"old")

    def test_relocation_checks_all_conflicts_before_moving_any_output(self):
        src = self.dir_path / "input.jpg"
        src.touch()
        outputs = [self.dir_path / f"{name}.png" for name in ("a", "b")]
        for out in outputs:
            out.write_bytes(b"new")
        destination = self.dir_path / "dest"
        destination.mkdir()
        (destination / "b.png").write_bytes(b"old")
        with patch("mcp_server.server.conv.process", return_value=outputs):
            result = convergent_convert(str(src), "PNG", output_path=str(destination), overwrite=False)
        self.assertFalse(result["success"])
        self.assertTrue(all(out.exists() for out in outputs))
        self.assertFalse((destination / "a.png").exists())


    def test_no_overwrite_relocation_handles_new_conflict_after_preflight(self):
        from mcp_server.server import _relocate_output
        source = self.dir_path / "new.png"
        destination = self.dir_path / "existing.png"
        source.write_bytes(b"new")
        destination.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            _relocate_output(source, destination, overwrite=False)
        self.assertEqual(source.read_bytes(), b"new")
        self.assertEqual(destination.read_bytes(), b"keep")

    def test_no_overwrite_relocation_moves_file_and_directory_without_conflicts(self):
        from mcp_server.server import _relocate_output
        for is_directory in (False, True):
            source = self.dir_path / ("pages" if is_directory else "photo.png")
            if is_directory:
                source.mkdir()
                (source / "page.png").write_bytes(b"new")
            else:
                source.write_bytes(b"new")
            destination = self.dir_path / "dest" / source.name
            _relocate_output(source, destination, overwrite=False)
            self.assertFalse(source.exists())
            content = destination / "page.png" if is_directory else destination
            self.assertEqual(content.read_bytes(), b"new")


import asyncio
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from mcp import StdioServerParameters


class TestMCPAsyncSession(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_client_session_stdio(self):
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(PROJECT_ROOT / "mcp_server" / "server.py")],
            env=None
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # 1. Bounded Initialize
                init_res = await asyncio.wait_for(session.initialize(), timeout=5.0)
                self.assertEqual(init_res.serverInfo.name, "Convergent")

                # 2. Bounded list_tools
                tools_res = await asyncio.wait_for(session.list_tools(), timeout=5.0)
                tool_names = [t.name for t in tools_res.tools]
                self.assertIn("convergent_convert", tool_names)
                self.assertIn("list_supported_formats", tool_names)
                self.assertIn("pdf_to_images", tool_names)
                self.assertIn("perform_ocr", tool_names)
                self.assertIn("perform_stt", tool_names)

                # 3. Bounded call_tool
                call_res = await asyncio.wait_for(session.call_tool("list_supported_formats", {}), timeout=5.0)
                self.assertFalse(call_res.isError)


if __name__ == "__main__":
    unittest.main()
