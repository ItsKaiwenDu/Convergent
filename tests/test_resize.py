import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules import resize


class TestResize(unittest.TestCase):
    def test_privacy_strip_preserves_icc_color_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "wide-gamut.png"
            source.touch()

            with patch.object(resize, "get_image_dimensions", return_value=(100, 100)), \
                 patch.object(resize, "send_to_trash"), \
                 patch.object(resize, "run_command", return_value=(True, "")) as mock_run:
                _, success, error, _ = resize.resize_single_file(
                    source,
                    method="1",
                    scale_val=50,
                    target_aspect="5",
                    strip_metadata=True,
                )

        self.assertTrue(success)
        self.assertEqual(error, "")

        command = mock_run.call_args.args[0]
        self.assertNotIn("-strip", command)
        self.assertIn("+profile", command)
        profile_arg = command[command.index("+profile") + 1]
        self.assertEqual(profile_arg, "exif,iptc,xmp")


if __name__ == "__main__":
    unittest.main()
