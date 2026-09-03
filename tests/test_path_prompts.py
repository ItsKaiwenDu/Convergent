import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Convergent import prompt_paths
from customs import shortcut
from rich.console import Console


class TestPathPrompts(unittest.TestCase):
    def test_prompt_paths_file_or_folder(self):
        output_io = StringIO()
        test_console = Console(file=output_io, force_terminal=False)

        with patch("Convergent.console", test_console), \
             patch("Convergent.get_input", return_value="/path/to/test"), \
             patch("Convergent.flush_stdin"):
            paths = prompt_paths("convert", allow_folders=True)

        self.assertEqual(paths, ["/path/to/test"])
        output = output_io.getvalue()
        self.assertIn("Enter file or folder path(s) to convert:", output)
        self.assertIn("(Tip: You can either paste or drag and drop here)", output)

    def test_prompt_paths_file_only(self):
        output_io = StringIO()
        test_console = Console(file=output_io, force_terminal=False)

        with patch("Convergent.console", test_console), \
             patch("Convergent.get_input", return_value="/path/to/doc.pdf"), \
             patch("Convergent.flush_stdin"):
            paths = prompt_paths("split", allow_folders=False)

        self.assertEqual(paths, ["/path/to/doc.pdf"])
        output = output_io.getvalue()
        self.assertIn("Enter file path(s) to split:", output)
        self.assertNotIn("folder", output)
        self.assertIn("(Tip: You can either paste or drag and drop here)", output)

    def test_all_action_formats(self):
        actions = [
            ("combine", True, "Enter file or folder path(s) to combine:"),
            ("split", False, "Enter file path(s) to split:"),
            ("resize", True, "Enter file or folder path(s) to resize:"),
            ("compress", True, "Enter file or folder path(s) to compress:"),
            ("decompress", False, "Enter file path(s) to decompress:"),
            ("OCR", True, "Enter file or folder path(s) to OCR:"),
            ("transcribe (STT)", True, "Enter file or folder path(s) to transcribe (STT):"),
            ("convert", True, "Enter file or folder path(s) to convert:"),
        ]

        for action, allow_folders, expected_header in actions:
            output_io = StringIO()
            test_console = Console(file=output_io, force_terminal=False)
            with patch("Convergent.console", test_console), \
                 patch("Convergent.get_input", return_value="foo.txt"), \
                 patch("Convergent.flush_stdin"):
                prompt_paths(action, allow_folders=allow_folders)
            output = output_io.getvalue()
            self.assertIn(expected_header, output)

    def test_shortcut_resolve_paths_prompts(self):
        test_cases = [
            ({"operation": "split"}, "Enter file path(s) to split:"),
            ({"operation": "decompress"}, "Enter file path(s) to decompress:"),
            ({"operation": "combine"}, "Enter file or folder path(s) to combine:"),
            ({"operation": "convert"}, "Enter file or folder path(s) to convert:"),
            ({"operation": "ocr"}, "Enter file or folder path(s) to OCR:"),
            ({"operation": "stt"}, "Enter file or folder path(s) to transcribe (STT):"),
        ]

        for sc, expected_header in test_cases:
            output_io = StringIO()
            test_console = Console(file=output_io, force_terminal=False)
            paths = shortcut._resolve_shortcut_paths(
                sc,
                paths=None,
                interactive=True,
                console=test_console,
                get_input=lambda p: "sample.txt",
                flush_stdin=lambda: None,
                clean_paths=lambda x: [x] if x else [],
            )
            self.assertEqual(paths, ["sample.txt"])
            output = output_io.getvalue()
            self.assertIn(expected_header, output)
            self.assertIn("(Tip: You can either paste or drag and drop here)", output)


if __name__ == "__main__":
    unittest.main()
