import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from rich.console import Console

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Convergent import Converter, clean_paths
from customs.file_process import (
    FORMAT_REGISTRY,
    get_expected_output_path,
    process_single_file,
    save_failed_run,
    load_failed_run,
    clear_failed_run,
    process,
)


class TestFileProcess(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.console = Console(file=StringIO(), force_terminal=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_paths_empty(self):
        self.assertEqual(clean_paths(""), [])
        self.assertEqual(clean_paths(None), [])
        self.assertEqual(clean_paths([]), [])

    def test_clean_paths_stdin(self):
        self.assertEqual(clean_paths("-"), ["-"])

    def test_clean_paths_quoted_and_spaces(self):
        # Existing file with space in path
        test_file = self.dir_path / "My Photo 2026.jpg"
        test_file.write_bytes(b"data")
        self.assertEqual(clean_paths(str(test_file)), [str(test_file)])

        # Quoted strings
        raw = f"'{self.dir_path}/a.jpg' '{self.dir_path}/b.jpg'"
        cleaned = clean_paths(raw)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(cleaned[0], f"{self.dir_path}/a.jpg")
        self.assertEqual(cleaned[1], f"{self.dir_path}/b.jpg")

    def test_format_registry_integrity(self):
        conv = Converter()
        self.assertGreater(len(FORMAT_REGISTRY), 20)

        for fd in FORMAT_REGISTRY:
            self.assertEqual(fd.name, fd.name.upper(), f"Format name {fd.name} should be uppercase")
            self.assertIn(fd.category_id, ["2", "3", "4", "5"], f"Invalid category ID for {fd.name}")
            self.assertGreater(len(fd.targets), 0, f"Targets should not be empty for {fd.name}")
            # Ensure handler method exists on Converter
            self.assertTrue(
                hasattr(conv, fd.handler_method),
                f"Converter is missing handler method '{fd.handler_method}' for {fd.name}"
            )

    def test_expected_output_path_resolution(self):
        pdf_file = self.dir_path / "report.pdf"
        img_file = self.dir_path / "photo.jpg"

        # PDF -> Image outputs to _images folder
        self.assertEqual(
            get_expected_output_path(pdf_file, "JPG"),
            self.dir_path / "report_images"
        )
        self.assertEqual(
            get_expected_output_path(pdf_file, "PNG"),
            self.dir_path / "report_images"
        )

        # PDF -> OCR (TXT/MD/DOCX) outputs to a single file
        self.assertEqual(
            get_expected_output_path(pdf_file, "TXT"),
            self.dir_path / "report.txt"
        )
        self.assertEqual(
            get_expected_output_path(pdf_file, "MD"),
            self.dir_path / "report.md"
        )
        self.assertEqual(
            get_expected_output_path(pdf_file, "DOCX"),
            self.dir_path / "report.docx"
        )

        # Standard file conversion
        self.assertEqual(
            get_expected_output_path(img_file, "PNG"),
            self.dir_path / "photo.png"
        )

    def test_failed_run_lifecycle(self):
        test_failed_file = self.dir_path / ".convergent_failed.json"
        with patch("customs.file_process.FAILED_RUN_FILE", test_failed_file):
            # Initially none
            self.assertIsNone(load_failed_run())

            # Save failed run
            failed_p1 = self.dir_path / "f1.jpg"
            failed_p2 = self.dir_path / "f2.jpg"
            failed_p1.touch()
            failed_p2.touch()

            save_failed_run(
                failed_files=[failed_p1, failed_p2],
                source_formats=["JPG"],
                target_format="PNG",
                fps=30,
                bitrate="192k",
                strip_metadata=True,
                use_cache=True,
            )

            loaded = load_failed_run()
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded["paths"]), 2)
            self.assertEqual(loaded["target_format"], "PNG")
            self.assertEqual(loaded["fps"], 30)
            self.assertEqual(loaded["bitrate"], "192k")
            self.assertTrue(loaded["strip_metadata"])
            self.assertTrue(loaded["use_cache"])

            # Clear
            clear_failed_run()
            self.assertIsNone(load_failed_run())
            self.assertFalse(test_failed_file.exists())

    def test_process_single_file_unsupported_target(self):
        conv = Converter()
        src_file = self.dir_path / "test.docx"
        src_file.touch()

        # DOCX only converts to PDF
        fname, success, err, dur = process_single_file(conv, src_file, "MP4")
        self.assertFalse(success)
        self.assertIn("Target MP4 not supported for DOCX", err)
        self.assertGreaterEqual(dur, 0.0)

    def test_process_single_file_same_format(self):
        conv = Converter()
        src_file = self.dir_path / "test.png"
        src_file.touch()

        fname, success, msg, dur = process_single_file(conv, src_file, "PNG")
        self.assertTrue(success)
        self.assertIn("Skipped (Same format)", msg)

    def test_process_single_file_with_mock_handler(self):
        conv = MagicMock()
        conv.formats = {"JPG": ["PNG"]}
        conv.convert_image.return_value = (True, "")

        src_file = self.dir_path / "test.jpg"
        src_file.touch()

        fname, success, err, dur = process_single_file(conv, src_file, "PNG", strip_metadata=True)
        self.assertTrue(success)
        self.assertEqual(err, "")
        conv.convert_image.assert_called_once()

    def test_process_batch_discovery_and_cache(self):
        conv = MagicMock()
        conv.formats = {"JPG": ["PNG"]}
        conv.convert_image.return_value = (True, "")

        f1 = self.dir_path / "1.jpg"
        f2 = self.dir_path / "2.jpg"
        f_other = self.dir_path / "readme.txt"
        f1.write_bytes(b"image 1")
        f2.write_bytes(b"image 2")
        f_other.write_bytes(b"text")

        def mock_get_char():
            return "1"

        # Batch process without cache
        res = process(
            conv=conv,
            console=self.console,
            get_char=mock_get_char,
            source_formats=["JPG"],
            target_format="PNG",
            paths=[str(self.dir_path)],
            overwrite=True,
            use_cache=False,
            interactive=False,
        )

        self.assertEqual(len(res), 2)
        out_names = [p.name for p in res]
        self.assertIn("1.png", out_names)
        self.assertIn("2.png", out_names)

    def test_collision_policy_skip(self):
        conv = MagicMock()
        conv.formats = {"JPG": ["PNG"]}

        src_file = self.dir_path / "photo.jpg"
        existing_out = self.dir_path / "photo.png"
        src_file.write_bytes(b"jpg content")
        existing_out.write_bytes(b"existing png content")

        def mock_get_char():
            return "s"

        res = process(
            conv=conv,
            console=self.console,
            get_char=mock_get_char,
            source_formats=["JPG"],
            target_format="PNG",
            paths=[str(src_file)],
            overwrite=False,
            skip=True,
            use_cache=False,
            interactive=False,
        )

        # Existing output was skipped, no conversion performed
        self.assertEqual(res, [])
        self.assertEqual(existing_out.read_bytes(), b"existing png content")
        conv.convert_image.assert_not_called()

    def test_collision_policy_overwrite(self):
        conv = MagicMock()
        conv.formats = {"JPG": ["PNG"]}

        src_file = self.dir_path / "photo.jpg"
        existing_out = self.dir_path / "photo.png"
        src_file.write_bytes(b"jpg content")
        existing_out.write_bytes(b"old content")

        def mock_convert(src, target_ext, **kwargs):
            existing_out.write_bytes(b"new overwritten content")
            return True, ""

        conv.convert_image.side_effect = mock_convert

        def mock_get_char():
            return "o"

        res = process(
            conv=conv,
            console=self.console,
            get_char=mock_get_char,
            source_formats=["JPG"],
            target_format="PNG",
            paths=[str(src_file)],
            overwrite=True,
            skip=False,
            use_cache=False,
            interactive=False,
        )

        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], existing_out)
        self.assertEqual(existing_out.read_bytes(), b"new overwritten content")

    def test_pdf_ocr_batch_output_discovery(self):
        conv = MagicMock()
        conv.formats = {"PDF": ["TXT", "MD", "DOCX", "JPG", "PNG"]}

        src_pdf = self.dir_path / "scan.pdf"
        src_pdf.write_bytes(b"%PDF-1.4 dummy")
        expected_txt = self.dir_path / "scan.txt"

        def mock_convert_pdf(src, target_ext, **kwargs):
            expected_txt.write_text("Extracted OCR text")
            return True, ""

        conv.convert_pdf.side_effect = mock_convert_pdf

        def mock_get_char():
            return "1"

        res = process(
            conv=conv,
            console=self.console,
            get_char=mock_get_char,
            source_formats=["PDF"],
            target_format="TXT",
            paths=[str(src_pdf)],
            overwrite=True,
            use_cache=False,
            interactive=False,
            ocr=True,
        )

        self.assertEqual(len(res), 1)
        # Must discover scan.txt and NOT scan_images
        self.assertEqual(res[0], expected_txt)
        self.assertTrue(expected_txt.exists())


if __name__ == "__main__":
    unittest.main()
