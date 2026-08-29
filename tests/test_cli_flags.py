import argparse
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Convergent import Converter


def build_arg_parser():
    """Reconstructs the CLI parser from Convergent.py for testing flag combinations."""
    parser = argparse.ArgumentParser(description="Convergent: Local File Converter")
    parser.add_argument("--from", dest="from_fmt", help="Source format")
    parser.add_argument("--to", dest="to_fmt", help="Target format")
    parser.add_argument("--fps", help="Frames per second")
    parser.add_argument("--bitrate", help="Audio bitrate")
    parser.add_argument("--md-pdf-mode", choices=["formatted", "raw"], default="formatted")
    parser.add_argument("--path", nargs="+", help="Path to file or directory")
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--jobs", "-j", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip", action="store_true")
    parser.add_argument("--strip-metadata", action="store_true")
    parser.add_argument("--dpi", type=int, default=None)
    parser.add_argument("--stt", action="store_true")
    parser.add_argument("--model", default="base", choices=["standard", "mini", "medium", "large", "tiny", "base", "small", "turbo", "large-v3-turbo"])
    parser.add_argument("--language", default=None)
    parser.add_argument("--hwaccel", choices=["auto", "videotoolbox", "nvenc", "qsv", "none"], default="auto")
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--no-cache", "--force", action="store_true", dest="no_cache")
    parser.add_argument("--cache-ttl", type=float, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--shortcut", dest="shortcut_key")
    parser.add_argument("--mcp", action="store_true")
    return parser


class TestCLIFlags(unittest.TestCase):
    def setUp(self):
        self.parser = build_arg_parser()
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
    unittest.main()
