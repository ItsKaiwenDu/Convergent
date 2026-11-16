import re
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path
from customs.run_command import (
    LAST_COMMAND_STDERR,
    LAST_COMMAND_STDOUT,
    get_last_command_stderr,
    get_last_command_stdout,
    run_command,
    run_command_output,
)

HAS_MACOS_VISION = False
if sys.platform == "darwin":
    try:
        import objc  # type: ignore
        from Foundation import NSURL  # type: ignore
        from Vision import VNImageRequestHandler, VNRecognizeTextRequest  # type: ignore
        HAS_MACOS_VISION = True
    except ImportError:
        pass

def required_dependencies(source_format, target_format, **options):
    tools = [] if HAS_MACOS_VISION else ["tesseract"]
    if source_format == "PDF":
        if not any(shutil.which(cmd) for cmd in ("pdftoppm", "gs")):
            tools.append("ghostscript")
    elif source_format not in ("PNG", "JPG", "JPEG"):
        if not any(shutil.which(cmd) for cmd in ("sips", "magick", "convert", "ffmpeg")):
            tools.append("imagemagick")
    if target_format == "DOCX":
        tools.append("pandoc")
    return tools


def _convert_image_to_temp_png(source: Path) -> Path:
    """
    Converts an image file (HEIC, HEIF, WEBP, etc.) to a temporary PNG for OCR processing.
    Uses sips (macOS-native) with ImageMagick or FFmpeg as fallback.
    Returns Path of temporary PNG file (caller must delete it).
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

    # Fallback: FFmpeg
    if shutil.which("ffmpeg"):
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(source), str(tmp_png)],
            capture_output=True, text=True
        )
        if result.returncode == 0 and tmp_png.exists():
            return tmp_png

    raise RuntimeError(
        f"Could not convert {source.suffix.upper()} to PNG for OCR. "
        "Ensure 'sips' (macOS), ImageMagick, or FFmpeg is installed."
    )

_convert_heic_to_temp_png = _convert_image_to_temp_png


_ENCRYPTED_PDF_MARKERS = (
    "requires a password",
    "password for access",
    "incorrect password",
    "password-protected",
    "password protected",
    "cannot decrypt",
    "encrypted",
)


def _looks_like_encrypted_pdf_error(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker in lower for marker in _ENCRYPTED_PDF_MARKERS)


def _is_pdf_encrypted_hint(source: Path) -> bool:
    """Best-effort check for PDF encryption via macOS metadata or PDF /Encrypt trailer key."""
    if shutil.which("mdls"):
        try:
            res = subprocess.run(
                ["mdls", "-name", "kMDItemSecurityMethod", "-raw", str(source)],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=3.0,
            )
            sec = (res.stdout or "").strip()
            if res.returncode == 0 and sec and sec != "(null)":
                return True
        except Exception:
            pass

    try:
        file_size = source.stat().st_size
        with source.open("rb") as f:
            if file_size <= 2 * 1024 * 1024:
                sample = f.read()
            else:
                head = f.read(65536)
                f.seek(max(0, file_size - 65536))
                tail = f.read(65536)
                sample = head + b"\n" + tail
        if re.search(rb"/Encrypt\s+\d+\s+\d+\s+R|/Encrypt\s*<<", sample):
            return True
    except Exception:
        pass
    return False


def _run_pdf_render_command(cmd) -> tuple:
    """Runs a PDF rendering command and returns (success, combined_diagnostic_output)."""
    LAST_COMMAND_STDERR.set("")
    LAST_COMMAND_STDOUT.set("")
    success, err = run_command(cmd)
    diag = "\n".join(
        part for part in (err, get_last_command_stderr(), get_last_command_stdout()) if part
    )
    return success, diag


def _clear_temp_pngs(temp_dir: Path):
    for p in temp_dir.glob("*.png"):
        try:
            p.unlink()
        except Exception:
            pass


def _convert_pdf_to_temp_images(source: Path):
    """
    Converts a PDF file to a directory of temporary PNG page images for OCR.
    Tries pdftoppm, Ghostscript (gs), ImageMagick (magick/convert), and sips (only when no dedicated PDF renderer exists).
    Returns (temp_dir_path, list_of_png_paths).
    Caller is responsible for removing temp_dir_path.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="convergent_pdf_ocr_"))
    attempted_renderers = []
    last_diag = ""

    def _abort(message: str):
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(message)

    # 1. pdftoppm (poppler) - fast & native rendering
    if shutil.which("pdftoppm"):
        out_prefix = temp_dir / "page"
        success, diag = _run_pdf_render_command(
            ["pdftoppm", "-png", "-r", "300", str(source), str(out_prefix)]
        )
        pngs = sorted(list(temp_dir.glob("*.png")))
        if success and pngs:
            return temp_dir, pngs
        _clear_temp_pngs(temp_dir)
        if _looks_like_encrypted_pdf_error(diag):
            _abort(f"Cannot OCR encrypted or password-protected PDF: {source.name}")
        attempted_renderers.append("pdftoppm")
        if diag:
            last_diag = diag

    # 2. Ghostscript (gs)
    if shutil.which("gs"):
        resolved_source = Path(source).resolve()
        resolved_temp = Path(temp_dir).resolve()
        out_pattern = resolved_temp / "page_%04d.png"
        success, diag = _run_pdf_render_command([
            "gs", "-dNOPAUSE", "-dBATCH", "-dSAFER",
            f"--permit-file-read={resolved_source}",
            f"--permit-file-write={resolved_temp}/*",
            "-sDEVICE=png16m", "-r300",
            f"-sOUTPUTFILE={out_pattern}", str(resolved_source)
        ])
        pngs = sorted(list(temp_dir.glob("*.png")))
        if success and pngs:
            return temp_dir, pngs
        _clear_temp_pngs(temp_dir)
        if _looks_like_encrypted_pdf_error(diag):
            _abort(f"Cannot OCR encrypted or password-protected PDF: {source.name}")
        attempted_renderers.append("gs")
        if diag:
            last_diag = diag

    # 3. ImageMagick (magick / convert)
    im_cmd = "magick" if shutil.which("magick") else ("convert" if shutil.which("convert") else None)
    if im_cmd:
        out_pattern = temp_dir / "page_%04d.png"
        success, diag = _run_pdf_render_command([im_cmd, "-density", "300", str(source), str(out_pattern)])
        pngs = sorted(list(temp_dir.glob("*.png")))
        if success and pngs:
            return temp_dir, pngs
        _clear_temp_pngs(temp_dir)
        if _looks_like_encrypted_pdf_error(diag):
            _abort(f"Cannot OCR encrypted or password-protected PDF: {source.name}")
        attempted_renderers.append(im_cmd)
        if diag:
            last_diag = diag

    # 4. sips (macOS fallback only when no dedicated PDF renderer is available)
    if not attempted_renderers and shutil.which("sips"):
        if _is_pdf_encrypted_hint(source):
            _abort(f"Cannot OCR encrypted or password-protected PDF: {source.name}")
        out_png = temp_dir / "page_0001.png"
        success, diag = _run_pdf_render_command(
            ["sips", "-s", "format", "png", str(source), "--out", str(out_png)]
        )
        if success and out_png.exists() and out_png.stat().st_size > 0:
            return temp_dir, [out_png]
        _clear_temp_pngs(temp_dir)
        if _looks_like_encrypted_pdf_error(diag):
            _abort(f"Cannot OCR encrypted or password-protected PDF: {source.name}")
        if diag:
            last_diag = diag

    if attempted_renderers:
        if _is_pdf_encrypted_hint(source):
            _abort(f"Cannot OCR encrypted or password-protected PDF: {source.name}")
        detail = last_diag.splitlines()[-1].strip() if last_diag.strip() else "PDF may be encrypted, corrupted, or unreadable."
        _abort(f"Could not render PDF pages for OCR ({source.name}): {detail}")

    _abort(
        "Could not convert PDF pages to PNG for OCR. "
        "Ensure 'pdftoppm', 'gs' (Ghostscript), or ImageMagick is installed."
    )


def convert_image_to_text(source_path, target_ext="TXT", **kwargs):
    """
    Extracts text from PNG/JPG/HEIC/WEBP/PDF/etc. and saves it to a .txt, .md, .docx, or .pdf file.
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
    elif source.suffix.lower() in (".heic", ".heif", ".webp"):
        try:
            temp_png = _convert_image_to_temp_png(source)
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

        # 3. Write/Compile extracted text to target format
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
    if not shutil.which("tesseract"):
        raise FileNotFoundError("Tesseract is not installed. Install via: brew install tesseract")
    code, stdout, stderr = run_command_output(["tesseract", str(image_path.resolve()), "stdout"])
    if code != 0:
        raise RuntimeError(f"Tesseract OCR failed: {stderr}")
    return stdout
