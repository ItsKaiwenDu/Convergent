import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
from rich.console import Console
from modules import resize
import customs.console as console_mod
from pathlib import Path
import os

class TestResizeFPS(unittest.TestCase):
    def setUp(self):
        self.console = Console(force_terminal=False)

    def test_prompt_video_fps(self):
        # Test Default
        with patch("customs.console.get_char", return_value="1"), \
             patch("customs.console.get_input", return_value=""):
            status, val = console_mod.prompt_video_fps()
            self.assertEqual(status, "success")
            self.assertEqual(val, None)

        # Test 30 FPS
        with patch("customs.console.get_char", return_value="2"):
            status, val = console_mod.prompt_video_fps()
            self.assertEqual(status, "success")
            self.assertEqual(val, 30)

        # Test 60 FPS
        with patch("customs.console.get_char", return_value="3"):
            status, val = console_mod.prompt_video_fps()
            self.assertEqual(status, "success")
            self.assertEqual(val, 60)

        # Test Custom FPS
        with patch("customs.console.get_char", return_value="4"), \
             patch("customs.console.get_input", return_value="24"):
            status, val = console_mod.prompt_video_fps()
            self.assertEqual(status, "success")
            self.assertEqual(val, 24.0)

        # Test Back
        with patch("customs.console.get_char", return_value="b"):
            status, val = console_mod.prompt_video_fps()
            self.assertEqual(status, "back")

    def test_resize_media_video_fps_flow(self):
        # Mocking necessary components to simulate user flow
        mock_conv = MagicMock()
        import os
        img_file = Path("test.mp4")
        img_file.touch()

        # char_inputs: Method=1(Pct), Pct=50, Aspect=1(16:9), FPS=2(30), Metadata=1(Yes)
        char_inputs = ["1", "1", "2", "1"]
        text_inputs = ["50"]

        with patch("modules.resize.get_video_dimensions", return_value=(1920, 1080)), \
             patch("modules.resize.resize_single_file", return_value=("test.mp4", True, "", 0.1)) as mock_resize, \
             patch("modules.resize.prompt_move_files"), \
             patch("modules.resize.ensure_dependencies", return_value=True):
            
            resize.resize_media([str(img_file)], mock_conv, self.console, 
                                get_char=lambda p: char_inputs.pop(0), 
                                get_input=lambda p: text_inputs.pop(0))
            
            self.assertEqual(mock_resize.call_args[1]["fps"], 30)

if __name__ == '__main__':
    unittest.main()
