import sys
import subprocess
import shutil
import tempfile
from pathlib import Path

# Module-level platform-specific imports
HAS_MACOS_VISION = False
if sys.platform == "darwin":
    try:
        import objc  # type: ignore
        from Foundation import NSURL  # type: ignore
        from Vision import VNImageRequestHandler, VNRecognizeTextRequest  # type: ignore
        HAS_MACOS_VISION = True
    except ImportError:
        pass

def _convert_heic_to_temp_png(source: Path) -> Path:
    """
    Converts a HEIC file to a temporary PNG for OCR processing.
    Uses sips (macOS-native) with ImageMagick as fallback.
    Returns the Path of the temporary PNG file (caller must delete it).
    """
    tmp_png = Path(tempfile.mktemp(suffix="_ocr_tmp.png"))
    
    # Try sips first (macOS native, zero dependencies)
    if shutil.which("sips"):
        result = subprocess.run(
            ["sips", "-s", "format", "png", str(source), "--out", str(tmp_png)],
            capture_output=True, text=True
        )
        if result.returncode == 0 and tmp_png.exists():
            return tmp_png
    
    # Fallback: ImageMagick
    if shutil.which("magick"):
        result = subprocess.run(
            ["magick", str(source), str(tmp_png)],
            capture_output=True, text=True
        )
        if result.returncode == 0 and tmp_png.exists():
            return tmp_png
    elif shutil.which("convert"):
        result = subprocess.run(
            ["convert", str(source), str(tmp_png)],
            capture_output=True, text=True
        )
        if result.returncode == 0 and tmp_png.exists():
            return tmp_png

    raise RuntimeError(
        f"Could not convert HEIC to PNG for OCR. "
        "Ensure 'sips' (macOS) or ImageMagick is installed."
    )


