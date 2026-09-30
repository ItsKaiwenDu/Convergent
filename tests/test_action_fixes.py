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
                tmp_out = Path(cmd[3])
                tmp_out.touch()
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
            self.assertIn("-p-", cmd_args)

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

        with patch.object(conv, "convert_image", side_effect=fake_convert_image):
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
            self.assertEqual(cwd_arg, str(self.dir_path))

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
            self.assertIn("libvorbis", cmd_args)

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


if __name__ == "__main__":
    unittest.main()
