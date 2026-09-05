import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Convergent import Converter
from customs import shortcut


class TestCLIFlow(unittest.TestCase):
    def setUp(self):
        self.conv = Converter()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_inspect_paths_single_file(self):
        f = self.test_dir / "video.mp4"
        f.touch()
        has_file, has_dir, exts = shortcut.inspect_paths([str(f)])
        self.assertTrue(has_file)
        self.assertFalse(has_dir)
        self.assertEqual(exts, {"mp4"})

    def test_inspect_paths_compound_archive(self):
        f = self.test_dir / "archive.tar.gz"
        f.touch()
        has_file, has_dir, exts = shortcut.inspect_paths([str(f)])
        self.assertTrue(has_file)
        self.assertFalse(has_dir)
        self.assertIn("tar.gz", exts)

    def test_inspect_paths_directory(self):
        f1 = self.test_dir / "image.jpg"
        f2 = self.test_dir / "doc.pdf"
        f1.touch()
        f2.touch()
        has_file, has_dir, exts = shortcut.inspect_paths([str(self.test_dir)])
        self.assertFalse(has_file)
        self.assertTrue(has_dir)
        self.assertEqual(exts, {"jpg", "pdf"})

    def test_applicable_entries_for_mp4_file(self):
        f = self.test_dir / "test.mp4"
        f.touch()
        entries = shortcut.get_applicable_menu_entries(self.conv, [str(f)])
        operations = [e["operation"] for e in entries]

        # MP4 should support Combine, Split, Resize, Video Convert, Compress, STT
        self.assertIn("combine", operations)
        self.assertIn("split", operations)
        self.assertIn("resize", operations)
        self.assertIn("convert", operations)
        self.assertIn("compress", operations)
        self.assertIn("stt", operations)

        # Should NOT support Decompress, OCR
        self.assertNotIn("decompress", operations)
        self.assertNotIn("ocr", operations)

        # Consecutive 0-based indexing
        expected_keys = [str(i) for i in range(len(entries))]
        actual_keys = [e["key"] for e in entries]
        self.assertEqual(actual_keys, expected_keys)

    def test_applicable_entries_for_heic_file(self):
        f = self.test_dir / "photo.heic"
        f.touch()
        entries = shortcut.get_applicable_menu_entries(self.conv, [str(f)])
        operations = [e["operation"] for e in entries]

        # HEIC should support Resize, Image Convert, Compress, OCR
        self.assertIn("resize", operations)
        self.assertIn("convert", operations)
        self.assertIn("compress", operations)
        self.assertIn("ocr", operations)

        # Should NOT support Combine, Split, Video, Audio, Decompress, STT
        self.assertNotIn("combine", operations)
        self.assertNotIn("split", operations)
        self.assertNotIn("decompress", operations)
        self.assertNotIn("stt", operations)

        # Consecutive 0-based indexing
        expected_keys = [str(i) for i in range(len(entries))]
        actual_keys = [e["key"] for e in entries]
        self.assertEqual(actual_keys, expected_keys)

    def test_applicable_entries_for_folder_excludes_split_and_decompress(self):
        f = self.test_dir / "video.mp4"
        f.touch()
        entries = shortcut.get_applicable_menu_entries(self.conv, [str(self.test_dir)])
        operations = [e["operation"] for e in entries]

        # Split and Decompress are strictly file-only!
        self.assertNotIn("split", operations)
        self.assertNotIn("decompress", operations)

        # Folder operations should include Combine, Resize, Video Convert, Compress, STT
        self.assertIn("combine", operations)
        self.assertIn("resize", operations)
        self.assertIn("convert", operations)
        self.assertIn("compress", operations)
        self.assertIn("stt", operations)

        # Consecutive 0-based indexing
        expected_keys = [str(i) for i in range(len(entries))]
        actual_keys = [e["key"] for e in entries]
        self.assertEqual(actual_keys, expected_keys)

    def test_applicable_entries_for_archive_file(self):
        f = self.test_dir / "archive.zip"
        f.touch()
        entries = shortcut.get_applicable_menu_entries(self.conv, [str(f)])
        operations = [e["operation"] for e in entries]

        self.assertIn("compress", operations)
        self.assertIn("decompress", operations)
        self.assertNotIn("split", operations)
        self.assertNotIn("combine", operations)
        self.assertNotIn("resize", operations)

        expected_keys = [str(i) for i in range(len(entries))]
        actual_keys = [e["key"] for e in entries]
        self.assertEqual(actual_keys, expected_keys)

    def test_applicable_entries_unknown_format(self):
        f = self.test_dir / "data.xyz"
        f.touch()
        entries = shortcut.get_applicable_menu_entries(self.conv, [str(f)])
        # Unknown/unsupported formats should return no applicable entries
        self.assertEqual(entries, [])

    def test_unsupported_format_guardrail(self):
        from unittest.mock import patch
        from io import StringIO
        from rich.console import Console
        import Convergent

        out_io = StringIO()
        test_console = Console(file=out_io, force_terminal=False)

        f = self.test_dir / "unknown.xyz"
        f.touch()

        # Input unsupported file -> guardrail prompts retry -> enter 'q' to exit
        input_responses = [str(f), "q"]

        with patch("Convergent.console", test_console), \
             patch("Convergent.clear_screen"), \
             patch("Convergent.flush_stdin"), \
             patch("Convergent.get_input", side_effect=input_responses), \
             patch("Convergent.get_char"), \
             patch("customs.shortcut.load_shortcuts", return_value={}), \
             patch("Convergent.load_failed_run", return_value=None), \
             patch("sys.argv", ["Convergent.py"]):
            Convergent.main()

        output = out_io.getvalue()
        self.assertIn("Oops sorry! This file format (.xyz) is not supported.", output)
        self.assertIn("Try another file (or Q to Quit):", output)
        self.assertIn("Exiting...", output)

    def test_empty_folder_guardrail(self):
        from unittest.mock import patch
        from io import StringIO
        from rich.console import Console
        import Convergent

        out_io = StringIO()
        test_console = Console(file=out_io, force_terminal=False)

        empty_d = self.test_dir / "empty_dir"
        empty_d.mkdir()

        input_responses = [str(empty_d), "q"]

        with patch("Convergent.console", test_console), \
             patch("Convergent.clear_screen"), \
             patch("Convergent.flush_stdin"), \
             patch("Convergent.get_input", side_effect=input_responses), \
             patch("Convergent.get_char"), \
             patch("customs.shortcut.load_shortcuts", return_value={}), \
             patch("Convergent.load_failed_run", return_value=None), \
             patch("sys.argv", ["Convergent.py"]):
            Convergent.main()

        output = out_io.getvalue()
        self.assertIn("Oops sorry! This folder is empty.", output)
        self.assertIn("Try another file (or Q to Quit):", output)
        self.assertIn("Exiting...", output)

    def test_folder_with_no_supported_formats_guardrail(self):
        from unittest.mock import patch
        from io import StringIO
        from rich.console import Console
        import Convergent

        out_io = StringIO()
        test_console = Console(file=out_io, force_terminal=False)

        folder = self.test_dir / "folder_xyz"
        folder.mkdir()
        (folder / "file.xyz").touch()

        input_responses = [str(folder), "q"]

        with patch("Convergent.console", test_console), \
             patch("Convergent.clear_screen"), \
             patch("Convergent.flush_stdin"), \
             patch("Convergent.get_input", side_effect=input_responses), \
             patch("Convergent.get_char"), \
             patch("customs.shortcut.load_shortcuts", return_value={}), \
             patch("Convergent.load_failed_run", return_value=None), \
             patch("sys.argv", ["Convergent.py"]):
            Convergent.main()

        output = out_io.getvalue()
        self.assertIn("Oops sorry! No supported files found in this folder (.xyz).", output)
        self.assertIn("Try another file (or Q to Quit):", output)
        self.assertIn("Exiting...", output)

    def test_guardrail_retry_with_valid_file(self):
        from unittest.mock import patch
        from io import StringIO
        from rich.console import Console
        import Convergent

        out_io = StringIO()
        test_console = Console(file=out_io, force_terminal=False)

        bad_file = self.test_dir / "bad.xyz"
        bad_file.touch()
        good_file = self.test_dir / "good.mp4"
        good_file.touch()

        # Enter bad file -> at retry prompt enter good file -> on Screen 2 hit 'b' -> on Screen 1 hit 'q'
        input_responses = [str(bad_file), str(good_file), "q"]
        char_responses = ["b"]

        with patch("Convergent.console", test_console), \
             patch("Convergent.clear_screen"), \
             patch("Convergent.flush_stdin"), \
             patch("Convergent.get_input", side_effect=input_responses), \
             patch("Convergent.get_char", side_effect=char_responses), \
             patch("customs.shortcut.load_shortcuts", return_value={}), \
             patch("Convergent.load_failed_run", return_value=None), \
             patch("sys.argv", ["Convergent.py"]):
            Convergent.main()

        output = out_io.getvalue()
        self.assertIn("Oops sorry! This file format (.xyz) is not supported.", output)
        self.assertIn("Detected: good.mp4", output)

    def test_interactive_main_flow(self):
        from unittest.mock import patch
        from io import StringIO
        from rich.console import Console
        import Convergent

        out_io = StringIO()
        test_console = Console(file=out_io, force_terminal=False)

        f = self.test_dir / "sample.mp4"
        f.touch()

        # Input path on Screen 1 -> on Screen 2 hit 'b' -> on Screen 1 hit 'q'
        input_responses = [str(f), "q"]
        char_responses = ["b"]

        with patch("Convergent.console", test_console), \
             patch("Convergent.clear_screen"), \
             patch("Convergent.flush_stdin"), \
             patch("Convergent.get_input", side_effect=input_responses), \
             patch("Convergent.get_char", side_effect=char_responses), \
             patch("customs.shortcut.load_shortcuts", return_value={}), \
             patch("Convergent.load_failed_run", return_value=None), \
             patch("sys.argv", ["Convergent.py"]):
            Convergent.main()

        output = out_io.getvalue()
        self.assertIn("Convergent", output)
        self.assertIn("Enter file or folder path(s) to continue:", output)
        self.assertIn("Detected: sample.mp4", output)
        self.assertIn("Convert from:", output)
        self.assertIn("(Other choices are hidden based on detected file format)", output)
        self.assertIn("0. Combine:", output)
        self.assertIn("1. Split:", output)
        self.assertIn("2. Resize:", output)
        self.assertIn("3. Video:", output)
        self.assertIn("4. Compress:", output)
        self.assertIn("5. STT:", output)
        self.assertNotIn("Decompress:", output)
        self.assertNotIn("OCR:", output)

    def test_same_format_strip_metadata(self):
        from unittest.mock import patch
        from customs.file_process import process_single_file

        img_file = self.test_dir / "sample.jpg"
        img_file.write_bytes(b"dummy image content")

        # 1. Without strip_metadata: should skip
        name, success, msg, dur = process_single_file(self.conv, img_file, "JPG", strip_metadata=False)
        self.assertTrue(success)
        self.assertEqual(msg, "Skipped (Same format)")
        self.assertTrue(img_file.exists())

        # 2. With strip_metadata: should NOT skip, should call convert_image
        with patch.object(self.conv, "convert_image", return_value=(True, "")) as mock_convert:
            name, success, msg, dur = process_single_file(self.conv, img_file, "JPG", strip_metadata=True)
            self.assertTrue(success)
            self.assertEqual(msg, "")
            self.assertTrue(img_file.exists())
            mock_convert.assert_called_once_with(
                img_file, "JPG", fps=None, bitrate=None, md_pdf_mode=None, strip_metadata=True,
                ocr=False, stt=False, model="base", language=None, hwaccel="auto", dpi=None
            )


if __name__ == "__main__":
    unittest.main()
