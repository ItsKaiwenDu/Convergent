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
    compress_files,
    decompress_archive,
    resize_media,
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

    def test_finding_1_in_place_strip_metadata_copy_safeguard(self):
        from mcp_server.server import _relocate_output
        source = self.dir_path / "photo.jpg"
        source.write_bytes(b"original_photo_bytes")
        destination = self.dir_path / "output_photo.jpg"

        # When source is in original_inputs, it must be copied, never unlinked/moved
        _relocate_output(source, destination, overwrite=True, original_inputs={source.resolve()})
        self.assertTrue(source.exists(), "Source input file must NEVER be deleted when relocating!")
        self.assertEqual(source.read_bytes(), b"original_photo_bytes")
        self.assertEqual(destination.read_bytes(), b"original_photo_bytes")

    def test_finding_2_split_pdf_custom_output_dir_never_trashed(self):
        from modules import split
        custom_dir = self.dir_path / "my_custom_split_dir"
        custom_dir.mkdir()
        canary = custom_dir / "canary.txt"
        canary.write_text("preserve me")

        # split_pdf with user output_dir must never trash the user directory
        with patch("modules.split.send_to_trash") as mock_trash, \
             patch("modules.split.get_pdf_page_count", return_value=0):
            split.split_pdf("dummy.pdf", output_dir=str(custom_dir), interactive=False)
            # send_to_trash should not have been called with custom_dir
            for call_args in mock_trash.call_args_list:
                self.assertNotEqual(Path(call_args[0][0]).resolve(), custom_dir.resolve())
        self.assertTrue(canary.exists())

    def test_finding_3_caching_with_output_path(self):
        from customs.cache import CacheManager
        cache_mgr = CacheManager(db_path=self.dir_path / "test_cache.db")
        src_file = self.dir_path / "doc.md"
        src_file.write_text("# Test Document")
        out_dir = self.dir_path / "custom_out"
        out_dir.mkdir()
        expected_out = out_dir / "doc.pdf"
        expected_out.write_bytes(b"%PDF-1.4 dummy")

        params = {"target": "PDF", "fps": None, "bitrate": None, "md_pdf_mode": "formatted",
                  "strip_metadata": False, "ocr": False, "stt": False, "model": "base", "language": None, "dpi": None}
        cache_mgr.save(src_file, expected_out, params)

        # Cache check against out_dir must succeed
        is_valid, _ = cache_mgr.is_cached_valid(src_file, expected_out, params)
        self.assertTrue(is_valid, "Cache entry must be valid for output in custom out_dir")
        cache_mgr.close()

    def test_finding_4_convenience_tools_accept_output_path(self):
        import inspect
        for fn in (pdf_to_images, extract_audio, perform_ocr, perform_stt):
            sig = inspect.signature(fn)
            self.assertIn("output_path", sig.parameters, f"{fn.__name__} must accept output_path parameter!")

    def test_finding_5_error_diagnostics_returned(self):
        src_file = self.dir_path / "bad.txt"
        src_file.write_text("hello")
        res = convergent_convert(
            input_path=str(src_file),
            target_format="XYZ",
            overwrite=True,
        )
        self.assertFalse(res["success"])
        self.assertIn("error", res)
        self.assertNotIn("No matching files found", res["error"])

    def test_finding_6_partial_success_reported(self):
        src_dir = self.dir_path / "batch_dir"
        src_dir.mkdir()
        f1 = src_dir / "file1.txt"
        f1.write_text("valid file 1")
        f2 = src_dir / "file2.txt"
        f2.write_text("valid file 2")

        dummy_out = self.dir_path / "file1.pdf"
        dummy_out.write_bytes(b"pdf")

        def mock_process_side_effect(*args, **kwargs):
            failed = kwargs.get("failed_details")
            if failed is not None:
                failed.append({"file": str(f2), "name": f2.name, "error": "Simulated error on file2"})
            return [dummy_out]

        with patch("mcp_server.server.conv.process", side_effect=mock_process_side_effect):
            res = convergent_convert(
                input_path=str(src_dir),
                target_format="PDF",
                overwrite=True,
            )
            self.assertTrue(res["success"])
            self.assertTrue(res.get("partial_success"))
            self.assertEqual(len(res.get("failed_files", [])), 1)
            self.assertIn("file2.txt", res["failed_files"][0]["name"])

    def test_finding_7_combine_files_rejects_mixed_formats(self):
        p1 = self.dir_path / "document.pdf"
        p2 = self.dir_path / "video.mp4"
        p1.write_bytes(b"%PDF")
        p2.write_bytes(b"MP4")

        res = combine_files(file_paths=[str(p1), str(p2)])
        self.assertFalse(res["success"])
        self.assertIn("mismatched file types", res["error"])

    def test_finding_8_compress_and_decompress_tools(self):
        test_file = self.dir_path / "hello.txt"
        test_file.write_text("Hello MCP Archive")

        comp_res = compress_files(
            file_paths=[str(test_file)],
            output_name="test_archive.zip",
            output_dir=str(self.dir_path),
        )
        self.assertTrue(comp_res["success"])
        self.assertTrue(Path(comp_res["archive_path"]).exists())

        extract_dir = self.dir_path / "extracted_contents"
        decomp_res = decompress_archive(
            archive_path=comp_res["archive_path"],
            output_dir=str(extract_dir),
        )
        self.assertTrue(decomp_res["success"])
        self.assertTrue((extract_dir / "hello.txt").exists())
        self.assertEqual((extract_dir / "hello.txt").read_text(), "Hello MCP Archive")

    def test_finding_9_resize_media_tool(self):
        img_file = self.dir_path / "sample.png"
        img_file.write_bytes(b"dummy")

        with patch("modules.resize.resize_single_file", return_value=("sample.png", True, "", 0.05)):
            res = resize_media(
                file_path=str(img_file),
                scale_percent=50,
                output_path=str(self.dir_path / "scaled.png"),
            )
            self.assertTrue(res["success"])
            self.assertIn("scaled.png", res["output_file"])
            self.assertIn("duration_seconds", res)

    def test_finding_10_split_file_docx_docstring(self):
        self.assertIn("DOCX", split_file.__doc__)
        self.assertIn("PDF", split_file.__doc__)

    def test_finding_11_list_supported_formats_filters(self):
        # Category filter
        res_cat = list_supported_formats(category="image")
        self.assertEqual(res_cat["category"], "image")
        self.assertIn("JPG", res_cat["source_formats"])

        # Source format filter
        res_fmt = list_supported_formats(source_format="PNG")
        self.assertEqual(res_fmt["source_format"], "PNG")
        self.assertIn("JPG", res_fmt["target_formats"])

    def test_finding_12_preview_truncation(self):
        ocr_out = self.dir_path / "ocr_output.txt"
        ocr_out.write_text("A" * 1200)

        with patch("mcp_server.server.convergent_convert") as mock_conv:
            mock_conv.return_value = {
                "success": True,
                "count": 1,
                "converted_files": [str(ocr_out)],
                "target_format": "TXT",
            }
            res = perform_ocr(input_path=str(ocr_out), preview_length=200)
            self.assertEqual(res["total_characters"], 1200)
            self.assertIn("truncated, 1200 total characters", res["extracted_text_preview"])
            self.assertTrue(len(res["extracted_text_preview"]) < 300)

    def test_finding_13_stt_model_fallback_warning(self):
        with patch("mcp_server.server.convergent_convert", return_value={"success": True, "converted_files": []}):
            dummy_audio = self.dir_path / "audio.mp3"
            dummy_audio.touch()
            res = perform_stt(input_path=str(dummy_audio), model="custom-gpt-whisper-unknown")
            self.assertEqual(res.get("model_used"), "base")
            self.assertIn("warning", res)
            self.assertIn("Falling back to 'base'", res["warning"])


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
                self.assertIn("compress_files", tool_names)
                self.assertIn("decompress_archive", tool_names)
                self.assertIn("resize_media", tool_names)

                # 3. Bounded call_tool
                call_res = await asyncio.wait_for(session.call_tool("list_supported_formats", {}), timeout=5.0)
                self.assertFalse(call_res.isError)


if __name__ == "__main__":
    unittest.main()
