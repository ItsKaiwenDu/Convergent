import os
import sys
import time
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

from customs.run_command import run_command
from customs.cache import CacheManager, PARTIAL_THRESHOLD
from modules.resize import calculate_crop_and_scale
from modules.compress import compress
from modules.combine import combine_pdfs, combine_videos, combine_audios
from mcp_server.server import (
    convergent_convert,
    pdf_to_images,
    perform_ocr,
    combine_files,
    compress_files,
    split_file,
    list_supported_formats,
    decompress_archive,
    resize_media,
    extract_audio,
)


class TestActionFixes(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. Run Command: stdin=DEVNULL and stderr tail-trimming
    def test_run_command_stdin_devnull(self):
        # 'cat' without stdin would hang if stdin were open; DEVNULL causes immediate EOF
        success, _ = run_command(["cat"])
        self.assertTrue(success)

    def test_run_command_stderr_tail_truncation(self):
        # Trigger an error with a long stderr output
        long_message = "A" * 2000
        cmd = [sys.executable, "-c", f"import sys; sys.stderr.write('{long_message}'); sys.exit(1)"]
        success, err = run_command(cmd)
        self.assertFalse(success)
        self.assertLessEqual(len(err), 1500)
        self.assertEqual(err, "A" * 1500)

    # 2. Combine: Input-as-output alias rejection
    def test_combine_rejects_input_as_output(self):
        pdf1 = self.dir_path / "a.pdf"
        pdf2 = self.dir_path / "b.pdf"
        pdf1.write_bytes(b"%PDF-1.4 a")
        pdf2.write_bytes(b"%PDF-1.4 b")

        # Combining into pdf1 directly must be rejected
        res = combine_pdfs([str(pdf1), str(pdf2)], output_path=str(pdf1), interactive=False)
        self.assertIsNone(res)

        from Convergent import Converter
        conv = Converter()
        self.assertIsNone(conv.combine_pdfs([str(pdf1), str(pdf2)], output_path=str(pdf1), interactive=False))

        # Via MCP tool
        mcp_res = combine_files([str(pdf1), str(pdf2)], output_path=str(pdf1))
        self.assertFalse(mcp_res["success"])
        self.assertIn("cannot be one of the input files", mcp_res["error"])

    # 3. Combine: Mixed video filter_complex
    def test_combine_videos_filter_complex_generation(self):
        vid1 = self.dir_path / "v1.mp4"
        vid2 = self.dir_path / "v2.mov"
        vid1.touch()
        vid2.touch()

        def mock_has_audio(p):
            return str(p).endswith("v1.mp4")

        def fake_run_cmd(cmd):
            Path(cmd[-1]).touch()
            return True, ""

        with patch("modules.combine.run_command", side_effect=fake_run_cmd) as mock_cmd, \
             patch("modules.combine.has_audio_stream", side_effect=mock_has_audio), \
             patch("modules.combine.get_media_duration", return_value=5.0):
            res = combine_videos([str(vid1), str(vid2)], output_path=str(self.dir_path / "out.mp4"), interactive=False)
            self.assertIsNotNone(res)
            self.assertTrue(mock_cmd.called)
            cmd_args = mock_cmd.call_args[0][0]
            self.assertIn("-filter_complex", cmd_args)
            filter_str = cmd_args[cmd_args.index("-filter_complex") + 1]
            self.assertIn("anullsrc=", filter_str)
            self.assertIn("concat=n=2:v=1:a=1", filter_str)

    # 4. Compress: Input-as-output alias rejection
    def test_compress_rejects_input_as_output(self):
        f1 = self.dir_path / "file1.zip"
        f1.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

        res = compress_files(file_paths=[str(f1)], output_name="file1.zip", output_dir=str(self.dir_path))
        self.assertFalse(res["success"])
        self.assertIn("cannot be one of the input files", res["error"])

    # 5. Compress: Password on tar.gz rejection
    def test_compress_rejects_password_on_tar(self):
        f1 = self.dir_path / "file1.txt"
        f1.write_text("content")

        res = compress_files(
            file_paths=[str(f1)],
            output_name="archive.tar.gz",
            format="TAR.GZ",
            output_dir=str(self.dir_path),
            password="secretpassword",
        )
        self.assertFalse(res["success"])
        self.assertIn("TAR archives do not support password encryption", res["error"])

    # 6. Compress: -p- flag in 7z when non-interactive
    def test_compress_7z_non_interactive_p_dash_flag(self):
        f1 = self.dir_path / "file1.txt"
        f1.write_text("content")

        with patch("modules.compress.shutil.which", return_value="/usr/local/bin/7z"), \
             patch("modules.compress.run_command") as mock_cmd:
            def fake_run(cmd, cwd=None):
                tmp_candidates = [a for a in cmd if a.endswith(".7z") or ".tmp_" in a]
                if tmp_candidates:
                    Path(tmp_candidates[0]).touch()
                return True, ""
            mock_cmd.side_effect = fake_run

            success, _, _ = compress(
                [f1],
                "test.7z",
                "7Z",
                output_dir=self.dir_path,
            )
            self.assertTrue(success)
            cmd_args = mock_cmd.call_args[0][0]
            self.assertNotIn("-p-", cmd_args)

    # 7. Resize: Validation for dimensions & aspect ratio
    def test_resize_validation(self):
        # Non-positive dimension/scale
        with self.assertRaises(ValueError):
            calculate_crop_and_scale(100, 100, "16:9", 0, "crop")
        with self.assertRaises(ValueError):
            calculate_crop_and_scale(100, 100, "16:9", -10, "crop")

        # Unknown aspect ratio
        with self.assertRaises(ValueError):
            calculate_crop_and_scale(100, 100, "invalid_ratio", 100, "crop")

    # 8. Batch stem collision disambiguation
    def test_batch_stem_collision_disambiguation(self):
        from Convergent import Converter
        conv = Converter()

        img1 = self.dir_path / "graphic.jpg"
        img2 = self.dir_path / "graphic.png"
        img1.write_bytes(b"jpg content")
        img2.write_bytes(b"png content")

        out_dir = self.dir_path / "output_webp"
        out_dir.mkdir()

        def fake_convert_image(source, target_ext, **kwargs):
            out_p = kwargs.get("output_file")
            if not out_p:
                out_p = source.with_suffix(f".{target_ext.lower()}")
            out_p.write_bytes(b"webp data")
            return True, ""

        with patch.object(conv, "prepare_conversion", return_value=True), \
             patch.object(conv, "convert_image", side_effect=fake_convert_image):
            converted = conv.process(
                source_formats=["JPG", "PNG"],
                target_format="WEBP",
                paths=[str(self.dir_path)],
                output_dir=str(out_dir),
                interactive=False,
            )
            self.assertEqual(len(converted), 2)
            out_names = {Path(p).name for p in converted}
            self.assertIn("graphic_jpg.webp", out_names)
            self.assertIn("graphic_png.webp", out_names)

    # 9. Pandoc Markdown resource path and cwd
    def test_pandoc_markdown_resource_path_and_cwd(self):
        from modules import doc
        md_file = self.dir_path / "article.md"
        md_file.write_text("# Article\n![Image](assets/logo.png)")

        def fake_pandoc(cmd, cwd=None):
            if "-o" in cmd:
                Path(cmd[cmd.index("-o") + 1]).touch()
            return True, ""

        with patch("modules.doc.run_command", side_effect=fake_pandoc) as mock_cmd:
            success, _ = doc.convert_markdown(md_file, "PDF")
            self.assertTrue(success)
            cmd_args = mock_cmd.call_args[0][0]
            cwd_arg = mock_cmd.call_args[1].get("cwd")
            self.assertIn(f"--resource-path={self.dir_path.resolve()}", cmd_args)
            self.assertEqual(Path(cwd_arg).resolve(), self.dir_path.resolve())

        with patch("modules.doc.run_command", side_effect=fake_pandoc) as mock_cmd:
            success, _ = doc.convert_markdown(md_file, "HTML")
            self.assertTrue(success)
            cmd_args = mock_cmd.call_args[0][0]
            self.assertIn("--embed-resources", cmd_args)
            self.assertIn("--standalone", cmd_args)

    # 10. Cache destination mismatch & mtime change on large files
    def test_cache_destination_mismatch_and_mtime_change(self):
        cache_mgr = CacheManager(db_path=self.dir_path / "test_cache.db")
        src_file = self.dir_path / "data.bin"
        src_file.write_bytes(b"data" * 100)
        out1 = self.dir_path / "out1.dat"
        out2 = self.dir_path / "out2.dat"
        out1.write_bytes(b"out data")
        out2.write_bytes(b"out data")

        params = {"target": "DAT"}
        cache_mgr.save(src_file, out1, params)

        # Querying with out2 should be a cache miss due to out_path mismatch
        is_valid, reason = cache_mgr.is_cached_valid(src_file, out2, params)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "output path mismatch")

        # Large file test (> PARTIAL_THRESHOLD)
        large_src = self.dir_path / "large.bin"
        large_out = self.dir_path / "large.out"
        large_src.write_bytes(b"0" * (PARTIAL_THRESHOLD + 1024))
        large_out.write_bytes(b"done")

        cache_mgr.save(large_src, large_out, params)
        # Touch large_src mtime to simulate modification without size change
        stat = large_src.stat()
        os.utime(large_src, (stat.st_atime, stat.st_mtime + 5.0))

        is_valid_large, reason_large = cache_mgr.is_cached_valid(large_src, large_out, params)
        self.assertFalse(is_valid_large)
        self.assertEqual(reason_large, "mtime changed")
        cache_mgr.close()

    # 11. Video: fps, bitrate, and ogg target
    def test_video_fps_bitrate_and_ogg_audio(self):
        from modules import video
        src_video = self.dir_path / "clip.mp4"
        src_video.touch()

        # Check fps and bitrate flags propagation
        with patch("modules.video.run_command", return_value=(True, "")) as mock_cmd:
            success, _ = video.convert_video(
                src_video, "MP4", fps=60, bitrate="4M"
            )
            self.assertTrue(success)
            cmd_args = mock_cmd.call_args[0][0]
            self.assertIn("-r", cmd_args)
            self.assertEqual(cmd_args[cmd_args.index("-r") + 1], "60")
            self.assertIn("-b:v", cmd_args)
            self.assertEqual(cmd_args[cmd_args.index("-b:v") + 1], "4M")

        # Check native OGG audio extraction
        with patch("modules.video.run_command", return_value=(True, "")) as mock_cmd:
            success, _ = video.convert_video(src_video, "OGG")
            self.assertTrue(success)
            cmd_args = mock_cmd.call_args[0][0]
            self.assertIn("-vn", cmd_args)
            self.assertTrue("libvorbis" in cmd_args or "libopus" in cmd_args)

    # 12. MCP server tools: edge cases and schema sanity
    def test_mcp_pdf_to_images_unsupported_format(self):
        doc = self.dir_path / "doc.pdf"
        doc.touch()
        res = pdf_to_images(pdf_path=str(doc), target_format="EXE")
        self.assertFalse(res["success"])
        self.assertIn("Unsupported target image format", res["error"])

    def test_mcp_split_file_returns_only_new_files(self):
        split_dir = self.dir_path / "split_output"
        split_dir.mkdir()
        preexisting = split_dir / "old_sibling.txt"
        preexisting.write_text("old")

        doc = self.dir_path / "book.pdf"
        doc.touch()

        def fake_split_pdf(*args, **kwargs):
            (split_dir / "page_1.pdf").write_text("page 1")
            return str(split_dir)

        with patch("mcp_server.server.conv.split_pdf", side_effect=fake_split_pdf):
            res = split_file(file_path=str(doc), output_dir=str(split_dir))
            self.assertTrue(res["success"])
            self.assertEqual(res["count"], 1)
            self.assertEqual(len(res["split_files"]), 1)
            self.assertTrue(res["split_files"][0].endswith("page_1.pdf"))

    def test_mcp_perform_ocr_failure_does_not_preview(self):
        sample = self.dir_path / "sample.jpg"
        sample.touch()

        with patch("mcp_server.server.convergent_convert", return_value={"success": False, "error": "OCR engine failed"}):
            res = perform_ocr(input_path=str(sample))
            self.assertFalse(res["success"])
            self.assertIsNone(res.get("extracted_text_preview"))

    def test_list_supported_formats_categories_and_no_phantom(self):
        res = list_supported_formats()
        cats = res.get("categories", {})
        # Verify valid category IDs and names in FORMAT_REGISTRY
        self.assertIn("2", cats)  # Image
        self.assertIn("3", cats)  # Video
        self.assertIn("4", cats)  # Audio
        self.assertIn("5", cats)  # Document

        # Verify no phantom source formats exist in FORMAT_REGISTRY
        source_fmts = res.get("source_formats", [])
        self.assertNotIn("XLSX", source_fmts)
        self.assertNotIn("TYP", source_fmts)
        self.assertNotIn("EPUB", source_fmts)
        self.assertIn("PDF", source_fmts)
        self.assertIn("PNG", source_fmts)

    def test_cache_output_corruption_rejection(self):
        cache_mgr = CacheManager(db_path=self.dir_path / "cache.db")
        src = self.dir_path / "sample.jpg"
        src.write_bytes(b"image_bytes_12345")
        out = self.dir_path / "sample.png"
        out.write_bytes(b"A" * 100)
        params = {"target": "PNG"}
        cache_mgr.save(src, out, params)
        valid, msg = cache_mgr.is_cached_valid(src, out, params)
        self.assertTrue(valid)

        out.write_bytes(b"B" * 100)
        valid_corrupt, msg_corrupt = cache_mgr.is_cached_valid(src, out, params)
        self.assertFalse(valid_corrupt)
        self.assertIn("content modified", msg_corrupt)
        cache_mgr.close()

    def test_document_staging_preserves_resource_dir(self):
        from customs.file_process import process_single_file
        from Convergent import Converter
        conv = Converter()
        md_file = self.dir_path / "notes.md"
        md_file.write_text("# Notes\n![img](sub/img.png)")
        out_dir = self.dir_path / "custom_out"
        out_dir.mkdir()

        with patch.object(conv, "convert_markdown") as mock_conv_md:
            mock_conv_md.return_value = (True, "")
            process_single_file(conv, md_file, "PDF", output_dir=str(out_dir))
            self.assertTrue(mock_conv_md.called)
            self.assertEqual(mock_conv_md.call_args[1].get("resource_dir"), self.dir_path)

    def test_same_extension_video_stream_incompatibility_checks(self):
        from modules.combine import are_videos_stream_compatible
        v1 = self.dir_path / "v1.mp4"
        v2 = self.dir_path / "v2.mp4"
        v1.touch()
        v2.touch()

        info1 = {"codec": "h264", "width": 1280, "height": 720, "fps": "24/1", "pix_fmt": "yuv420p", "has_audio": True}
        info2 = {"codec": "h264", "width": 640, "height": 480, "fps": "15/1", "pix_fmt": "yuv420p", "has_audio": True}
        info3 = {"codec": "h264", "width": 1280, "height": 720, "fps": "24/1", "pix_fmt": "yuv420p", "has_audio": False}

        with patch("modules.combine.get_video_stream_info", side_effect=[info1, info2]):
            self.assertFalse(are_videos_stream_compatible([v1, v2]))

        with patch("modules.combine.get_video_stream_info", side_effect=[info1, info3]):
            self.assertFalse(are_videos_stream_compatible([v1, v2]))

        with patch("modules.combine.get_video_stream_info", side_effect=[info1, info1]):
            self.assertTrue(are_videos_stream_compatible([v1, v2]))

    def test_pdf_to_images_cleans_stale_pages(self):
        from modules import pdf_manip
        dummy_pdf = self.dir_path / "doc.pdf"
        dummy_pdf.touch()
        img_dir = self.dir_path / "doc_images"
        img_dir.mkdir()
        stale1 = img_dir / "page_001.jpg"
        stale2 = img_dir / "page_002.jpg"
        stale3 = img_dir / "page_003.jpg"
        stale1.touch()
        stale2.touch()
        stale3.touch()

        def fake_gs(cmd):
            out_patt = next((a.split("=", 1)[1] for a in cmd if a.startswith("-sOUTPUTFILE=")), None)
            if out_patt:
                p = Path(out_patt.replace("%03d", "001"))
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
            else:
                (img_dir / "page_001.jpg").touch()
            return True, ""

        with patch("modules.pdf_manip.run_command", side_effect=fake_gs):
            pdf_manip.convert_pdf_to_image(str(dummy_pdf), "jpg", output_dir=str(img_dir))
            self.assertTrue(stale1.exists())
            self.assertFalse(stale2.exists())
            self.assertFalse(stale3.exists())

    def test_decompress_archive_accurate_member_count(self):
        import zipfile
        zip_path = self.dir_path / "archive.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file1.txt", "hello")
            zf.writestr("file2.txt", "world")

        out_dir = self.dir_path / "extracted"
        out_dir.mkdir()
        unrelated = out_dir / "unrelated.txt"
        unrelated.write_text("other")

        res1 = decompress_archive(str(zip_path), output_dir=str(out_dir))
        self.assertTrue(res1["success"])
        self.assertEqual(res1["extracted_files_count"], 2)

        res2 = decompress_archive(str(zip_path), output_dir=str(out_dir))
        self.assertTrue(res2["success"])
        self.assertEqual(res2["extracted_files_count"], 2)

    def test_convergent_convert_preflight_destination_conflict(self):
        src = self.dir_path / "item.jpg"
        src.write_bytes(b"data")
        dest = self.dir_path / "existing.png"
        dest.write_bytes(b"existing_content")

        res = convergent_convert(str(src), "PNG", output_path=str(dest), overwrite=False, use_cache=False)
        self.assertFalse(res["success"])
        self.assertIn("Destination already exists", res["error"])
        self.assertEqual(res["converted_files"], [])
        self.assertEqual(dest.read_bytes(), b"existing_content")

    def test_strict_parameter_bounds_and_mode_validation(self):
        src = self.dir_path / "media.mp4"
        src.touch()

        res_w0 = resize_media(str(src), width=0)
        self.assertFalse(res_w0["success"])
        self.assertIn("Invalid width", res_w0["error"])

        res_h0 = resize_media(str(src), height=-5)
        self.assertFalse(res_h0["success"])
        self.assertIn("Invalid height", res_h0["error"])

        res_scale0 = resize_media(str(src), scale_percent=0)
        self.assertFalse(res_scale0["success"])
        self.assertIn("Invalid scale_percent", res_scale0["error"])

        res_aspect = resize_media(str(src), aspect_ratio="bad_aspect")
        self.assertFalse(res_aspect["success"])
        self.assertIn("Unsupported aspect ratio", res_aspect["error"])

        res_parts0 = split_file(str(src), num_parts=0)
        self.assertFalse(res_parts0["success"])
        self.assertIn("Invalid num_parts", res_parts0["error"])

        res_inv0 = split_file(str(src), interval=0)
        self.assertFalse(res_inv0["success"])
        self.assertIn("Invalid interval", res_inv0["error"])

        res_mode = split_file(str(src), mode="invalid_mode")
        self.assertFalse(res_mode["success"])
        self.assertIn("Invalid mode", res_mode["error"])

    def test_split_file_pdf_ranges_warning_and_rejection(self):
        pdf_file = self.dir_path / "doc.pdf"
        pdf_file.touch()

        with patch("modules.split.get_pdf_page_count", return_value=3):
            res_all_bad = split_file(str(pdf_file), ranges="bad,9-12")
            self.assertFalse(res_all_bad["success"])
            self.assertIn("No valid ranges provided", res_all_bad["error"])

        out_split = self.dir_path / "split_res"
        out_split.mkdir()
        (out_split / "part_1_1-1.pdf").touch()

        with patch("modules.split.get_pdf_page_count", return_value=3), \
             patch("mcp_server.server.conv.split_pdf", return_value=out_split):
            res_partial = split_file(str(pdf_file), ranges="1-1,bad,9-12", output_dir=str(out_split))
            self.assertTrue(res_partial["success"])
            self.assertIn("warnings", res_partial)
            self.assertEqual(len(res_partial["warnings"]), 2)

    def test_ogg_audio_extraction_supported(self):
        from customs.file_process import FORMAT_REGISTRY
        video_fmts = ["MP4", "MKV", "MOV", "AVI", "WEBM"]
        for vf in video_fmts:
            fdef = next(fd for fd in FORMAT_REGISTRY if fd.name == vf)
            self.assertIn("OGG", fdef.targets)

        dummy_vid = self.dir_path / "sample.mp4"
        dummy_vid.touch()

        with patch("mcp_server.server.convergent_convert", return_value={"success": True, "converted_files": ["sample.ogg"]}):
            res = extract_audio(str(dummy_vid), target_format="OGG")
            self.assertTrue(res["success"])

    def test_mcp_concurrency_non_blocking(self):
        import asyncio
        import time
        from mcp_server.server import mcp

        async def check_concurrency():
            task_slow = asyncio.create_task(
                mcp._tool_manager.get_tool("convergent_convert").run({
                    "input_path": str(self.dir_path / "nonexistent.jpg"),
                    "target_format": "PNG",
                })
            )
            task_fast = asyncio.create_task(
                mcp._tool_manager.get_tool("list_supported_formats").run({})
            )
            res_fast = await task_fast
            res_slow = await task_slow
            self.assertIn("format_mapping", res_fast)
            self.assertFalse(res_slow["success"])

        asyncio.run(check_concurrency())

    # 14. Robustness: PDF failure preserves existing pages (Finding 1)
    def test_pdf_to_images_failure_preserves_existing_pages(self):
        from modules import pdf_manip
        dummy_pdf = self.dir_path / "broken.pdf"
        dummy_pdf.touch()
        img_dir = self.dir_path / "preserved_images"
        img_dir.mkdir()
        existing_page = img_dir / "page_001.jpg"
        existing_page.write_text("pre-existing good image content")

        with patch("modules.pdf_manip.run_command", return_value=(False, "Ghostscript syntax error")):
            success, err = pdf_manip.convert_pdf_to_image(str(dummy_pdf), "jpg", output_dir=str(img_dir))
            self.assertFalse(success)
            self.assertTrue(existing_page.exists())
            self.assertEqual(existing_page.read_text(), "pre-existing good image content")

    # 15. Robustness: Cache invalidation on directory mtime edit & large file mtime (Finding 2)
    def test_cache_directory_manifest_mtime_invalidation(self):
        cache_mgr = CacheManager(db_path=self.dir_path / ".cache.sqlite")
        src = self.dir_path / "in.pdf"
        src.write_text("pdf-content")
        out_dir = self.dir_path / "out_pages"
        out_dir.mkdir()
        p1 = out_dir / "page_001.jpg"
        p1.write_bytes(b"image-data-1")
        params = {"target": "JPG"}

        cache_mgr.save(src, out_dir, params)
        is_valid, _ = cache_mgr.is_cached_valid(src, out_dir, params)
        self.assertTrue(is_valid)

        # Overwrite file with exact same size (zero byte replacement) but updated mtime
        time.sleep(0.01)
        p1.write_bytes(b"image-data-2")  # Same length (12 bytes)
        is_valid, reason = cache_mgr.is_cached_valid(src, out_dir, params)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "output content modified")
        cache_mgr.close()

    def test_cache_large_file_mtime_invalidation(self):
        cache_mgr = CacheManager(db_path=self.dir_path / ".cache.sqlite")
        src = self.dir_path / "in.mov"
        src.write_bytes(b"A" * 100)
        out_file = self.dir_path / "out.mp4"
        out_file.write_bytes(b"B" * (PARTIAL_THRESHOLD + 100))
        params = {"target": "MP4"}

        cache_mgr.save(src, out_file, params)
        is_valid, _ = cache_mgr.is_cached_valid(src, out_file, params)
        self.assertTrue(is_valid)

        # Touch file to change mtime
        time.sleep(0.01)
        os.utime(out_file, None)
        is_valid, reason = cache_mgr.is_cached_valid(src, out_file, params)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "output mtime changed")
        cache_mgr.close()

    # 16. Robustness: Image -auto-orient before -strip (Finding 3)
    def test_image_strip_metadata_auto_orient(self):
        from modules import image
        src_img = self.dir_path / "rotated.jpg"
        src_img.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF")

        with patch("sys.platform", "darwin"), \
             patch("shutil.which", return_value="/usr/local/bin/magick"), \
             patch("modules.image.run_command") as mock_cmd:
            # First command is sips, second is magick strip
            mock_cmd.side_effect = [(True, ""), (True, "")]
            success, _ = image.convert_image(src_img, "JPG", strip_metadata=True)
            self.assertTrue(success)
            self.assertEqual(mock_cmd.call_count, 2)
            strip_call_args = mock_cmd.call_args_list[1][0][0]
            self.assertIn("-auto-orient", strip_call_args)
            self.assertIn("-strip", strip_call_args)
            self.assertLess(strip_call_args.index("-auto-orient"), strip_call_args.index("-strip"))

    # 17. Robustness: 7z password handling & Decompress password support (Finding 4)
    def test_compress_7z_password_parameter_no_dash(self):
        f = self.dir_path / "doc.txt"
        f.write_text("data")

        with patch("modules.compress.shutil.which", return_value="/usr/local/bin/7z"), \
             patch("modules.compress.run_command") as mock_cmd:
            def fake_run(cmd, cwd=None):
                tmp_candidates = [a for a in cmd if ".tmp_" in a or a.endswith(".7z")]
                if tmp_candidates:
                    Path(tmp_candidates[0]).touch()
                return True, ""
            mock_cmd.side_effect = fake_run

            # Without password: no -p- flag
            success, _, _ = compress([f], "test.7z", "7Z", output_dir=self.dir_path)
            self.assertTrue(success)
            cmd_args = mock_cmd.call_args[0][0]
            self.assertNotIn("-p-", cmd_args)

            # With password: has -psecret
            success2, _, _ = compress([f], "test.7z", "7Z", password="secret", output_dir=self.dir_path)
            self.assertTrue(success2)
            cmd_args2 = mock_cmd.call_args[0][0]
            self.assertIn("-psecret", cmd_args2)

    def test_decompress_password_support(self):
        from modules import decompress
        dummy_zip = self.dir_path / "secure.zip"
        dummy_zip.touch()

        with patch("shutil.which", return_value="/usr/bin/unzip"), \
             patch("modules.decompress.run_command") as mock_cmd:
            mock_cmd.return_value = (True, "")
            success, _, _ = decompress.decompress(dummy_zip, output_dir=self.dir_path / "out", password="my_password")
            self.assertTrue(success)
            cmd_args = mock_cmd.call_args[0][0]
            self.assertIn("-P", cmd_args)
            self.assertEqual(cmd_args[cmd_args.index("-P") + 1], "my_password")

    # 18. Robustness: Strict argument validation rejecting typos (Finding 7)
    def test_mcp_strict_arg_validation_rejects_typos(self):
        import asyncio
        from mcp.server.fastmcp.exceptions import ToolError
        from mcp_server.server import mcp

        async def check_typo_rejection():
            tool = mcp._tool_manager.get_tool("convergent_convert")
            with self.assertRaises((ValueError, ToolError)) as cm:
                await tool.run({
                    "input_path": str(self.dir_path / "test.png"),
                    "target_format": "JPG",
                    "overwite": False,  # Typo for overwrite
                })
            self.assertIn("Unexpected argument(s)", str(cm.exception))
            self.assertIn("overwite", str(cm.exception))

        asyncio.run(check_typo_rejection())

    # 19. Robustness: Same-format conversion to distinct destination copies file (Finding 8)
    def test_same_format_distinct_destination_copies_file(self):
        from Convergent import Converter
        from customs.file_process import process_single_file
        conv = Converter()
        src_png = self.dir_path / "icon.png"
        src_png.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        dest_dir = self.dir_path / "copied_dir"

        name, success, err, _ = process_single_file(conv, src_png, "PNG", output_dir=dest_dir)
        self.assertTrue(success)
        self.assertEqual(err, "")
        self.assertTrue((dest_dir / "icon.png").exists())
        self.assertEqual((dest_dir / "icon.png").read_bytes(), src_png.read_bytes())

    # 20. Robustness: Video accurate split option (Finding 6)
    def test_split_video_accurate_option(self):
        from modules import split
        sample_vid = self.dir_path / "sample.mp4"
        sample_vid.touch()

        with patch("modules.split.get_media_duration", return_value=120.0), \
             patch("modules.split.run_command") as mock_cmd:
            mock_cmd.return_value = (True, "")

            # Default: fast stream copy (-c copy)
            split.split_video(sample_vid, mode="interval", interval=60, output_dir=self.dir_path / "split_fast", interactive=False)
            cmd_fast = mock_cmd.call_args[0][0]
            self.assertIn("-c", cmd_fast)
            self.assertEqual(cmd_fast[cmd_fast.index("-c") + 1], "copy")

            # Accurate: re-encodes, omits -c copy
            split.split_video(sample_vid, mode="interval", interval=60, output_dir=self.dir_path / "split_acc", interactive=False, accurate=True)
            cmd_acc = mock_cmd.call_args[0][0]
            self.assertNotIn("copy", cmd_acc)

    # 21. Robustness: Decompress excludes AppleDouble metadata (Finding 10)
    def test_tar_decompress_excludes_appledouble(self):
        import zipfile
        zip_path = self.dir_path / "sample.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("real.txt", "real content")
            zf.writestr("__MACOSX/._real.txt", "apple double metadata")
            zf.writestr("._real2.txt", "apple double metadata")

        res = decompress_archive(str(zip_path), output_dir=str(self.dir_path / "zip_out"))
        self.assertTrue(res["success"])
        # Should count 1 real extracted file, excluding AppleDouble and __MACOSX
        self.assertEqual(res["extracted_files_count"], 1)

    # 22. Request-scoped cancellation preserves concurrent requests
    def test_request_scoped_cancellation_preserves_concurrent_requests(self):
        from customs.run_command import set_request_context, terminate_active_processes, _REQUEST_PROCESSES
        import threading
        from unittest.mock import MagicMock

        proc_a = MagicMock()
        proc_b = MagicMock()

        # Simulate Request A
        cancel_evt_a = threading.Event()
        set_request_context("req_A", cancel_evt_a)
        _REQUEST_PROCESSES["req_A"].add(proc_a)

        # Simulate Request B
        cancel_evt_b = threading.Event()
        set_request_context("req_B", cancel_evt_b)
        _REQUEST_PROCESSES["req_B"].add(proc_b)

        # Cancel Request A only
        terminate_active_processes(request_id="req_A")

        # Process A was terminated/killed
        proc_a.terminate.assert_called_once()
        proc_a.kill.assert_called_once()

        # Process B was NOT touched!
        proc_b.terminate.assert_not_called()
        proc_b.kill.assert_not_called()

        # Clean up
        _REQUEST_PROCESSES.clear()
        set_request_context(None, None)

    # 23. Split loop stops subsequent segments upon cancellation
    def test_split_loop_stops_subsequent_segments_on_cancellation(self):
        from modules import split
        from customs.run_command import set_request_context
        import threading

        sample_vid = self.dir_path / "cancel_loop.mp4"
        sample_vid.touch()

        cancel_evt = threading.Event()
        set_request_context("test_cancel", cancel_evt)

        call_count = [0]
        def fake_run(cmd, cwd=None):
            call_count[0] += 1
            # Signal cancellation on first part
            cancel_evt.set()
            return True, ""

        with patch("modules.split.get_media_duration", return_value=120.0), \
             patch("modules.split.run_command", side_effect=fake_run):
            split.split_video(sample_vid, mode="parts", num_parts=5, output_dir=self.dir_path / "cancel_out", interactive=False)

        # Loop must stop after part 1, NOT proceed to 5 parts!
        self.assertEqual(call_count[0], 1)
        set_request_context(None, None)

    # 24. PDF publication directory collision aborts without deleting existing pages
    def test_pdf_publication_directory_collision_preserves_pages(self):
        from modules import pdf_manip
        src = self.dir_path / "book.pdf"
        src.write_text("dummy-pdf")
        out_dir = self.dir_path / "book_images"
        out_dir.mkdir()

        p1 = out_dir / "page_001.jpg"
        p1.write_text("original page 1")
        # page_002.jpg is a directory containing sentinel
        p2_dir = out_dir / "page_002.jpg"
        p2_dir.mkdir()
        (p2_dir / "sentinel.txt").write_text("sentinel content")

        with patch("modules.pdf_manip.run_command") as mock_cmd:
            def fake_gs(cmd, cwd=None):
                # Ghostscript succeeds and writes 2 pages into staging
                for part in cmd:
                    if "-sOUTPUTFILE=" in part:
                        pat = part.split("-sOUTPUTFILE=")[1]
                        staging_p1 = Path(pat.replace("%03d", "001"))
                        staging_p2 = Path(pat.replace("%03d", "002"))
                        staging_p1.parent.mkdir(parents=True, exist_ok=True)
                        staging_p1.write_text("new page 1")
                        staging_p2.write_text("new page 2")
                return True, ""
            mock_cmd.side_effect = fake_gs

            success, err = pdf_manip.convert_pdf_to_image(src, "JPG", output_dir=out_dir)
            self.assertFalse(success)
            self.assertIn("Destination conflict", err)
            # p1 original file must still be intact!
            self.assertTrue(p1.exists())
            self.assertEqual(p1.read_text(), "original page 1")
            # Sentinel inside p2_dir must also survive
            self.assertTrue((p2_dir / "sentinel.txt").exists())

    # 25. Fresh conversion reports cached=False and repeat reports cached=True
    def test_fresh_conversion_reports_cached_false_and_repeat_reports_cached_true(self):
        src_img = self.dir_path / "raw.png"
        src_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        out_target = self.dir_path / "fresh_out.jpg"

        def fake_make_out(conv, f, target_fmt, *args, **kwargs):
            out_d = kwargs.get("output_dir") or f.parent
            out_f = Path(out_d) / f"{f.stem}.{target_fmt.lower()}"
            out_f.write_bytes(b"converted-jpg")
            return (f.name, True, "", 0.01)

        with patch("customs.file_process.process_single_file", side_effect=fake_make_out):
            res1 = convergent_convert(
                input_path=str(src_img),
                target_format="JPG",
                output_path=str(out_target),
                overwrite=True,
                use_cache=True,
            )
            self.assertTrue(res1["success"])
            # Fresh conversion must NOT be reported as cached!
            self.assertFalse(res1.get("cached", False))

            # Repeat conversion with identical output in place must be reported as cached
            res2 = convergent_convert(
                input_path=str(src_img),
                target_format="JPG",
                output_path=str(out_target),
                overwrite=True,
                use_cache=True,
            )
            self.assertTrue(res2["success"])
            self.assertTrue(res2.get("cached", False))

    # 26. Parameter validation: dpi, md_pdf_mode, bitrate
    def test_parameter_validations(self):
        src_f = self.dir_path / "test_doc.md"
        src_f.write_text("# Hello")

        # dpi <= 0 rejection
        res_dpi = convergent_convert(str(src_f), "PDF", dpi=0)
        self.assertFalse(res_dpi["success"])
        self.assertIn("positive integer", res_dpi["error"])

        # invalid md_pdf_mode
        res_mode = convergent_convert(str(src_f), "PDF", md_pdf_mode="invalid_engine")
        self.assertFalse(res_mode["success"])
        self.assertIn("Allowed modes", res_mode["error"])

        # invalid bitrate string
        res_br = convergent_convert(str(src_f), "MP3", bitrate="nonsense")
        self.assertFalse(res_br["success"])
        self.assertIn("Invalid bitrate", res_br["error"])

    # 27. Bitrate normalization: "256000" and "256k"
    def test_bitrate_normalization(self):
        from modules import audio
        src_wav = self.dir_path / "clip.wav"
        src_wav.touch()

        with patch("modules.audio.run_command") as mock_cmd:
            mock_cmd.return_value = (True, "")

            # "256000" raw bps -> normalized to 256k
            success, _ = audio.convert_audio(src_wav, "MP3", bitrate="256000")
            self.assertTrue(success)
            cmd1 = mock_cmd.call_args[0][0]
            self.assertIn("256k", cmd1)
            self.assertNotIn("256000k", cmd1)

            # "256k" stays 256k
            success2, _ = audio.convert_audio(src_wav, "MP3", bitrate="256k")
            self.assertTrue(success2)
            cmd2 = mock_cmd.call_args[0][0]
            self.assertIn("256k", cmd2)

    # 28. Split file reports partial_success and failed_parts
    def test_split_file_reports_partial_success(self):
        from Convergent import Converter
        sample_vid = self.dir_path / "split_partial.mp4"
        sample_vid.touch()

        from modules import split
        # Simulate part 2 failure in split
        def fake_split(p, **kwargs):
            out_d = self.dir_path / "partial_out"
            out_d.mkdir(parents=True, exist_ok=True)
            (out_d / "part_001.mp4").touch()
            split.LAST_SPLIT_FAILED_PARTS = [{"part": 2, "error": "Destination was a directory"}]
            return out_d

        with patch.object(Converter, "split_video", side_effect=fake_split):
            res = split_file(str(sample_vid), mode="parts", num_parts=2)
            self.assertTrue(res["success"])
            self.assertTrue(res.get("partial_success", False))
            self.assertEqual(len(res.get("failed_parts", [])), 1)
            self.assertEqual(res["failed_parts"][0]["part"], 2)
            self.assertIn("warnings", res)


if __name__ == "__main__":
    unittest.main()

