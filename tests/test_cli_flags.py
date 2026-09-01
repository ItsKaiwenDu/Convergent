import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Convergent import build_parser, Converter


class TestCLIFlags(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()
        self.conv = Converter()

    def test_default_flags(self):
        args = self.parser.parse_args([])
        self.assertFalse(args.no_cache)
        self.assertIsNone(args.cache_ttl)
        self.assertFalse(args.overwrite)
        self.assertFalse(args.skip)
        self.assertFalse(args.strip_metadata)
        self.assertEqual(args.hwaccel, "auto")
        self.assertEqual(args.model, "base")
        self.assertEqual(args.md_pdf_mode, "formatted")
        self.assertFalse(args.mcp)
        self.assertFalse(args.resume)
        self.assertFalse(args.stt)
        self.assertIsNone(args.shortcut_key)
        self.assertIsNone(args.dpi)

    def test_custom_flags_parsing(self):
        args = self.parser.parse_args([
            "--from", "JPG",
            "--to", "PNG",
            "--path", "/path/to/img.jpg",
            "--jobs", "4",
            "--overwrite",
            "--strip-metadata",
            "--dpi", "300",
            "--no-cache",
            "--cache-ttl", "14.5",
        ])
        self.assertEqual(args.from_fmt, "JPG")
        self.assertEqual(args.to_fmt, "PNG")
        self.assertEqual(args.path, ["/path/to/img.jpg"])
        self.assertEqual(args.jobs, 4)
        self.assertTrue(args.overwrite)
        self.assertTrue(args.strip_metadata)
        self.assertEqual(args.dpi, 300)
        self.assertTrue(args.no_cache)
        self.assertEqual(args.cache_ttl, 14.5)

    def test_force_alias_flag(self):
        args = self.parser.parse_args(["--force"])
        self.assertTrue(args.no_cache)

    def test_mcp_flag_parsing(self):
        args = self.parser.parse_args(["--mcp"])
        self.assertTrue(args.mcp)

    def test_resume_flag_parsing(self):
        args = self.parser.parse_args(["--resume"])
        self.assertTrue(args.resume)

    def test_stt_flags_parsing(self):
        args = self.parser.parse_args([
            "--from", "MP4",
            "--to", "TXT",
            "--stt",
            "--model", "turbo",
            "--language", "en",
        ])
        self.assertTrue(args.stt)
        self.assertEqual(args.model, "turbo")
        self.assertEqual(args.language, "en")

    def test_invalid_choices(self):
        with self.assertRaises(SystemExit):
            with patch("sys.stderr"):
                self.parser.parse_args(["--hwaccel", "invalid_accel"])

        with self.assertRaises(SystemExit):
            with patch("sys.stderr"):
                self.parser.parse_args(["--model", "invalid_model"])

        with self.assertRaises(SystemExit):
            with patch("sys.stderr"):
                self.parser.parse_args(["--md-pdf-mode", "invalid_mode"])

    def test_converter_categories_and_formats(self):
        self.assertIn("2", self.conv.categories)
        self.assertIn("3", self.conv.categories)
        self.assertIn("4", self.conv.categories)
        self.assertIn("5", self.conv.categories)

        self.assertEqual(self.conv.categories["2"]["name"], "Image")
        self.assertEqual(self.conv.categories["3"]["name"], "Video")
        self.assertEqual(self.conv.categories["4"]["name"], "Audio")
        self.assertEqual(self.conv.categories["5"]["name"], "Document")

        # Formats should be populated and mapped correctly
        self.assertIn("JPG", self.conv.formats)
        self.assertIn("MP4", self.conv.formats)
        self.assertIn("MP3", self.conv.formats)
        self.assertIn("PDF", self.conv.formats)


if __name__ == "__main__":
    from unittest.mock import patch
    unittest.main()
