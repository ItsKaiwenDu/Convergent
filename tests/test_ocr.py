import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Convergent import Converter
from modules import ocr
from customs.file_process import FORMAT_REGISTRY


class TestWebpOCR(unittest.TestCase):
    def setUp(self):
        self.conv = Converter()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_webp_in_format_registry_and_conv_targets(self):
        self.assertIn("TXT", self.conv.formats["WEBP"])
        self.assertIn("MD", self.conv.formats["WEBP"])
        self.assertIn("DOCX", self.conv.formats["WEBP"])

        webp_def = next(fd for fd in FORMAT_REGISTRY if fd.name == "WEBP")
        self.assertIn("TXT", webp_def.targets)
        self.assertIn("MD", webp_def.targets)
        self.assertIn("DOCX", webp_def.targets)

    @patch("modules.ocr._ocr_tesseract", return_value="Recognized text from webp")
    @patch("modules.ocr._convert_image_to_temp_png")
    def test_convert_webp_to_text(self, mock_convert_png, mock_ocr):
        # Create a dummy webp file
        webp_file = self.dir_path / "sample.webp"
        webp_file.write_bytes(b"dummy webp content")

        fake_png = self.dir_path / "fake_tmp.png"
        fake_png.write_bytes(b"dummy png content")
        mock_convert_png.return_value = fake_png

        # Test TXT extraction
        success, err = ocr.convert_image_to_text(webp_file, "TXT")
        self.assertTrue(success)
        self.assertEqual(err, "")
        mock_convert_png.assert_called_once_with(webp_file)

        output_txt = self.dir_path / "sample.txt"
        self.assertTrue(output_txt.exists())
        self.assertEqual(output_txt.read_text(encoding="utf-8"), "Recognized text from webp")

    @patch("modules.ocr.convert_image_to_text", return_value=(True, ""))
    def test_converter_convert_image_delegates_to_ocr(self, mock_ocr_convert):
        webp_file = self.dir_path / "sample.webp"
        webp_file.write_bytes(b"dummy")

        # Calling convert_image with target_ext TXT triggers OCR
        self.conv.convert_image(webp_file, "TXT")
        mock_ocr_convert.assert_called_once_with(webp_file, "TXT")

    def test_convert_heic_alias(self):
        self.assertIs(ocr._convert_heic_to_temp_png, ocr._convert_image_to_temp_png)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_convert_image_to_temp_png_sips(self, mock_run, mock_which):
        def which_side_effect(cmd):
            return "/usr/bin/sips" if cmd == "sips" else None

        mock_which.side_effect = which_side_effect
        mock_run.return_value = MagicMock(returncode=0)

        webp_file = self.dir_path / "test.webp"
        webp_file.touch()

        # Patch Path.exists so tmp_png.exists() returns True
        with patch.object(Path, "exists", return_value=True):
            tmp_path = ocr._convert_image_to_temp_png(webp_file)
            self.assertTrue(str(tmp_path).endswith("_ocr_tmp.png"))
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            self.assertEqual(args[0], "sips")
            self.assertIn("png", args)


if __name__ == "__main__":
    unittest.main()