def _convert_pdf_to_temp_images(source: Path):
    """
    Converts a PDF file to a directory of temporary PNG page images for OCR.
    Tries pdftoppm, Ghostscript (gs), ImageMagick (magick/convert), and sips.
    Returns (temp_dir_path, list_of_png_paths).
    Caller is responsible for removing temp_dir_path.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="convergent_pdf_ocr_"))
    
    # 1. pdftoppm (poppler) - fast & native rendering
    if shutil.which("pdftoppm"):
        out_prefix = temp_dir / "page"
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", "300", str(source), str(out_prefix)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            pngs = sorted(list(temp_dir.glob("*.png")))
            if pngs:
                return temp_dir, pngs

    # 2. Ghostscript (gs)
    if shutil.which("gs"):
        out_pattern = temp_dir / "page_%04d.png"
        result = subprocess.run(
            [
                "gs", "-dNOPAUSE", "-dBATCH", "-dNOSAFER",
                "-sDEVICE=png16m", "-r300",
                f"-sOUTPUTFILE={out_pattern}", str(source)
            ],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            pngs = sorted(list(temp_dir.glob("*.png")))
            if pngs:
                return temp_dir, pngs

    # 3. ImageMagick (magick / convert)
    if shutil.which("magick"):
        out_pattern = temp_dir / "page_%04d.png"
        result = subprocess.run(
            ["magick", "-density", "300", str(source), str(out_pattern)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            pngs = sorted(list(temp_dir.glob("*.png")))
            if pngs:
                return temp_dir, pngs
    elif shutil.which("convert"):
        out_pattern = temp_dir / "page_%04d.png"
        result = subprocess.run(
            ["convert", "-density", "300", str(source), str(out_pattern)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            pngs = sorted(list(temp_dir.glob("*.png")))
            if pngs:
                return temp_dir, pngs

    # 4. sips (macOS fallback)
    if shutil.which("sips"):
        out_png = temp_dir / "page_0001.png"
        result = subprocess.run(
            ["sips", "-s", "format", "png", str(source), "--out", str(out_png)],
            capture_output=True, text=True
        )
        if result.returncode == 0 and out_png.exists():
            return temp_dir, [out_png]

    # Cleanup temp dir if conversion failed
    shutil.rmtree(temp_dir, ignore_errors=True)
    raise RuntimeError(
        "Could not convert PDF pages to PNG for OCR. "
        "Ensure 'pdftoppm', 'gs' (Ghostscript), or ImageMagick is installed."
    )


def convert_image_to_text(source_path, target_ext="TXT", **kwargs):
    """
    Extracts text from PNG/JPG/HEIC/PDF/etc. and saves it to a .txt, .md, .docx, or .pdf file.
    Returns: (bool, str) - Success status and error message or empty string.
    """
    source = Path(source_path)
    target_ext = target_ext.upper()
    output = source.with_suffix(f".{target_ext.lower()}")

    temp_png = None
    temp_dir = None
    ocr_sources = []

    if source.suffix.lower() == ".pdf":
        try:
            temp_dir, ocr_sources = _convert_pdf_to_temp_images(source)
        except RuntimeError as e:
            return False, str(e)
    elif source.suffix.lower() in (".heic", ".heif"):
        try:
            temp_png = _convert_heic_to_temp_png(source)
            ocr_sources = [temp_png]
        except RuntimeError as e:
            return False, str(e)
    else:
        ocr_sources = [source]

    try:
        page_texts = []
        for ocr_src in ocr_sources:
            text = ""
            # 1. Try macOS Vision first (zero installation, hardware-accelerated)
            if HAS_MACOS_VISION:
                try:
                    text = _ocr_macos_native(ocr_src)
                except Exception:
                    # If there's an error, fallback to Tesseract
                    pass
                    
            # 2. Fallback/Standard option: Tesseract CLI
            if not text:
                text = _ocr_tesseract(ocr_src)

            if text.strip():
                page_texts.append(text)

        combined_text = "\n\n".join(page_texts)

        # 3. Write/Compile extracted text to the target format
        if target_ext in ("TXT", "MD"):
            with open(output, "w", encoding="utf-8") as f:
                f.write(combined_text)
            return True, ""
            
        elif target_ext == "DOCX":
            temp_md = source.with_suffix(".temp_ocr.md")
            try:
                with open(temp_md, "w", encoding="utf-8") as f:
                    f.write(combined_text)
                
                if shutil.which("pandoc"):
                    result = subprocess.run(
                        ["pandoc", str(temp_md), "-o", str(output)],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        return True, ""
                    return False, f"Pandoc docx compile failed: {result.stderr}"
                else:
                    return False, "Pandoc is required to output to DOCX. Install via: brew install pandoc"
            finally:
                if temp_md.exists():
                    temp_md.unlink()
                    
        elif target_ext == "PDF":
            temp_md = source.with_suffix(".temp_ocr.md")
            try:
                with open(temp_md, "w", encoding="utf-8") as f:
                    f.write(combined_text)
                
                # Try typst first
                if shutil.which("typst"):
                    result = subprocess.run(
                        ["typst", "compile", str(temp_md), str(output)],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        return True, ""
                
                # Fallback to pandoc with typst/default engines
                if shutil.which("pandoc"):
                    result = subprocess.run(
                        ["pandoc", str(temp_md), "-o", str(output), "--pdf-engine=typst"],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        return True, ""
                        
                    result = subprocess.run(
                        ["pandoc", str(temp_md), "-o", str(output)],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        return True, ""
                        
                return False, "Failed to compile PDF. Typst or Pandoc (with a PDF engine) is required."
            finally:
                if temp_md.exists():
                    temp_md.unlink()
                    
        return False, f"Unsupported target format: {target_ext}"
    except Exception as e:
        return False, str(e)
    finally:
        # Clean up temporary files / directories created
        if temp_png is not None and temp_png.exists():
            temp_png.unlink()
        if temp_dir is not None and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

def _ocr_macos_native(image_path: Path) -> str:
    if not HAS_MACOS_VISION:
        raise ImportError("pyobjc-framework-Vision is not installed. Run 'pip install pyobjc-framework-Vision'")
        
    url = NSURL.fileURLWithPath_(str(image_path.resolve()))
    handler = VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    
    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(0)  # 0 = Accurate, 1 = Fast
    
    success, error = handler.performRequests_error_([request], None)
    if not success:
        raise RuntimeError("macOS Vision OCR failed")
        
    results = request.results()
    if not results:
        return ""
        
    text_lines = []
    for r in results:
        candidates = r.topCandidates_(1)
        if candidates:
            text_lines.append(candidates[0].string())
            
    return "\n".join(text_lines)

def _ocr_tesseract(image_path: Path) -> str:
    try:
        result = subprocess.run(
            ["tesseract", str(image_path), "stdout"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except FileNotFoundError:
        raise FileNotFoundError("Tesseract is not installed. Install via: brew install tesseract")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Tesseract OCR failed: {e.stderr}")
