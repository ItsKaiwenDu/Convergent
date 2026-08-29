import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from customs.check_deps import (
    get_command_output,
    get_imagemagick_version,
    get_libreoffice_version,
    get_whisper_version,
)


class TestCheckDeps(unittest.TestCase):
    def test_get_imagemagick_version_parsing(self):
        sample_output = "Version: ImageMagick 7.1.1-29 Q16-HDRI x86_64 https://imagemagick.org"
        with patch("customs.check_deps.get_command_output", return_value=sample_output):
            ver = get_imagemagick_version()
            self.assertEqual(ver, "7.1.1-29")

        # Fallback when output has no version pattern
        with patch("customs.check_deps.get_command_output", return_value="ImageMagick installed"):
            ver = get_imagemagick_version()
            self.assertEqual(ver, "Found")

        # Not found
        with patch("customs.check_deps.get_command_output", return_value=None):
            ver = get_imagemagick_version()
            self.assertIsNone(ver)

    def test_get_libreoffice_version_parsing(self):
        sample_output = "LibreOffice 24.2.0.3 420(Build:3)"
        with patch("shutil.which", return_value="/usr/bin/soffice"):
            with patch("customs.check_deps.get_command_output", return_value=sample_output):
                ver = get_libreoffice_version()
                self.assertEqual(ver, "24.2.0.3")

    def test_get_whisper_version(self):
        with patch("shutil.which", side_effect=lambda x: "/usr/local/bin/whisper-cli" if x == "whisper-cli" else None):
            ver = get_whisper_version()
            self.assertEqual(ver, "Found")


if __name__ == "__main__":
    unittest.main()
