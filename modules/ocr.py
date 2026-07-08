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


def convert_image_to_text(source_path, target_ext="TXT", **kwargs):
    """
    Extracts text from PNG/JPG/HEIC/etc. and saves it to a .txt, .md, .docx, or .pdf file.
    Returns: (bool, str) - Success status and error message or empty string.
    """
    source = Path(source_path)
    target_ext = target_ext.upper()
    output = source.with_suffix(f".{target_ext.lower()}")

    # HEIC cannot be read directly by Vision or Tesseract — convert to temp PNG first
    temp_png = None
    ocr_source = source
    if source.suffix.lower() in (".heic", ".heif"):
        try:
            temp_png = _convert_heic_to_temp_png(source)
            ocr_source = temp_png
        except RuntimeError as e:
            return False, str(e)

    try:
        text = ""
        # 1. Try macOS Vision first (zero installation, hardware-accelerated)
        if HAS_MACOS_VISION:
            try:
                text = _ocr_macos_native(ocr_source)
            except Exception:
                # If there's an error, fallback to Tesseract
                pass
                
        # 2. Fallback/Standard option: Tesseract CLI
        if not text:
            text = _ocr_tesseract(ocr_source)
            
        # 3. Write/Compile extracted text to the target format
        if target_ext in ("TXT", "MD"):
            with open(output, "w", encoding="utf-8") as f:
                f.write(text)
            return True, ""
            
        elif target_ext == "DOCX":
            temp_md = source.with_suffix(".temp_ocr.md")
            try:
                with open(temp_md, "w", encoding="utf-8") as f:
                    f.write(text)
                
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
                    f.write(text)
                
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
        # Clean up the temporary PNG created from HEIC/HEIF input
        if temp_png is not None and temp_png.exists():
            temp_png.unlink()

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
