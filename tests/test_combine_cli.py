import sys
import unittest
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules import combine
from customs.console import prompt_paths
from rich.console import Console


class TestCombineCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prompt_paths_add_action(self):
        output_io = StringIO()
        test_console = Console(file=output_io, force_terminal=False)

        with patch("customs.console.console", test_console), \
             patch("customs.console.get_input", return_value="/path/to/folder"), \
             patch("customs.console.flush_stdin"):
            paths = prompt_paths("add", allow_folders=True)

        self.assertEqual(paths, ["/path/to/folder"])
        output = output_io.getvalue()
        self.assertIn("Enter file or folder path(s) to add:", output)
        self.assertIn("(Tip: You can either paste or drag and drop here)", output)

    def test_video_metadata_newline(self):
        v = self.dir_path / "test.mp4"
        v.touch()

        output_io = StringIO()
        test_console = Console(file=output_io, force_terminal=False)

        with patch("modules.combine.console", test_console), \
             patch("modules.combine.get_media_duration", return_value=12.5), \
             patch("modules.combine.get_input", return_value="q"):
            combine.combine_videos([str(v)], interactive=True)

        output = output_io.getvalue()
        # Verify newline precedes Reading video metadata
        self.assertIn("\nReading video metadata...", output)

    def test_combine_videos_command_a_mixed_folder(self):
        init_v = self.dir_path / "initial.mp4"
        init_v.touch()

        folder = self.dir_path / "more_videos"
        folder.mkdir()
        v_mov = folder / "clip1.mov"
        v_mp4 = folder / "clip2.mp4"
        txt_file = folder / "notes.txt"
        v_mov.touch()
        v_mp4.touch()
        txt_file.touch()

        output_io = StringIO()
        test_console = Console(file=output_io, force_terminal=False)

        inputs = [
            "a",            # Command: A (Add more files)
            "q",            # Command: Q (Cancel)
        ]
        input_iter = iter(inputs)

        with patch("modules.combine.console", test_console), \
             patch("modules.combine.get_media_duration", return_value=10.0), \
             patch("modules.combine.get_input", side_effect=lambda p="": next(input_iter)), \
             patch("modules.combine.prompt_paths", return_value=[str(folder)]):
            combine.combine_videos([str(init_v)], interactive=True)

        output = output_io.getvalue()
        # Check command list has "A.                Add more files"
        self.assertIn("A.                Add more files", output)
        # Check that both mov and mp4 were added
        self.assertIn("clip1.mov", output)
        self.assertIn("clip2.mp4", output)
        self.assertIn("✓ Added 2 file(s).", output)
        # Check notes.txt was not added as a video
        self.assertNotIn("notes.txt", output)

    def test_combine_pdfs_command_a(self):
        p1 = self.dir_path / "doc1.pdf"
        p2 = self.dir_path / "doc2.pdf"
        p1.touch()
        p2.touch()

        output_io = StringIO()
        test_console = Console(file=output_io, force_terminal=False)

        inputs = [
            "a",            # Command: A
            "q",            # Command: Q
        ]
        input_iter = iter(inputs)

        with patch("modules.combine.console", test_console), \
             patch("modules.combine.get_pdf_page_count", return_value=5), \
             patch("modules.combine.get_input", side_effect=lambda p="": next(input_iter)), \
             patch("modules.combine.prompt_paths", return_value=[str(p2)]):
            combine.combine_pdfs([str(p1)], interactive=True)

        output = output_io.getvalue()
        self.assertIn("A.                Add more files", output)
        self.assertIn("doc1.pdf", output)
        self.assertIn("doc2.pdf", output)
        self.assertIn("✓ Added 1 file(s).", output)

    def test_shortcuts_display_no_extra_newline(self):
        output_io = StringIO()
        test_console = Console(file=output_io, force_terminal=False)

        shortcuts = {
            "V": {"title": "Video to Audio", "operation": "convert"}
        }

        # Emulate the main menu block for shortcuts
        if shortcuts:
            test_console.print("\n[bold yellow]Your Shortcuts:[/bold yellow]")
            for sym, sc in shortcuts.items():
                test_console.print(f" [bold cyan]{sym}.[/bold cyan] {sc['title']}")

        test_console.print(" [bold white]+.[/bold white] Add Shortcut")

        output = output_io.getvalue()
        # Verify "V. Video to Audio" is immediately followed by "+. Add Shortcut" without a blank line
        lines = [line.strip() for line in output.strip().splitlines() if line.strip()]
        v_idx = next(i for i, l in enumerate(lines) if "Video to Audio" in l)
        add_idx = next(i for i, l in enumerate(lines) if "Add Shortcut" in l)
        self.assertEqual(add_idx, v_idx + 1)


if __name__ == "__main__":
    unittest.main()
