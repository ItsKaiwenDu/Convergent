import os
import sys
import shutil
import tempfile
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Convergent import Converter


class TestConversionsIntegration(unittest.TestCase):
    """
    Integration tests verifying actual orchestration boundaries and subprocess execution
    for representative FFmpeg, ImageMagick/sips, Pandoc/Typst, and Ghostscript conversions.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.conv = Converter()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_markdown_to_txt_real(self):
        md_file = self.dir_path / "sample.md"
        md_file.write_text("# Convergent Docs\n\n**Local** conversion tool.")
        
        ok, err = self.conv.convert_markdown(md_file, "TXT")
        self.assertTrue(ok, f"Markdown to TXT failed: {err}")
        
        txt_output = self.dir_path / "sample.txt"
        self.assertTrue(txt_output.exists())
        self.assertIn("Convergent Docs", txt_output.read_text())

    def test_combine_txt_real(self):
        t1 = self.dir_path / "1.txt"
        t2 = self.dir_path / "2.txt"
        t1.write_text("Hello from file 1\n")
        t2.write_text("Hello from file 2\n")

        out_combined = self.dir_path / "merged.txt"
        res = self.conv.combine_txt([str(t1), str(t2)], output_path=str(out_combined), interactive=False)
        self.assertIsNotNone(res)
        self.assertTrue(out_combined.exists())
        content = out_combined.read_text()
        self.assertIn("Hello from file 1", content)
        self.assertIn("Hello from file 2", content)

    @unittest.skipUnless(
        bool(shutil.which("typst") or shutil.which("pandoc") or shutil.which("cupsfilter")),
        "Neither Typst, Pandoc, nor cupsfilter installed"
    )
    def test_markdown_to_pdf_formatted_real(self):
        md_file = self.dir_path / "document.md"
        md_file.write_text("# Chapter 1\n\nThis is a *real* formatted test document.")

        ok, err = self.conv.convert_markdown(md_file, "PDF", md_pdf_mode="formatted")
        self.assertTrue(ok, f"Markdown to PDF failed: {err}")

        pdf_output = self.dir_path / "document.pdf"
        self.assertTrue(pdf_output.exists())
        self.assertTrue(pdf_output.stat().st_size > 100)
        self.assertTrue(pdf_output.read_bytes().startswith(b"%PDF-"))

    @unittest.skipUnless(
        bool(shutil.which("sips") or shutil.which("magick") or shutil.which("convert")),
        "Neither sips nor ImageMagick is available"
    )
    def test_image_png_to_jpg_real(self):
        # Generate a minimal valid 10x10 PNG
        png_file = self.dir_path / "icon.png"
        if shutil.which("sips"):
            # Create a 10x10 dummy image with sips or python
            dummy_bmp = self.dir_path / "temp.bmp"
            # 1x1 BMP raw bytes
            bmp_header = bytes([
                0x42, 0x4D, 0x3A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x36, 0x00, 0x00, 0x00,
                0x28, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00,
                0x18, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x00
            ])
            dummy_bmp.write_bytes(bmp_header)
            subprocess.run(["sips", "-s", "format", "png", str(dummy_bmp), "--out", str(png_file)], capture_output=True)
        elif shutil.which("magick"):
            subprocess.run(["magick", "-size", "10x10", "xc:blue", str(png_file)], capture_output=True)
        elif shutil.which("convert"):
            subprocess.run(["convert", "-size", "10x10", "xc:blue", str(png_file)], capture_output=True)

        if not png_file.exists():
            self.skipTest("Failed to synthesize test PNG file")

        ok, err = self.conv.convert_image(png_file, "JPG")
        self.assertTrue(ok, f"Image conversion failed: {err}")

        jpg_output = self.dir_path / "icon.jpg"
        self.assertTrue(jpg_output.exists())
        self.assertTrue(jpg_output.stat().st_size > 50)

    @unittest.skipUnless(bool(shutil.which("ffmpeg")), "FFmpeg is not installed")
    def test_audio_conversion_ffmpeg_real(self):
        wav_file = self.dir_path / "sine.wav"
        res = subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5", "-y", "-loglevel", "error", str(wav_file)],
            capture_output=True
        )
        if res.returncode != 0 or not wav_file.exists():
            self.skipTest("Failed to generate test WAV file with FFmpeg")

        ok, err = self.conv.convert_audio(wav_file, "MP3", bitrate="128k")
        self.assertTrue(ok, f"Audio conversion WAV->MP3 failed: {err}")

        mp3_output = self.dir_path / "sine.mp3"
        self.assertTrue(mp3_output.exists())
        self.assertTrue(mp3_output.stat().st_size > 100)


if __name__ == "__main__":
    unittest.main()
