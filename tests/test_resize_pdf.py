import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from customs import shortcut
from modules import resize
from mcp_server.server import resize_media as mcp_resize_media


class TestResizePDF(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.has_gs = bool(shutil.which("gs"))
        cls.has_magick = bool(shutil.which("magick"))

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="conv_test_pdf_resize_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_sample_pdf(self, filename="sample.pdf", w=600, h=800, pages=1):
        """Creates a vector/blank PDF with specific page dimensions in points."""
        path = self.test_dir / filename
        cmd = [
            "gs",
            "-sDEVICE=pdfwrite",
            f"-dDEVICEWIDTHPOINTS={w}",
            f"-dDEVICEHEIGHTPOINTS={h}",
            f"-sOutputFile={path}",
            "-dBATCH",
            "-dNOPAUSE",
            "-c",
            " ".join(["showpage"] * pages)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return path

    def _create_image_pdf(self, filename="image_doc.pdf", img_w=2000, img_h=3000):
        """Creates an image-based PDF composed of a high-resolution raster image."""
        if not self.has_magick:
            self.skipTest("ImageMagick required to create image PDF test asset")
        img_path = self.test_dir / "temp_scan.png"
        pdf_path = self.test_dir / filename
        # Create a dense gradient/plasma image so it has real compressibility
        subprocess.run(["magick", "-size", f"{img_w}x{img_h}", "plasma:fractal", str(img_path)], check=True, capture_output=True)
        subprocess.run(["magick", str(img_path), str(pdf_path)], check=True, capture_output=True)
        img_path.unlink(missing_ok=True)
        return pdf_path

    def test_menu_entries_for_pdf_file_includes_resize(self):
        class DummyConv:
            categories = {
                "2": {"name": "Image", "extensions": ["jpg", "png", "heic", "webp"]},
                "3": {"name": "Video", "extensions": ["mp4", "mov"]},
                "4": {"name": "Audio", "extensions": ["mp3", "wav"]},
                "5": {"name": "Document", "extensions": ["docx", "pdf", "txt", "md"]},
            }

        pdf_f = self.test_dir / "document.pdf"
        pdf_f.touch()

        entries = shortcut.get_applicable_menu_entries(DummyConv(), [str(pdf_f)])
        operations = [e["operation"] for e in entries]

        # PDF should now support Resize in addition to Combine, Split, Convert, OCR, Compress
        self.assertIn("resize", operations)
        self.assertIn("combine", operations)
        self.assertIn("split", operations)
        self.assertIn("convert", operations)
        self.assertIn("ocr", operations)
        self.assertIn("compress", operations)

    def test_get_pdf_dimensions(self):
        if not self.has_gs and not self.has_magick:
            self.skipTest("Neither gs nor magick available")
        pdf_path = self._create_sample_pdf("dim_test.pdf", w=612, h=792, pages=2)
        w, h = resize.get_pdf_dimensions(pdf_path)
        self.assertEqual((w, h), (612, 792))

        # Test that get_image_dimensions automatically delegates for .pdf
        w2, h2 = resize.get_image_dimensions(pdf_path)
        self.assertEqual((w2, h2), (612, 792))

    def test_resize_pdf_by_percentage(self):
        if not self.has_gs:
            self.skipTest("Ghostscript required")
        pdf_path = self._create_sample_pdf("scale_pct.pdf", w=600, h=800)

        # Scale by 50%
        name, success, error, duration = resize.resize_single_file(
            pdf_path,
            method="1",
            scale_val=50.0,
            target_aspect="5"
        )
        self.assertTrue(success, f"Resize failed: {error}")
        out_file = self.test_dir / "scale_pct_resized.pdf"
        self.assertTrue(out_file.exists())

        out_w, out_h = resize.get_pdf_dimensions(out_file)
        self.assertEqual((out_w, out_h), (300, 400))

    def test_resize_pdf_by_target_height(self):
        if not self.has_gs:
            self.skipTest("Ghostscript required")
        pdf_path = self._create_sample_pdf("target_h.pdf", w=600, h=800)

        # Scale to height = 400 (aspect 600/800 = 0.75 -> width 300)
        name, success, error, duration = resize.resize_single_file(
            pdf_path,
            method="2",
            scale_val=400,
            target_aspect="5"
        )
        self.assertTrue(success, f"Resize failed: {error}")
        out_file = self.test_dir / "target_h_resized.pdf"
        self.assertTrue(out_file.exists())

        out_w, out_h = resize.get_pdf_dimensions(out_file)
        self.assertEqual((out_w, out_h), (300, 400))

    def test_resize_pdf_by_exact_dimensions(self):
        if not self.has_gs:
            self.skipTest("Ghostscript required")
        pdf_path = self._create_sample_pdf("exact_dim.pdf", w=600, h=800)

        # Custom dimensions (500x500)
        name, success, error, duration = resize.resize_single_file(
            pdf_path,
            method="3",
            scale_val=(500, 500),
            target_aspect="5"
        )
        self.assertTrue(success, f"Resize failed: {error}")
        out_file = self.test_dir / "exact_dim_resized.pdf"
        self.assertTrue(out_file.exists())

        out_w, out_h = resize.get_pdf_dimensions(out_file)
        self.assertEqual((out_w, out_h), (500, 500))

    def test_resize_multi_page_pdf(self):
        if not self.has_gs:
            self.skipTest("Ghostscript required")
        pdf_path = self._create_sample_pdf("multipage.pdf", w=600, h=800, pages=3)

        name, success, error, duration = resize.resize_single_file(
            pdf_path,
            method="1",
            scale_val=50.0,
            target_aspect="5"
        )
        self.assertTrue(success, f"Resize failed: {error}")
        out_file = self.test_dir / "multipage_resized.pdf"
        self.assertTrue(out_file.exists())

        # Verify page count is preserved
        count_cmd = [
            "gs", "-q", "-dNODISPLAY", "-dSAFER",
            f"--permit-file-read={out_file.resolve()}",
            "-c",
            f"({out_file.resolve()}) (r) file runpdfbegin pdfpagecount = quit"
        ]
        res = subprocess.run(count_cmd, capture_output=True, text=True, check=True)
        self.assertEqual(res.stdout.strip(), "3")

    def test_resize_image_based_pdf_downsampling(self):
        if not self.has_gs or not self.has_magick:
            self.skipTest("Ghostscript and ImageMagick required")

        img_pdf = self._create_image_pdf("scanned_photo.pdf", img_w=2000, img_h=3000)
        orig_size = img_pdf.stat().st_size
        self.assertGreater(orig_size, 100_000)

        # Resize by 50%
        name, success, error, duration = resize.resize_single_file(
            img_pdf,
            method="1",
            scale_val=50.0,
            target_aspect="5"
        )
        self.assertTrue(success, f"Resize failed: {error}")
        out_file = self.test_dir / "scanned_photo_resized.pdf"
        self.assertTrue(out_file.exists())

        resized_size = out_file.stat().st_size
        # Embedded images downsampled -> file size must be significantly smaller
        self.assertLess(resized_size, orig_size)

    def test_resize_pdf_strip_metadata(self):
        if not self.has_gs:
            self.skipTest("Ghostscript required")
        pdf_path = self._create_sample_pdf("metadata.pdf", w=600, h=800)

        name, success, error, duration = resize.resize_single_file(
            pdf_path,
            method="1",
            scale_val=50.0,
            target_aspect="5",
            strip_metadata=True
        )
        self.assertTrue(success, f"Resize failed: {error}")
        out_file = self.test_dir / "metadata_resized.pdf"
        self.assertTrue(out_file.exists())

    def test_mcp_resize_pdf(self):
        if not self.has_gs:
            self.skipTest("Ghostscript required")
        pdf_path = self._create_sample_pdf("mcp_test.pdf", w=600, h=800)

        res = mcp_resize_media(
            file_path=str(pdf_path),
            scale_percent=50.0
        )
        self.assertTrue(res["success"], f"MCP resize failed: {res.get('error')}")
        self.assertTrue(Path(res["output_file"]).exists())
        w, h = resize.get_pdf_dimensions(Path(res["output_file"]))
        self.assertEqual((w, h), (300, 400))


if __name__ == "__main__":
    unittest.main()
