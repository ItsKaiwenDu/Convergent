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
    convert,
    pdf_to_images,
    extract_audio,
    ocr,
    stt,
    combine,
    split,
    compress,
    decompress,
    resize,
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
        self.assertNotIn("dependencies", res)
        self.assertIn("JPG", res["source_formats"])
        jpg_group_targets = next(
            targets for key, targets in res["format_mapping"].items() if "JPG" in key.split(",")
        )
        self.assertIn("PNG", jpg_group_targets)
        self.assertLess(len(res["format_mapping"]), len(res["source_formats"]))
        self.assertIn("image", res["categories"])
        self.assertNotIn("2", res["categories"])

    def test_convergent_convert_nonexistent_file(self):
        res = convert(
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

            res = convert(
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
        res = ocr(input_path=str(self.dir_path / "ghost.png"))
        self.assertFalse(res["success"])
        self.assertIn("File not found", res["error"])

    def test_perform_stt_missing_file(self):
        res = stt(input_path=str(self.dir_path / "ghost.wav"))
        self.assertFalse(res["success"])
        self.assertIn("File not found", res["error"])

    def test_combine_files_empty_and_unsupported(self):
        # Empty list
        res = combine(file_paths=[])
        self.assertFalse(res["success"])
        self.assertIn("No valid existing files", res["error"])

        # Unsupported extension
        unsupported_file = self.dir_path / "data.xyz"
        unsupported_file.write_bytes(b"xyz")
        res2 = combine(file_paths=[str(unsupported_file)])
        self.assertFalse(res2["success"])
        self.assertIn("Unsupported file type", res2["error"])

    def test_split_file_missing_and_unsupported(self):
        # Missing file
        res = split(file_path=str(self.dir_path / "ghost.pdf"))
        self.assertFalse(res["success"])
        self.assertIn("File not found", res["error"])

        # Unsupported extension
        unsupported_file = self.dir_path / "data.xyz"
        unsupported_file.write_bytes(b"xyz")
        res2 = split(file_path=str(unsupported_file))
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
            res = convert(
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
                    result = convert(str(src), "PNG", output_path=str(destination), overwrite=False)
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
                result = convert(str(src), "PNG", output_path=str(destination), overwrite=overwrite)
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
            result = convert(str(src), "PNG", output_path=str(destination), overwrite=False)
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

        # split_pdf with user output_dir must never trash user directory
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
        for fn in (pdf_to_images, extract_audio, ocr, stt):
            sig = inspect.signature(fn)
            self.assertIn("output_path", sig.parameters, f"{fn.__name__} must accept output_path parameter!")

    def test_finding_5_error_diagnostics_returned(self):
        src_file = self.dir_path / "bad.txt"
        src_file.write_text("hello")
        res = convert(
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
            res = convert(
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

        res = combine(file_paths=[str(p1), str(p2)])
        self.assertFalse(res["success"])
        self.assertIn("mismatched file types", res["error"])

    def test_finding_8_compress_and_decompress_tools(self):
        test_file = self.dir_path / "hello.txt"
        test_file.write_text("Hello MCP Archive")

        comp_res = compress(
            file_paths=[str(test_file)],
            output_name="test_archive.zip",
            output_dir=str(self.dir_path),
        )
        self.assertTrue(comp_res["success"])
        self.assertTrue(Path(comp_res["archive_path"]).exists())

        extract_dir = self.dir_path / "extracted_contents"
        decomp_res = decompress(
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
            res = resize(
                file_path=str(img_file),
                scale_percent=50,
                output_path=str(self.dir_path / "scaled.png"),
            )
            self.assertTrue(res["success"])
            self.assertIn("scaled.png", res["output_file"])
            self.assertIn("duration_seconds", res)

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

        with patch("mcp_server.server.convert") as mock_conv:
            mock_conv.return_value = {
                "success": True,
                "count": 1,
                "converted_files": [str(ocr_out)],
                "target_format": "TXT",
            }
            res = ocr(input_path=str(ocr_out), preview_length=200)
            self.assertEqual(res["total_characters"], 1200)
            self.assertIn("truncated, 1200 total characters", res["extracted_text_preview"])
            self.assertTrue(len(res["extracted_text_preview"]) < 300)

    def test_finding_13_stt_model_fallback_warning(self):
        with patch("mcp_server.server.convert", return_value={"success": True, "converted_files": []}):
            dummy_audio = self.dir_path / "audio.mp3"
            dummy_audio.touch()
            res = stt(input_path=str(dummy_audio), model="custom-gpt-whisper-unknown")
            self.assertEqual(res.get("model_used"), "base")
            self.assertIn("warning", res)
            self.assertIn("Falling back to 'base'", res["warning"])

    def test_ghostscript_uses_dsafer(self):
        from modules import pdf_manip
        dummy_pdf = self.dir_path / "test.pdf"
        dummy_pdf.touch()

        def fake_gs(cmd, **kwargs):
            for a in cmd:
                if a.startswith("-sOUTPUTFILE="):
                    p_str = a.split("=", 1)[1].replace("%03d", "001")
                    p = Path(p_str)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.touch()
            return True, ""

        with patch("modules.pdf_manip.run_command", side_effect=fake_gs) as mock_cmd:
            success, err = pdf_manip.convert_pdf_to_image(str(dummy_pdf), "jpg", output_dir=str(self.dir_path / "out"))
            self.assertTrue(success)
            cmd_args = mock_cmd.call_args[0][0]
            self.assertIn("-dSAFER", cmd_args)
            self.assertNotIn("-dNOSAFER", cmd_args)
            permit_read = [a for a in cmd_args if a.startswith("--permit-file-read=")]
            self.assertTrue(len(permit_read) > 0)

    def test_stt_whisper_timestamp_flags_and_turbo_alias(self):
        from modules.stt import normalize_model_name
        self.assertEqual(normalize_model_name("large-v3-turbo"), "turbo")
        self.assertEqual(normalize_model_name("large-turbo"), "turbo")

        with patch("mcp_server.server.convert", return_value={"success": True, "converted_files": []}):
            dummy_audio = self.dir_path / "audio.mp3"
            dummy_audio.touch()
            res = stt(input_path=str(dummy_audio), model="large-v3-turbo")
            self.assertEqual(res.get("model_used"), "turbo")
            self.assertEqual(res.get("model_requested"), "large-v3-turbo")
            self.assertNotIn("warning", res)

    def test_combine_apostrophe_escaping(self):
        import modules.combine as combine_mod
        f1 = self.dir_path / "speaker's recording.wav"
        f1.touch()
        f2 = self.dir_path / "normal.wav"
        f2.touch()

        with patch("modules.combine.run_command", return_value=(True, "")) as mock_cmd, \
             patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            combine_mod.combine_audios([str(f1), str(f2)], output_path=str(self.dir_path / "out.wav"), interactive=False)
            written_lines = [call[0][0] for call in mock_file().write.call_args_list if call[0]]
            # Ensure apostrophe in filename is escaped as '\'''
            escaped_found = any("'\\'''" in line or "\\'" in line for line in written_lines)
            self.assertTrue(escaped_found)

    def test_perform_ocr_docx_no_binary_preview(self):
        docx_file = self.dir_path / "output.docx"
        docx_file.write_bytes(b"PK\x03\x04\x14\x00fake_zip_binary")
        with patch("mcp_server.server.convert") as mock_conv:
            mock_conv.return_value = {
                "success": True,
                "count": 1,
                "converted_files": [str(docx_file)],
                "target_format": "DOCX",
            }
            res = ocr(input_path=str(docx_file), target_format="DOCX")
            self.assertIsNone(res.get("total_characters"))
            self.assertEqual(res.get("extracted_text_preview"), "[Text extracted and saved to DOCX document]")

    def test_resize_media_width_only(self):
        with patch("modules.resize.resize_single_file", return_value=("test.jpg", True, "", 0.05)) as mock_resize:
            dummy_img = self.dir_path / "img.jpg"
            dummy_img.touch()
            res = resize(file_path=str(dummy_img), width=300)
            self.assertTrue(res["success"])
            self.assertEqual(mock_resize.call_args[1]["method"], "w")
            self.assertEqual(mock_resize.call_args[1]["scale_val"], 300)

    def test_extract_audio_validation(self):
        dummy_video = self.dir_path / "video.mp4"
        dummy_video.touch()

        # Reject GIF or invalid non-audio formats
        res_gif = extract_audio(video_path=str(dummy_video), target_format="GIF")
        self.assertFalse(res_gif["success"])
        self.assertIn("Invalid audio target format", res_gif["error"])

        # Allow valid AAC audio format
        with patch("mcp_server.server.convert", return_value={"success": True, "converted_files": ["video.aac"]}):
            res_aac = extract_audio(video_path=str(dummy_video), target_format="AAC")
            self.assertTrue(res_aac["success"])

    def test_list_supported_formats_category_5_and_alias(self):
        # Category "5" (Document)
        res_cat5 = list_supported_formats(category="5")
        self.assertEqual(res_cat5.get("category"), "document")
        self.assertIn("PDF", res_cat5.get("source_formats", []))

        # Alias lookup for jpeg
        res_jpeg = list_supported_formats(source_format="jpeg")
        self.assertEqual(res_jpeg.get("source_format"), "JPG")
        self.assertIn("PNG", res_jpeg.get("target_formats", []))

        # Verify RAW and HEIF in image category
        res_img = list_supported_formats(category="image")
        self.assertIn("ARW", res_img.get("source_formats", []))
        self.assertIn("DNG", res_img.get("source_formats", []))
        self.assertIn("HEIF", res_img.get("source_formats", []))

    def test_process_single_file_staging_prevents_sibling_clobbering(self):
        from customs.file_process import process_single_file
        from Convergent import Converter
        conv = Converter()
        
        src_dir = self.dir_path / "src"
        src_dir.mkdir()
        out_dir = self.dir_path / "out"
        out_dir.mkdir()
        
        # Source file to convert
        src_file = src_dir / "photo.jpg"
        src_file.write_bytes(b"original jpg content")
        
        # Sibling file in source directory that happens to share target name
        sibling_file = src_dir / "photo.png"
        sibling_file.write_bytes(b"precious sibling content")
        
        # Mock handler on conv to simulate creating output file next to input
        def mock_convert_image(source, target_ext, **kwargs):
            out_p = source.with_suffix(f".{target_ext.lower()}")
            out_p.write_bytes(b"converted png data")
            return True, ""
            
        with patch.object(conv, "convert_image", side_effect=mock_convert_image):
            name, success, err, dur = process_single_file(
                conv, src_file, "PNG", output_dir=out_dir
            )
            self.assertTrue(success)
            
            # Sibling file in src_dir MUST remain untouched
            self.assertTrue(sibling_file.exists())
            self.assertEqual(sibling_file.read_bytes(), b"precious sibling content")
            
            # Output file in out_dir must be created
            dest_file = out_dir / "photo.png"
            self.assertTrue(dest_file.exists())
            self.assertEqual(dest_file.read_bytes(), b"converted png data")

    def test_pdf_to_images_natural_sorting_and_truncation(self):
        # Create 60 dummy page images
        doc_pdf = self.dir_path / "doc.pdf"
        doc_pdf.touch()
        img_dir = self.dir_path / "doc_images"
        img_dir.mkdir()
        created_paths = []
        page_indices = list(range(1, 61))
        for idx in page_indices:
            p = img_dir / f"page_{idx}.jpg"
            p.touch()
            created_paths.append(str(p))

        with patch("mcp_server.server.convert") as mock_conv:
            mock_conv.return_value = {
                "success": True,
                "count": len(created_paths),
                "converted_files": [str(img_dir)],
                "target_format": "JPG",
            }
            res = pdf_to_images(pdf_path=str(doc_pdf))
            self.assertTrue(res["success"])
            self.assertEqual(res["count"], 60)
            self.assertTrue(res["truncated"])
            self.assertEqual(len(res["images"]), 10)
            # Verify natural sorting (page_2 comes before page_10)
            self.assertTrue(res["images"][0].endswith("page_1.jpg"))
            self.assertTrue(res["images"][1].endswith("page_2.jpg"))
            self.assertTrue(res["images"][9].endswith("page_10.jpg"))

    def test_split_file_auto_mode_and_truncation(self):
        # 1. Video auto-mode -> interval
        dummy_video = self.dir_path / "clip.mp4"
        dummy_video.touch()
        with patch("mcp_server.server.conv.split_video", return_value=str(self.dir_path / "split_out")) as mock_split_vid:
            (self.dir_path / "split_out").mkdir(exist_ok=True)
            res = split(file_path=str(dummy_video))
            self.assertEqual(mock_split_vid.call_args[1]["mode"], "interval")

        # 2. PDF auto-mode -> pages
        dummy_pdf = self.dir_path / "doc.pdf"
        dummy_pdf.touch()
        with patch("mcp_server.server.conv.split_pdf", return_value=str(self.dir_path / "split_out")) as mock_split_pdf:
            res = split(file_path=str(dummy_pdf))
            self.assertEqual(mock_split_pdf.call_args[1]["mode"], "pages")

    def test_combine_mixed_audio_filter_complex(self):
        import modules.combine as combine_mod
        f1 = self.dir_path / "track1.wav"
        f1.touch()
        f2 = self.dir_path / "track2.flac"
        f2.touch()

        with patch("modules.combine.run_command", return_value=(True, "")) as mock_cmd:
            combine_mod.combine_audios([str(f1), str(f2)], output_path=str(self.dir_path / "combined.mp3"), interactive=False)
            self.assertTrue(mock_cmd.called)
            cmd_args = mock_cmd.call_args[0][0]
            # Must use filter_complex concat instead of demuxer -c copy
            self.assertIn("-filter_complex", cmd_args)
            self.assertIn("[0:a][1:a]concat=n=2:v=0:a=1[outa]", cmd_args)
            self.assertNotIn("-c", cmd_args)

    def test_cache_custom_output_path_relocation_and_hit(self):
        dummy_src = self.dir_path / "source.jpg"
        dummy_src.write_bytes(b"test jpg source binary")
        custom_out = self.dir_path / "custom_named.png"
        test_db = self.dir_path / "test_cache.sqlite"
        
        with patch("customs.cache.CACHE_DB_PATH", test_db):
            # First call: converts and relocates
            with patch("mcp_server.server.conv.process") as mock_proc:
                def fake_proc(*args, **kwargs):
                    default_file = self.dir_path / "source.png"
                    default_file.write_bytes(b"generated png data")
                    return [default_file]
                mock_proc.side_effect = fake_proc

                res1 = convert(
                    input_path=str(dummy_src),
                    target_format="PNG",
                    output_path=str(custom_out),
                )
                self.assertTrue(res1["success"])
                self.assertTrue(custom_out.exists())
                self.assertEqual(custom_out.read_bytes(), b"generated png data")

            # Second call: hits cache directly without calling conv.process
            with patch("mcp_server.server.conv.process") as mock_proc2:
                res2 = convert(
                    input_path=str(dummy_src),
                    target_format="PNG",
                    output_path=str(custom_out),
                )
                self.assertTrue(res2["success"])
                self.assertEqual(
                    [str(Path(p).resolve()) for p in res2["converted_files"]],
                    [str(custom_out.resolve())]
                )
                # conv.process should NOT have been called because cache hit directly!
                self.assertFalse(mock_proc2.called)

    def test_ocr_tesseract_and_gs_use_resolved_paths(self):
        from modules import ocr

        real_dir = self.dir_path / "real_dir"
        real_dir.mkdir()
        link_dir = self.dir_path / "link_dir"
        link_dir.symlink_to(real_dir)

        img = link_dir / "scan.png"
        img.write_bytes(b"fake png")

        with patch("modules.ocr.shutil.which", side_effect=lambda cmd: "/usr/bin/tesseract" if cmd == "tesseract" else None), \
             patch("modules.ocr.run_command_output", return_value=(0, "hello", "")) as mock_cmd:
            text = ocr._ocr_tesseract(img)
            self.assertEqual(text, "hello")
            called_args = mock_cmd.call_args[0][0]
            self.assertEqual(called_args[1], str(img.resolve()))

        pdf_file = link_dir / "doc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")
        temp_sub = real_dir / "gs_tmp"
        temp_sub.mkdir()
        temp_link = link_dir / "gs_tmp_link"
        temp_link.symlink_to(temp_sub)

        def fake_gs(cmd, *args, **kwargs):
            (temp_sub / "page_0001.png").write_bytes(b"png")
            return True, ""

        with patch("modules.ocr.tempfile.mkdtemp", return_value=str(temp_link)), \
             patch("modules.ocr.shutil.which", side_effect=lambda cmd: "/usr/bin/gs" if cmd == "gs" else None), \
             patch("modules.ocr.run_command", side_effect=fake_gs) as mock_gs:
            _, pngs = ocr._convert_pdf_to_temp_images(pdf_file)
            self.assertEqual(len(pngs), 1)
            gs_cmd = mock_gs.call_args[0][0]
            resolved_tmp = str(temp_link.resolve())
            self.assertIn(f"--permit-file-write={resolved_tmp}/*", gs_cmd)
            self.assertIn(f"-sOUTPUTFILE={resolved_tmp}/page_%04d.png", gs_cmd)

    def test_sips_zero_byte_skipped_output_reports_failure(self):
        from modules import image

        empty_jpg = self.dir_path / "empty.jpg"
        empty_jpg.write_bytes(b"")

        with patch("modules.image.sys.platform", "darwin"), \
             patch("modules.image.shutil.which", side_effect=lambda cmd: "/usr/bin/sips" if cmd == "sips" else None), \
             patch("modules.image.run_command", return_value=(True, "")):
            ok, err = image.convert_image(empty_jpg, "PNG")
            self.assertFalse(ok)
            self.assertTrue(len(err) > 0)

            empty_heic = self.dir_path / "empty.heic"
            empty_heic.write_bytes(b"")
            ok_heic, err_heic = image.convert_heic(empty_heic, "JPG")
            self.assertFalse(ok_heic)
            self.assertTrue(len(err_heic) > 0)

    def test_convergent_convert_cache_respects_overwrite_false(self):
        test_db = self.dir_path / "test_cache_overwrite.sqlite"
        src = self.dir_path / "source.txt"
        src.write_text("hello cache overwrite", encoding="utf-8")
        custom_out = self.dir_path / "out.md"

        with patch("customs.cache.CACHE_DB_PATH", test_db):
            with patch("mcp_server.server.conv.process") as mock_proc:
                def fake_proc(*args, **kwargs):
                    default_file = self.dir_path / "source.md"
                    default_file.write_text("converted md", encoding="utf-8")
                    return [default_file]
                mock_proc.side_effect = fake_proc

                res1 = convert(
                    input_path=str(src),
                    target_format="MD",
                    output_path=str(custom_out),
                    overwrite=True,
                    use_cache=True,
                )
                self.assertTrue(res1["success"])
                self.assertTrue(custom_out.exists())

            # Calling again with overwrite=False must NOT bypass the check via cache
            res2 = convert(
                input_path=str(src),
                target_format="MD",
                output_path=str(custom_out),
                overwrite=False,
                use_cache=True,
            )
            self.assertFalse(res2["success"])
            self.assertIn("Destination already exists", res2["error"])

    def test_combine_files_rejects_non_pdf_output_for_pdf_docx_pptx(self):
        d1 = self.dir_path / "a.docx"
        d2 = self.dir_path / "b.docx"
        d1.write_bytes(b"docx1")
        d2.write_bytes(b"docx2")
        res_docx = combine(file_paths=[str(d1), str(d2)], output_path=str(self.dir_path / "merged.docx"))
        self.assertFalse(res_docx["success"])
        self.assertIn(".pdf", res_docx["error"])

        p1 = self.dir_path / "a.pptx"
        p2 = self.dir_path / "b.pptx"
        p1.write_bytes(b"pptx1")
        p2.write_bytes(b"pptx2")
        res_pptx = combine(file_paths=[str(p1), str(p2)], output_path=str(self.dir_path / "merged.pptx"))
        self.assertFalse(res_pptx["success"])
        self.assertIn(".pdf", res_pptx["error"])

        pdf1 = self.dir_path / "a.pdf"
        pdf2 = self.dir_path / "b.pdf"
        pdf1.write_bytes(b"%PDF-1.4\n")
        pdf2.write_bytes(b"%PDF-1.4\n")
        res_noext = combine(file_paths=[str(pdf1), str(pdf2)], output_path=str(self.dir_path / "merged"))
        self.assertFalse(res_noext["success"])
        self.assertIn(".pdf", res_noext["error"])

    def test_resize_media_validation_and_extensions(self):
        img = self.dir_path / "photo.jpg"
        img.write_bytes(b"jpg")
        pdf = self.dir_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        txt = self.dir_path / "note.txt"
        txt.write_text("hello", encoding="utf-8")
        svg = self.dir_path / "icon.svg"
        svg.write_text("<svg/>", encoding="utf-8")
        mp3 = self.dir_path / "audio.mp3"
        mp3.write_bytes(b"mp3")

        # 1. Reject internal CLI code aspect_ratio="5"
        res_ar5 = resize(file_path=str(img), width=100, aspect_ratio="5")
        self.assertFalse(res_ar5["success"])
        self.assertIn("aspect ratio", res_ar5["error"].lower())

        # 2. Reject invalid fps (<= 0, bool, non-numeric)
        for bad_fps in (0, -24, True, "30"):
            vid = self.dir_path / "clip.mp4"
            vid.write_bytes(b"mp4")
            res_fps = resize(file_path=str(vid), fps=bad_fps)
            self.assertFalse(res_fps["success"], f"Expected failure for fps={bad_fps!r}")
            self.assertIn("fps", res_fps["error"].lower())

        # 3. Reject fps on non-video files
        for non_vid in (img, pdf):
            res_nonvid_fps = resize(file_path=str(non_vid), width=100, fps=30)
            self.assertFalse(res_nonvid_fps["success"])
            self.assertIn("video", res_nonvid_fps["error"].lower())

        # 4. Reject pure no-op calls
        res_noop = resize(file_path=str(img))
        self.assertFalse(res_noop["success"])
        self.assertIn("no operation", res_noop["error"].lower())

        # 5. Reject unsupported extensions with explicit error
        for bad_file in (txt, svg, mp3):
            res_unsup = resize(file_path=str(bad_file), width=100)
            self.assertFalse(res_unsup["success"])
            self.assertIn("unsupported file format", res_unsup["error"].lower())

        # 6. Accept expanded video extensions (.avi, .mkv, .webm)
        for ext in (".avi", ".mkv", ".webm"):
            v = self.dir_path / f"sample{ext}"
            v.write_bytes(b"video")
            with patch("modules.resize.resize_single_file", return_value=(v.name, True, "", 0.05)):
                res_v = resize(file_path=str(v), fps=24)
                self.assertTrue(res_v["success"], f"Expected success for {ext}: {res_v}")

        # 7. Verify resize_single_file falls back to libx264 for .avi when get_video_encoder returns None
        from modules import resize as resize_mod
        avi = self.dir_path / "fallback.avi"
        avi.write_bytes(b"avi")
        captured_cmds = []

        def fake_run_command(cmd):
            captured_cmds.append(cmd)
            Path(cmd[-1]).write_bytes(b"resized")
            return True, ""

        with patch("modules.resize.get_video_dimensions", return_value=(640, 480)), \
             patch("modules.resize.get_video_encoder", return_value=(None, [], "")), \
             patch("modules.resize.run_command", side_effect=fake_run_command):
            _, ok, err, _ = resize_mod.resize_single_file(avi, "w", 320, "5")
            self.assertTrue(ok, err)
            self.assertIn("libx264", captured_cmds[0])

    def test_convert_image_exif_auto_orient_with_sips(self):
        from modules import image

        src_jpg = self.dir_path / "rotated.jpg"
        src_jpg.write_bytes(b"fake jpg")
        expected_png = self.dir_path / "rotated.png"

        cmds_sips = []

        def fake_run_sips(cmd):
            cmds_sips.append(cmd)
            expected_png.write_bytes(b"png")
            return True, ""

        mock_proc = MagicMock()
        mock_proc.stdout = "  orientation: 6\n"
        with patch("modules.image.sys.platform", "darwin"), \
             patch("modules.image.shutil.which", side_effect=lambda c: "/usr/bin/sips" if c == "sips" else None), \
             patch("modules.image.subprocess.run", return_value=mock_proc), \
             patch("modules.image.run_command", side_effect=fake_run_sips):
            ok, err = image.convert_image(src_jpg, "PNG", strip_metadata=False)
            self.assertTrue(ok, err)
            self.assertEqual(cmds_sips[0][0], "sips")
            self.assertIn("-r", cmds_sips[0])
            self.assertIn("90", cmds_sips[0])
            self.assertIn("orientation", cmds_sips[0])

    def test_convergent_convert_manifest_in_new_output_dir_and_deterministic(self):
        in_dir = self.dir_path / "batch_in"
        in_dir.mkdir()
        for i in range(28):
            (in_dir / f"f_{i:02d}.txt").write_text(f"hello {i}", encoding="utf-8")

        new_out_dir = self.dir_path / "brand_new_out"
        self.assertFalse(new_out_dir.exists())

        def fake_process(**kwargs):
            out_dir = Path(kwargs["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            out_files = []
            for i in range(28):
                p = out_dir / f"f_{i:02d}.md"
                p.write_text(f"# hello {i}", encoding="utf-8")
                out_files.append(str(p))
            return out_files

        with patch("mcp_server.server.conv.process", side_effect=fake_process):
            res1 = convert(input_path=str(in_dir), target_format="MD", output_path=str(new_out_dir), use_cache=False)
            self.assertTrue(res1["success"])
            self.assertTrue(res1["truncated"])
            manifest1 = Path(res1["manifest_path"])
            self.assertEqual(manifest1.parent, new_out_dir.resolve())
            self.assertEqual(manifest1.name, ".convergent_manifest_converted.json")
            self.assertTrue(manifest1.exists())

            # Repeat run overwrites same deterministic manifest instead of creating multiple files
            res2 = convert(input_path=str(in_dir), target_format="MD", output_path=str(new_out_dir), use_cache=False)
            self.assertEqual(res2["manifest_path"], res1["manifest_path"])
            manifests = list(new_out_dir.glob(".convergent_manifest_converted*.json"))
            self.assertEqual(len(manifests), 1)

    def test_pdf_to_images_overwrite_false_and_file_output_path(self):
        doc_pdf = self.dir_path / "report.pdf"
        doc_pdf.write_bytes(b"%PDF-1.4\n")

        # 1. File-like image output_path rejected
        res_file_out = pdf_to_images(pdf_path=str(doc_pdf), output_path=str(self.dir_path / "page.jpg"))
        self.assertFalse(res_file_out["success"])
        self.assertIn("directory path", res_file_out["error"].lower())

        # 2. overwrite=False when default <stem>_images dir already exists
        existing_default_dir = self.dir_path / "report_images"
        existing_default_dir.mkdir()
        res_dup_default = pdf_to_images(pdf_path=str(doc_pdf), overwrite=False)
        self.assertFalse(res_dup_default["success"])
        self.assertIn("Destination already exists", res_dup_default["error"])

        # 3. overwrite=False when custom output_path/<stem>_images dir already exists
        custom_out = self.dir_path / "custom_out"
        (custom_out / "report_images").mkdir(parents=True)
        res_dup_custom = pdf_to_images(pdf_path=str(doc_pdf), output_path=str(custom_out), overwrite=False)
        self.assertFalse(res_dup_custom["success"])
        self.assertIn("Destination already exists", res_dup_custom["error"])

    def test_list_supported_formats_errors_and_combined_filter(self):
        res_bad_fmt = list_supported_formats(source_format="NOTAFMT")
        self.assertFalse(res_bad_fmt["success"])
        self.assertIn("not a recognized source format", res_bad_fmt["error"])

        res_bad_cat = list_supported_formats(category="notacat")
        self.assertFalse(res_bad_cat["success"])
        self.assertIn("not recognized", res_bad_cat["error"])

        res_mismatch = list_supported_formats(category="audio", source_format="PNG")
        self.assertFalse(res_mismatch["success"])
        self.assertIn("does not belong to category 'audio'", res_mismatch["error"])

        res_match = list_supported_formats(category="image", source_format="PNG")
        self.assertEqual(res_match["category"], "image")
        self.assertEqual(res_match["source_format"], "PNG")
        self.assertIn("JPG", res_match["target_formats"])

    def test_perform_stt_mcp_missing_model_message(self):
        dummy_audio = self.dir_path / "audio.mp3"
        dummy_audio.touch()
        raw_err = "Whisper model 'small' (~466 MB) is not installed. Rerun conversion with --install-deps to download it."
        with patch("mcp_server.server.convert", return_value={"success": False, "error": raw_err, "converted_files": []}):
            res = stt(input_path=str(dummy_audio), model="small")
        self.assertFalse(res["success"])
        self.assertNotIn("Rerun conversion with --install-deps", res["error"])
        self.assertIn("python Convergent.py --install-deps", res["error"])

    def test_decompress_archive_compound_suffixes(self):
        from modules.decompress import archive_stem
        self.assertEqual(archive_stem(Path("out.tar.gz")), "out")
        self.assertEqual(archive_stem(Path("out.tar.bz2")), "out")
        self.assertEqual(archive_stem(Path("out.TAR.XZ")), "out")
        self.assertEqual(archive_stem(Path("out.tar.zst")), "out")
        self.assertEqual(archive_stem(Path("out.zip")), "out")

        tar_gz = self.dir_path / "bundle.tar.gz"
        tar_gz.write_bytes(b"fake")
        expected_dir = self.dir_path / "bundle"

        def fake_decompress(path, output_dir=None, interactive=False, password=None):
            expected_dir.mkdir(exist_ok=True)
            (expected_dir / "file.txt").write_text("hi")
            return True, "", expected_dir

        with patch("mcp_server.server.conv.decompress", side_effect=fake_decompress):
            res = decompress(archive_path=str(tar_gz))
        self.assertTrue(res["success"])
        self.assertEqual(Path(res["output_dir"]).name, "bundle")
        self.assertEqual(res["extracted_files_count"], 1)

    def test_split_file_cleans_stale_parts_on_resplit_preserves_other_files(self):
        from modules.split import record_split_generated_file
        dummy_pdf = self.dir_path / "doc.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4\n")
        out_dir = self.dir_path / "split_out"
        out_dir.mkdir()
        stale1 = out_dir / "part_1_1-2.pdf"
        stale2 = out_dir / "part_2_3-4.pdf"
        canary = out_dir / "canary.txt"
        stale1.write_bytes(b"old1")
        stale2.write_bytes(b"old2")
        canary.write_text("keep")

        def fake_split_pdf(*args, **kwargs):
            new_part = out_dir / "part_1_1-3.pdf"
            new_part.write_bytes(b"new1")
            record_split_generated_file(new_part)
            return out_dir

        with patch("mcp_server.server.conv.split_pdf", side_effect=fake_split_pdf), \
             patch("modules.split.send_to_trash") as mock_trash:
            res = split(file_path=str(dummy_pdf), mode="parts", num_parts=1, output_dir=str(out_dir))
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 1)
        self.assertEqual([Path(p).name for p in res["split_files"]], ["part_1_1-3.pdf"])
        self.assertFalse(stale1.exists())
        self.assertFalse(stale2.exists())
        self.assertTrue(canary.exists())
        mock_trash.assert_not_called()

    def test_perform_ocr_directory_aggregates_total_characters_and_labels_preview(self):
        img_dir = self.dir_path / "scans"
        img_dir.mkdir()
        f1 = self.dir_path / "page1.txt"
        f2 = self.dir_path / "page2.txt"
        f1.write_text("Hello")
        f2.write_text("World!")
        with patch("mcp_server.server.convert", return_value={
            "success": True,
            "count": 2,
            "converted_files": [str(f1), str(f2)],
            "target_format": "TXT",
        }):
            res = ocr(input_path=str(img_dir), preview_length=500)
        self.assertTrue(res["success"])
        self.assertEqual(res["total_characters"], 11)
        self.assertIn("page1.txt", res["extracted_text_preview"])
        self.assertIn("page2.txt", res["extracted_text_preview"])

    def test_convergent_convert_same_format_message_and_symlink_output_and_svg_font_hint(self):
        # 1. Same-format in-place skip includes informative message
        png = self.dir_path / "pic.png"
        png.write_bytes(b"png")
        res_same = convert(input_path=str(png), target_format="PNG", use_cache=False)
        self.assertTrue(res_same["success"])
        self.assertEqual(res_same.get("message"), "Skipped (same format as input).")

        # 2. Symlink input with output_path=None writes next to symlink
        real_dir = self.dir_path / "real_target"
        link_dir = self.dir_path / "work_dir"
        real_dir.mkdir()
        link_dir.mkdir()
        real_file = real_dir / "source.txt"
        real_file.write_text("hello")
        sym_file = link_dir / "alias.txt"
        sym_file.symlink_to(real_file)

        res_sym = convert(input_path=str(sym_file), target_format="MD", use_cache=False)
        self.assertTrue(res_sym["success"])
        self.assertEqual(Path(res_sym["converted_files"][0]).parent.resolve(), link_dir.resolve())
        self.assertFalse((real_dir / "source.md").exists())
        self.assertIn("symlink", res_sym.get("note", "").lower())

        # 3. SVG font error hint
        from modules import image
        svg = self.dir_path / "diagram.svg"
        svg.write_text("<svg><text>Hi</text></svg>")
        with patch("modules.image.shutil.which", side_effect=lambda c: "/usr/bin/magick" if c == "magick" else None), \
             patch("modules.image.run_command", return_value=(False, "magick: unable to read font `Helvetica'")):
            ok, err = image.convert_image(svg, "PNG")
        self.assertFalse(ok)
        self.assertIn("Freetype font missing for SVG <text>", err)

    def test_sanitize_mcp_error_and_single_failure_dedup(self):
        from mcp_server.server import _sanitize_mcp_error

        raw = (
            "FFmpeg failed: Invalid data found when processing input\n"
            "[out#0/mp4 @ 0x7f8b1c004a00] Error opening output file /tmp/.tmp_abc123/out.mp4\n"
            "[vost#0:0/libx264 @ 0x7f8b1c005b00] Could not write header"
        )
        cleaned = _sanitize_mcp_error(raw)
        self.assertIn("FFmpeg failed: Invalid data found", cleaned)
        self.assertNotIn("0x7f8b1c004a00", cleaned)
        self.assertNotIn(".tmp_abc123", cleaned)

        src_file = self.dir_path / "broken.mp4"
        src_file.touch()

        def fake_fail(*args, **kwargs):
            failed = kwargs.get("failed_details")
            if failed is not None:
                failed.append({"file": str(src_file), "name": "broken.mp4", "error": "Line 1 error\nLine 2 detail"})
            return []

        with patch("mcp_server.server.conv.process", side_effect=fake_fail):
            res = convert(input_path=str(src_file), target_format="MP3", overwrite=True, use_cache=False)
        self.assertFalse(res["success"])
        self.assertNotIn("failed_files", res)
        self.assertIn("broken.mp4", res["error"])
        self.assertIn("Line 1 error", res["error"])
        self.assertIn("Line 2 detail", res["error"])

    def test_split_file_truncation_cap_matches_25_to_10(self):
        doc_pdf = self.dir_path / "many.pdf"
        doc_pdf.touch()
        split_dir = self.dir_path / "many_split"
        split_dir.mkdir()
        for i in range(1, 31):
            (split_dir / f"page_{i:03d}.pdf").touch()

        with patch("mcp_server.server.conv.split_pdf", return_value=str(split_dir)):
            res = split(file_path=str(doc_pdf), output_dir=str(split_dir))
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 30)
        self.assertTrue(res["truncated"])
        self.assertEqual(len(res["split_files"]), 10)
        self.assertIn("manifest_path", res)

    def test_pdf_page_count_falls_back_to_gs_without_mdls(self):
        from modules.split import get_pdf_page_count as split_page_count
        from modules.combine import get_pdf_page_count as combine_page_count

        pdf_file = self.dir_path / "dummy.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%%EOF\n")

        fake_gs = MagicMock(returncode=0, stdout="5\n", stderr="")
        with patch("shutil.which", side_effect=lambda cmd: None if cmd == "mdls" else f"/usr/bin/{cmd}"), \
             patch("subprocess.run", return_value=fake_gs) as mock_run:
            self.assertEqual(split_page_count(str(pdf_file)), 5)
            self.assertEqual(combine_page_count(str(pdf_file)), 5)
            self.assertEqual(mock_run.call_count, 2)
            self.assertEqual(mock_run.call_args_list[0][0][0][0], "gs")
            self.assertEqual(mock_run.call_args_list[1][0][0][0], "gs")

    def test_encrypted_pdf_ocr_rejected_without_zero_byte_output(self):
        from modules import ocr as ocr_mod
        from customs.run_command import LAST_COMMAND_STDERR, LAST_COMMAND_STDOUT

        enc_pdf = self.dir_path / "encrypted.pdf"
        enc_pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Encrypt 2 0 R >> endobj\n%%EOF\n")

        def fake_gs_encrypted(cmd, *args, **kwargs):
            if cmd[0] == "gs":
                LAST_COMMAND_STDERR.set("   **** This file requires a password for access.")
                LAST_COMMAND_STDOUT.set("   **** Error: Couldn't initialise file.")
                return True, ""
            if cmd[0] == "sips":
                raise AssertionError("sips fallback must not run after gs fails on encrypted PDF")
            return False, "unexpected"

        def fake_which(c):
            if c in ("gs", "sips", "tesseract", "pandoc"):
                return f"/usr/bin/{c}"
            return None

        with patch("modules.ocr.shutil.which", side_effect=fake_which), \
             patch("modules.ocr.run_command", side_effect=fake_gs_encrypted):
            with self.assertRaises(RuntimeError) as cm:
                ocr_mod._convert_pdf_to_temp_images(enc_pdf)
            self.assertIn("encrypted or password-protected PDF", str(cm.exception))

            out_txt_custom = self.dir_path / "custom_out.txt"
            res_ocr = ocr(input_path=str(enc_pdf), target_format="TXT", output_path=str(out_txt_custom))
            self.assertFalse(res_ocr["success"])
            self.assertIn("encrypted or password-protected PDF", res_ocr["error"])
            self.assertFalse((self.dir_path / "encrypted.txt").exists())
            self.assertFalse(out_txt_custom.exists())

            res_conv = convert(input_path=str(enc_pdf), target_format="TXT", use_cache=False)
            self.assertFalse(res_conv["success"])
            self.assertIn("encrypted or password-protected PDF", res_conv["error"])
            self.assertFalse((self.dir_path / "encrypted.txt").exists())

            out_pdf_custom = self.dir_path / "ocr_out.pdf"
            res_pdf = ocr(input_path=str(enc_pdf), target_format="PDF", output_path=str(out_pdf_custom))
            self.assertFalse(res_pdf["success"])
            self.assertIn("encrypted or password-protected PDF", res_pdf["error"])
            self.assertFalse(out_pdf_custom.exists())

        # Even if only sips is installed, /Encrypt hint blocks blank-PNG masking
        with patch("modules.ocr.shutil.which", side_effect=lambda c: f"/usr/bin/{c}" if c in ("sips", "tesseract") else None), \
             patch("modules.ocr.run_command", side_effect=AssertionError("sips must not run on encrypted PDF")):
            with self.assertRaises(RuntimeError) as cm_sips:
                ocr_mod._convert_pdf_to_temp_images(enc_pdf)
            self.assertIn("encrypted or password-protected PDF", str(cm_sips.exception))

        # Corrupt/unreadable PDF failing gs must not fall back to sips either
        corrupt_pdf = self.dir_path / "corrupt.pdf"
        corrupt_pdf.write_bytes(b"%PDF-1.4\nnot valid pdf content\n")

        def fake_gs_corrupt(cmd, *args, **kwargs):
            if cmd[0] == "gs":
                LAST_COMMAND_STDERR.set("")
                LAST_COMMAND_STDOUT.set("   **** Error: Couldn't initialise file.")
                return True, ""
            if cmd[0] == "sips":
                raise AssertionError("sips fallback must not mask gs failure on unreadable PDF")
            return False, "unexpected"

        with patch("modules.ocr.shutil.which", side_effect=fake_which), \
             patch("modules.ocr.run_command", side_effect=fake_gs_corrupt):
            with self.assertRaises(RuntimeError) as cm_corrupt:
                ocr_mod._convert_pdf_to_temp_images(corrupt_pdf)
            self.assertIn("Could not render PDF pages for OCR", str(cm_corrupt.exception))

    def test_compress_files_respects_overwrite(self):
        src = self.dir_path / "note.txt"
        src.write_text("compress me", encoding="utf-8")
        archive_path = self.dir_path / "bundle.zip"
        archive_path.write_bytes(b"existing_archive")

        res_no = compress(
            file_paths=[str(src)],
            output_name="bundle.zip",
            output_dir=str(self.dir_path),
            overwrite=False,
        )
        self.assertFalse(res_no["success"])
        self.assertIn("Destination already exists", res_no["error"])
        self.assertEqual(archive_path.read_bytes(), b"existing_archive")

        res_yes = compress(
            file_paths=[str(src)],
            output_name="bundle.zip",
            output_dir=str(self.dir_path),
            overwrite=True,
        )
        self.assertTrue(res_yes["success"], msg=res_yes.get("error"))
        import zipfile
        self.assertTrue(zipfile.is_zipfile(archive_path))

    def test_decompress_archive_respects_overwrite(self):
        import zipfile
        import tarfile

        zip_path = self.dir_path / "bundle.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file1.txt", "new_from_zip")
            zf.writestr("sub/file2.txt", "nested_from_zip")

        # 1. Existing directory with unrelated file -> overwrite=False succeeds cleanly
        out_dir = self.dir_path / "out"
        out_dir.mkdir()
        unrelated = out_dir / "unrelated.txt"
        unrelated.write_text("keep_me", encoding="utf-8")

        res_non_colliding = decompress(str(zip_path), output_dir=str(out_dir), overwrite=False)
        self.assertTrue(res_non_colliding["success"], msg=res_non_colliding.get("error"))
        self.assertEqual((out_dir / "file1.txt").read_text(encoding="utf-8"), "new_from_zip")
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep_me")

        # 2. Existing colliding file -> overwrite=False rejects without clobbering
        (out_dir / "file1.txt").write_text("original_local", encoding="utf-8")
        res_collide = decompress(str(zip_path), output_dir=str(out_dir), overwrite=False)
        self.assertFalse(res_collide["success"])
        self.assertIn("conflicting file", res_collide["error"])
        self.assertEqual((out_dir / "file1.txt").read_text(encoding="utf-8"), "original_local")
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep_me")

        # 3. overwrite=True overwrites colliding file
        res_overwrite = decompress(str(zip_path), output_dir=str(out_dir), overwrite=True)
        self.assertTrue(res_overwrite["success"], msg=res_overwrite.get("error"))
        self.assertEqual((out_dir / "file1.txt").read_text(encoding="utf-8"), "new_from_zip")

        # 4. Default output_dir=None with overwrite=False preserves unrelated files and blocks collisions
        tgz_path = self.dir_path / "pkg.tar.gz"
        payload = self.dir_path / "item.txt"
        payload.write_text("from_tar", encoding="utf-8")
        with tarfile.open(tgz_path, "w:gz") as tf:
            tf.add(payload, arcname="item.txt")

        default_dir = self.dir_path / "pkg"
        default_dir.mkdir()
        (default_dir / "keep.txt").write_text("do_not_trash", encoding="utf-8")
        res_tgz_ok = decompress(str(tgz_path), overwrite=False)
        self.assertTrue(res_tgz_ok["success"], msg=res_tgz_ok.get("error"))
        self.assertEqual((default_dir / "keep.txt").read_text(encoding="utf-8"), "do_not_trash")
        self.assertEqual((default_dir / "item.txt").read_text(encoding="utf-8"), "from_tar")

        (default_dir / "item.txt").write_text("local_edit", encoding="utf-8")
        res_tgz_collide = decompress(str(tgz_path), overwrite=False)
        self.assertFalse(res_tgz_collide["success"])
        self.assertEqual((default_dir / "item.txt").read_text(encoding="utf-8"), "local_edit")
        self.assertEqual((default_dir / "keep.txt").read_text(encoding="utf-8"), "do_not_trash")

        # 5. Parser unit checks for 7z and unrar listings
        from modules.decompress import _parse_7z_slt_members, _parse_unrar_lt_members
        parsed_7z = _parse_7z_slt_members(
            "Listing archive: test.7z\n----------\nPath = sub\nAttributes = D drwxr-xr-x\n\nPath = sub/b.txt\nAttributes = A\n"
        )
        self.assertEqual(parsed_7z, [("sub", True), ("sub/b.txt", False)])
        parsed_rar = _parse_unrar_lt_members(
            "        Name: sub\n        Type: Directory\n        Name: sub/b.txt\n        Type: File\n"
        )
        self.assertEqual(parsed_rar, [("sub", True), ("sub/b.txt", False)])

    def test_directory_convert_skips_same_format_and_disambiguates_distinct_sources(self):
        from Convergent import Converter
        batch_dir = self.dir_path / "batch_mixed"
        batch_dir.mkdir()
        for i in range(1, 5):
            (batch_dir / f"item_{i:02d}.png").write_bytes(b"png")
        existing_jpg = batch_dir / "item_01.jpg"
        existing_jpg.write_bytes(b"original_jpg")

        converted_calls = []

        def fake_convert_image(self_conv, source, target_ext, **kwargs):
            converted_calls.append(Path(source).name)
            out_p = Path(source).with_suffix(f".{target_ext.lower()}")
            out_p.write_bytes(b"converted_jpg")
            return True, ""

        with patch.object(Converter, "prepare_conversion", return_value=True), \
             patch.object(Converter, "convert_image", fake_convert_image):
            res = convert(
                input_path=str(batch_dir),
                target_format="JPG",
                overwrite=False,
                use_cache=False,
            )

        self.assertTrue(res["success"], msg=res.get("error"))
        self.assertEqual(res["count"], 3)
        self.assertEqual(existing_jpg.read_bytes(), b"original_jpg")
        self.assertFalse((batch_dir / "item_01_png.jpg").exists())
        self.assertFalse((batch_dir / "item_01_jpg.jpg").exists())
        skipped_names = {Path(p).name for p in res.get("skipped_files", [])}
        self.assertEqual(skipped_names, {"item_01.jpg", "item_01.png"})
        self.assertEqual(sorted(converted_calls), ["item_02.png", "item_03.png", "item_04.png"])

        # Same-stem different formats (a.png + a.webp + a.jpg -> JPG) still disambiguates a.png & a.webp while skipping a.jpg
        disambig_dir = self.dir_path / "disambig"
        disambig_dir.mkdir()
        (disambig_dir / "a.png").write_bytes(b"png")
        (disambig_dir / "a.webp").write_bytes(b"webp")
        (disambig_dir / "a.jpg").write_bytes(b"orig_jpg")

        with patch.object(Converter, "prepare_conversion", return_value=True), \
             patch.object(Converter, "convert_image", fake_convert_image):
            res_dis = convert(
                input_path=str(disambig_dir),
                target_format="JPG",
                overwrite=False,
                use_cache=False,
            )

        self.assertTrue(res_dis["success"], msg=res_dis.get("error"))
        self.assertEqual(res_dis["count"], 2)
        out_names = {Path(p).name for p in res_dis["converted_files"]}
        self.assertEqual(out_names, {"a_png.jpg", "a_webp.jpg"})
        self.assertEqual([Path(p).name for p in res_dis.get("skipped_files", [])], ["a.jpg"])
        self.assertEqual((disambig_dir / "a.jpg").read_bytes(), b"orig_jpg")

        # Directory with only target-format files (including JPEG alias) skips all cleanly
        only_jpg_dir = self.dir_path / "only_jpg"
        only_jpg_dir.mkdir()
        (only_jpg_dir / "x.jpg").write_bytes(b"jpg")
        (only_jpg_dir / "y.jpeg").write_bytes(b"jpeg")
        res_all_same = convert(input_path=str(only_jpg_dir), target_format="JPG", use_cache=False)
        self.assertTrue(res_all_same["success"], msg=res_all_same.get("error"))
        self.assertEqual(res_all_same["count"], 0)
        self.assertEqual(
            {Path(p).name for p in res_all_same.get("skipped_files", [])},
            {"x.jpg", "y.jpeg"},
        )

    def test_convergent_convert_source_format_filter_and_validation(self):
        from Convergent import Converter
        mix_dir = self.dir_path / "mix_filter"
        mix_dir.mkdir()
        (mix_dir / "pic.png").write_bytes(b"png")
        (mix_dir / "photo.webp").write_bytes(b"webp")
        (mix_dir / "snap.jpeg").write_bytes(b"jpeg")

        def fake_convert_image(self_conv, source, target_ext, **kwargs):
            out_p = Path(source).with_suffix(f".{target_ext.lower()}")
            out_p.write_bytes(b"converted")
            return True, ""

        # 1. Invalid source_format rejected
        res_bad = convert(input_path=str(mix_dir), source_format="NOTAFMT", target_format="JPG")
        self.assertFalse(res_bad["success"])
        self.assertIn("Unsupported source_format", res_bad["error"])

        # 2. Directory filtered to PNG only
        with patch.object(Converter, "prepare_conversion", return_value=True), \
             patch.object(Converter, "convert_image", fake_convert_image):
            res_png = convert(
                input_path=str(mix_dir),
                source_format="png",
                target_format="JPG",
                use_cache=False,
            )
        self.assertTrue(res_png["success"], msg=res_png.get("error"))
        self.assertEqual(res_png["count"], 1)
        self.assertEqual([Path(p).name for p in res_png["converted_files"]], ["pic.jpg"])
        self.assertFalse((mix_dir / "photo.jpg").exists())

        # 3. Alias normalization: source_format="JPEG" matches both pic.jpg (from step 2) and snap.jpeg
        with patch.object(Converter, "prepare_conversion", return_value=True), \
             patch.object(Converter, "convert_image", fake_convert_image):
            res_jpeg = convert(
                input_path=str(mix_dir),
                source_format="JPEG",
                target_format="BMP",
                use_cache=False,
            )
        self.assertTrue(res_jpeg["success"], msg=res_jpeg.get("error"))
        self.assertEqual({Path(p).name for p in res_jpeg["converted_files"]}, {"pic.bmp", "snap.bmp"})
        self.assertFalse((mix_dir / "photo.bmp").exists())

        # 4. Single-file mismatch rejected clearly
        res_mismatch = convert(
            input_path=str(mix_dir / "pic.png"),
            source_format="JPG",
            target_format="WEBP",
            use_cache=False,
        )
        self.assertFalse(res_mismatch["success"])
        self.assertIn("does not match source_format 'JPG'", res_mismatch["error"])

    def test_split_file_rejects_incompatible_modes_and_warns_ignored_args(self):
        vid = self.dir_path / "clip.mp4"
        vid.write_bytes(b"mp4")
        mp3 = self.dir_path / "song.mp3"
        mp3.write_bytes(b"mp3")
        pdf = self.dir_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        gif = self.dir_path / "anim.gif"
        gif.write_bytes(b"GIF89a")

        for media_f in (vid, mp3):
            for bad_mode in ("pages", "frames"):
                res = split(file_path=str(media_f), mode=bad_mode)
                self.assertFalse(res["success"])
                self.assertIn("not supported", res["error"])
                self.assertIn("interval", res["error"])

        for bad_doc_mode in ("interval", "frames"):
            res = split(file_path=str(pdf), mode=bad_doc_mode)
            self.assertFalse(res["success"])
            self.assertIn("not supported", res["error"])
            self.assertIn("pages", res["error"])

        res_gif = split(file_path=str(gif), mode="pages")
        self.assertFalse(res_gif["success"])
        self.assertIn("not supported", res_gif["error"])
        self.assertIn("frames", res_gif["error"])

        # Explicit mode='pages' with num_parts attaches warning instead of silently ignoring
        out_dir = self.dir_path / "pdf_pages_out"
        out_dir.mkdir()
        with patch("mcp_server.server.conv.split_pdf") as mock_split_pdf:
            def fake_pages(*args, **kwargs):
                (out_dir / "page_001.pdf").write_bytes(b"p1")
                return str(out_dir)
            mock_split_pdf.side_effect = fake_pages
            res_warn = split(file_path=str(pdf), mode="pages", num_parts=2, output_dir=str(out_dir))
            self.assertTrue(res_warn["success"])
            self.assertTrue(any("ignores" in w for w in res_warn.get("warnings", [])))

    def test_resize_media_rejects_conflicting_scale_percent_and_dimensions(self):
        img = self.dir_path / "photo.png"
        img.write_bytes(b"png")

        res_w = resize(file_path=str(img), width=100, scale_percent=50)
        self.assertFalse(res_w["success"])
        self.assertIn("Conflicting sizing parameters", res_w["error"])

        res_h = resize(file_path=str(img), height=100, scale_percent=50)
        self.assertFalse(res_h["success"])
        self.assertIn("Conflicting sizing parameters", res_h["error"])

        res_wh = resize(file_path=str(img), width=100, height=200, scale_percent=50)
        self.assertFalse(res_wh["success"])
        self.assertIn("Conflicting sizing parameters", res_wh["error"])

    def test_convergent_convert_pdf_ocr_false_warning(self):
        from Convergent import Converter
        pdf_file = self.dir_path / "scan.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        def fake_convert_pdf(self_conv, source, target_ext, **kwargs):
            out_p = Path(source).with_suffix(f".{target_ext.lower()}")
            out_p.write_text("extracted text", encoding="utf-8")
            return True, ""

        with patch.object(Converter, "prepare_conversion", return_value=True), \
             patch.object(Converter, "convert_pdf", fake_convert_pdf):
            # Explicit ocr=False -> warns that OCR override occurred
            res_false = convert(
                input_path=str(pdf_file),
                target_format="TXT",
                ocr=False,
                use_cache=False,
            )
            self.assertTrue(res_false["success"], msg=res_false.get("error"))
            self.assertIn("warnings", res_false)
            self.assertTrue(any("ocr=False was overridden" in w for w in res_false["warnings"]))

            # Default omitted ocr (None) -> no override warning
            res_default = convert(
                input_path=str(pdf_file),
                target_format="TXT",
                use_cache=False,
            )
            self.assertTrue(res_default["success"], msg=res_default.get("error"))
            self.assertNotIn("warnings", res_default)

    def test_perform_ocr_pdf_summary_metadata(self):
        pdf_out = self.dir_path / "searchable.pdf"
        pdf_out.write_bytes(b"%PDF-1.4\n")
        with patch("mcp_server.server.convert") as mock_conv:
            mock_conv.return_value = {
                "success": True,
                "count": 1,
                "converted_files": [str(pdf_out)],
                "target_format": "PDF",
            }
            res = ocr(input_path=str(pdf_out), target_format="PDF")
        self.assertTrue(res["success"])
        self.assertIsNone(res.get("total_characters"))
        self.assertEqual(
            res.get("extracted_text_preview"),
            "[Searchable OCR text layer embedded in PDF document]",
        )

    def test_convergent_convert_pdf_to_images_note_and_output_directory(self):
        pdf_file = self.dir_path / "slides.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")
        img_dir = self.dir_path / "slides_images"
        img_dir.mkdir()
        (img_dir / "page_001.png").write_bytes(b"png1")
        (img_dir / "page_002.png").write_bytes(b"png2")

        with patch("mcp_server.server.conv.process", return_value=[img_dir]):
            res = convert(
                input_path=str(pdf_file),
                target_format="PNG",
                use_cache=False,
            )
        self.assertTrue(res["success"])
        self.assertEqual(res["converted_files"], [str(img_dir)])
        self.assertEqual(res.get("output_directory"), str(img_dir))
        self.assertIn("pdf_to_images", res.get("note", ""))
        self.assertIn("2 page image file(s)", res.get("note", ""))

    def test_combine_files_single_file_warning(self):
        single_pdf = self.dir_path / "only_one.pdf"
        single_pdf.write_bytes(b"%PDF-1.4\n")
        out_pdf = self.dir_path / "combined.pdf"
        with patch("mcp_server.server.conv.combine_pdfs", return_value=out_pdf):
            res = combine(file_paths=[str(single_pdf)], output_path=str(out_pdf))
        self.assertTrue(res["success"])
        self.assertEqual(res["output_file"], str(out_pdf))
        self.assertEqual(
            res.get("warnings"),
            ["Only 1 input file was provided; created output without merging multiple files."],
        )

        second_pdf = self.dir_path / "second.pdf"
        second_pdf.write_bytes(b"%PDF-1.4\n")
        with patch("mcp_server.server.conv.combine_pdfs", return_value=out_pdf):
            res_multi = combine(file_paths=[str(single_pdf), str(second_pdf)], output_path=str(out_pdf))
        self.assertTrue(res_multi["success"])
        self.assertNotIn("warnings", res_multi)

    def test_list_supported_formats_include_dependencies(self):
        models_dir = self.dir_path / "whisper_models"
        models_dir.mkdir()
        (models_dir / "ggml-base.bin").write_bytes(b"model")
        (models_dir / "ggml-tiny.bin").write_bytes(b"model")
        (models_dir / "ggml-small.tmp").write_bytes(b"partial")

        with patch("modules.stt.MODELS_DIR", models_dir), \
             patch("modules.ocr.HAS_MACOS_VISION", True), \
             patch("modules.stt.find_whisper_binary", return_value="/opt/homebrew/bin/whisper-cli"), \
             patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd in ("ffmpeg", "ffprobe", "gs", "magick") else None):
            res = list_supported_formats(include_dependencies=True)

        self.assertIn("dependencies", res)
        deps = res["dependencies"]
        self.assertTrue(deps["macos_vision"])
        self.assertEqual(deps["whisper_models"], ["base", "tiny"])
        self.assertTrue(deps["binaries"]["ffmpeg"])
        self.assertTrue(deps["binaries"]["ffprobe"])
        self.assertTrue(deps["binaries"]["gs"])
        self.assertTrue(deps["binaries"]["magick"])
        self.assertTrue(deps["binaries"]["whisper"])
        self.assertFalse(deps["binaries"]["tesseract"])

    def test_mcp_schemas_strip_titles_have_enums_and_case_insensitive_validation(self):
        import json
        from mcp_server.server import mcp

        def has_title_key(obj):
            if isinstance(obj, dict):
                if "title" in obj:
                    return True
                return any(has_title_key(v) for v in obj.values())
            if isinstance(obj, list):
                return any(has_title_key(item) for item in obj)
            return False

        async def check_schemas_and_calls():
            tools = await mcp.list_tools()
            by_name = {t.name: t for t in tools}

            for t in tools:
                self.assertFalse(
                    has_title_key(t.inputSchema),
                    f"Tool {t.name} inputSchema still contains 'title': {t.inputSchema}",
                )

            # Verify enum definitions on the 7 parameterized tools
            self.assertEqual(
                by_name["pdf_to_images"].inputSchema["properties"]["target_format"]["enum"],
                ["JPG", "PNG", "TIF", "BMP"],
            )
            self.assertEqual(
                by_name["extract_audio"].inputSchema["properties"]["target_format"]["enum"],
                ["MP3", "WAV", "AAC", "FLAC", "M4A", "OGG"],
            )
            self.assertEqual(
                by_name["ocr"].inputSchema["properties"]["target_format"]["enum"],
                ["TXT", "MD", "DOCX", "PDF"],
            )
            self.assertEqual(
                by_name["stt"].inputSchema["properties"]["target_format"]["enum"],
                ["TXT", "SRT", "VTT", "MD"],
            )
            self.assertEqual(
                by_name["compress"].inputSchema["properties"]["format"]["enum"],
                ["ZIP", "TAR.GZ", "TAR.BZ2", "TAR.XZ", "7Z", "RAR"],
            )
            self.assertEqual(
                by_name["split"].inputSchema["properties"]["frame_format"]["enum"],
                ["png", "jpg"],
            )
            cat_any_of = by_name["list_supported_formats"].inputSchema["properties"]["category"]["anyOf"]
            self.assertEqual(cat_any_of[0]["enum"], ["image", "video", "audio", "document"])

            # Verify case-insensitive and alias inputs succeed through FastMCP validation AND emit compact JSON
            res_cat = await mcp.call_tool("list_supported_formats", {"category": "IMAGE"})
            self.assertEqual(len(res_cat), 1)
            raw_text = res_cat[0].text
            self.assertNotIn("\n  ", raw_text)
            self.assertEqual(json.loads(raw_text)["category"], "image")

            res_cat_num = await mcp.call_tool("list_supported_formats", {"category": "5"})
            self.assertEqual(json.loads(res_cat_num[0].text)["category"], "document")

            # Lowercase & alias inputs for enum-validated tools
            dummy_pdf = self.dir_path / "s.pdf"
            dummy_pdf.write_bytes(b"%PDF-1.4\n")
            dummy_txt = self.dir_path / "n.txt"
            dummy_txt.write_text("hi", encoding="utf-8")
            dummy_img = self.dir_path / "p.png"
            dummy_img.write_bytes(b"png")
            dummy_aud = self.dir_path / "a.wav"
            dummy_aud.write_bytes(b"wav")

            with patch("mcp_server.server.convert", return_value={"success": True, "converted_files": [str(dummy_txt)]}) as mock_cc:
                await mcp.call_tool("ocr", {"input_path": str(dummy_img), "target_format": "txt"})
                self.assertEqual(mock_cc.call_args[1]["target_format"], "TXT")

                await mcp.call_tool("stt", {"input_path": str(dummy_aud), "target_format": "srt"})
                self.assertEqual(mock_cc.call_args[1]["target_format"], "SRT")

            with patch("mcp_server.server.conv.compress", return_value=(True, "", self.dir_path / "out.tar.gz")) as mock_comp:
                res_comp = await mcp.call_tool(
                    "compress",
                    {"file_paths": [str(dummy_txt)], "output_name": "out.tgz", "format": "tgz", "output_dir": str(self.dir_path)},
                )
                self.assertEqual(mock_comp.call_args[1]["format_choice"], "TAR.GZ")
                self.assertTrue(json.loads(res_comp[0].text)["success"])

            with patch("mcp_server.server.convert", return_value={"success": False, "error": "missing"}):
                res_p2i = await mcp.call_tool("pdf_to_images", {"pdf_path": str(dummy_pdf), "target_format": "jpeg"})
                self.assertFalse(json.loads(res_p2i[0].text)["success"])

            # Verify docstrings and server instructions include error/behavior guidance
            self.assertIn("isError=true", mcp.instructions)
            self.assertIn("OCR", convert.__doc__)
            self.assertIn("pdf_to_images", convert.__doc__)
            self.assertIn("Ghostscript", resize.__doc__)

        asyncio.run(check_schemas_and_calls())


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
                self.assertIn("isError=true", init_res.instructions or "")

                # 2. Bounded list_tools
                tools_res = await asyncio.wait_for(session.list_tools(), timeout=5.0)
                tool_names = [t.name for t in tools_res.tools]
                self.assertIn("convert", tool_names)
                self.assertIn("list_supported_formats", tool_names)
                self.assertIn("pdf_to_images", tool_names)
                self.assertIn("ocr", tool_names)
                self.assertIn("stt", tool_names)
                self.assertIn("compress", tool_names)
                self.assertIn("decompress", tool_names)
                self.assertIn("resize", tool_names)
                for t in tools_res.tools:
                    self.assertIsNone(t.outputSchema, f"{t.name} should not emit outputSchema")
                    self.assertNotIn("title", t.inputSchema, f"{t.name} should strip title from inputSchema")

                # 3. Bounded call_tool (verify compact JSON response)
                call_res = await asyncio.wait_for(session.call_tool("list_supported_formats", {}), timeout=5.0)
                self.assertFalse(call_res.isError)
                self.assertIsNone(call_res.structuredContent)
                self.assertNotIn("\n  ", call_res.content[0].text)


if __name__ == "__main__":
    unittest.main()
