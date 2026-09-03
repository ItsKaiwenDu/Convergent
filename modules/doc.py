import subprocess
import shutil
import sys
import uuid
from pathlib import Path
from customs.run_command import run_command

def convert_with_temp_files(source, output, run_conv_fn):
    """
    Copies input files to a temp directory inside Convergent workspace
    to bypass macOS TCC / sandbox restrictions on folders like Downloads.
    Runs conversion function run_conv_fn(temp_source, temp_output),
    and then copies output back to original destination.
    """
    workspace_dir = Path(__file__).parent.parent.resolve()
    tmp_dir = workspace_dir / ".convergent_tmp"
    tmp_dir.mkdir(exist_ok=True)
    
    unique_id = uuid.uuid4().hex
    temp_source = tmp_dir / f"{unique_id}{source.suffix}"
    temp_output = tmp_dir / f"{unique_id}{output.suffix}"
    
    try:
        shutil.copy2(source, temp_source)
        success, err = run_conv_fn(temp_source, temp_output)
        if success:
            if temp_output.exists():
                shutil.copy2(temp_output, output)
                return True, ""
            else:
                return False, "Conversion succeeded but output file was not created."
        return False, err
    except Exception as e:
        return False, f"Workspace temporary file operation failed: {e}"
    finally:
        try:
            if temp_source.exists(): temp_source.unlink()
            if temp_output.exists(): temp_output.unlink()
        except:
            pass

_libreoffice_warned = False

def convert_office(source, target_ext):
    if target_ext.upper() == "PDF":
        output = source.with_suffix(".pdf")
        
        def run_conv(temp_src, temp_out):
            # Try LibreOffice first for high-fidelity conversion
            soffice_path = None
            if sys.platform == "darwin":
                app_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
                if Path(app_path).exists():
                    soffice_path = app_path
            
            if not soffice_path:
                soffice_path = shutil.which("soffice") or shutil.which("libreoffice")
                
            if soffice_path:
                outdir = str(temp_out.parent)
                success, err = run_command([soffice_path, "--headless", "--convert-to", "pdf", "--outdir", outdir, str(temp_src)])
                if success:
                    return True, ""
                # If LibreOffice failed, fall back to pandoc
                
            global _libreoffice_warned
            if not soffice_path and not _libreoffice_warned:
                _libreoffice_warned = True
                try:
                    from customs.console import console
                    console.print(
                        "[yellow]⚠ Warning: LibreOffice not found. Office document conversions (DOCX/PPTX/RTF) "
                        "will fall back to Pandoc, which may result in layout and styling differences.[/yellow]"
                    )
                    console.print(
                        "[dim]Tip: Install LibreOffice for high-fidelity, 1-to-1 conversions: brew install --cask libreoffice[/dim]"
                    )
                except Exception:
                    pass

            # Try converting using typst as PDF engine first, as typst is fast and clean
            success, err = run_command(["pandoc", str(temp_src), "-o", str(temp_out), "--pdf-engine=typst"])
            if success:
                return True, ""
            # Fallback to default pandoc behavior (which usually uses LaTeX/pdflatex)
            success_fb, err_fb = run_command(["pandoc", str(temp_src), "-o", str(temp_out)])
            if success_fb:
                return True, ""
            return False, err or err_fb

        success, err = convert_with_temp_files(source, output, run_conv)
        if success:
            return True, ""
            
        return False, (
            f"Failed to convert {source.suffix[1:].upper()} to PDF.\n"
            "This usually requires 'libreoffice' or 'pandoc' and a PDF engine like 'typst' or 'pdflatex' (LaTeX).\n"
            "Install LibreOffice via: brew install --cask libreoffice\n"
            f"Error details: {err}"
        )
    return False, f"Unsupported target format: {target_ext}"

def convert_markdown(source, target_ext, md_pdf_mode=None):
    target_ext = target_ext.upper()
    output = source.with_suffix(f".{target_ext.lower()}")
    
    if target_ext == "HTML":
        def run_conv(temp_src, temp_out):
            return run_command(["pandoc", str(temp_src), "-o", str(temp_out)])
            
        success, err = convert_with_temp_files(source, output, run_conv)
        if success:
            return True, ""
        return False, f"Markdown to HTML requires 'pandoc'.\nInstall via: brew install pandoc\nError details: {err}"
        
    elif target_ext == "TXT":
        def run_conv(temp_src, temp_out):
            return run_command(["pandoc", str(temp_src), "-t", "plain", "-o", str(temp_out)])
            
        success, err = convert_with_temp_files(source, output, run_conv)
        if success:
            return True, ""
        # Fallback to copy file if pandoc fails or is missing
        try:
            shutil.copy2(source, output)
            return True, ""
        except Exception as e:
            return False, f"Failed to copy plain text file: {e}"
            
    elif target_ext == "PDF":
        if md_pdf_mode == "raw":
            # Convert raw markdown text to PDF using macOS cupsfilter
            if sys.platform != "darwin":
                return False, "Raw PDF conversion is only supported on macOS."
            
            def run_conv(temp_src, temp_out):
                try:
                    with open(temp_out, "wb") as out_file:
                        result = subprocess.run(["/usr/sbin/cupsfilter", str(temp_src)], stdout=out_file, stderr=subprocess.PIPE)
                    if result.returncode == 0:
                        return True, ""
                    return False, f"cupsfilter failed: {result.stderr.decode('utf-8')}"
                except Exception as e:
                    return False, f"cupsfilter execution failed: {e}"
                    
            success, err = convert_with_temp_files(source, output, run_conv)
            if success:
                return True, ""
            return False, f"Raw PDF conversion failed: {err}"
        else:
            def run_conv(temp_src, temp_out):
                # First try pandoc with typst PDF engine
                success, err = run_command(["pandoc", str(temp_src), "-o", str(temp_out), "--pdf-engine=typst"])
                if success:
                    return True, ""
                
                # Direct fallback to typst compile
                success_fb, err_fb = run_command(["typst", "compile", str(temp_src), str(temp_out)])
                if success_fb:
                    return True, ""
                return False, err or err_fb
                
            success, err = convert_with_temp_files(source, output, run_conv)
            if success:
                return True, ""
            return False, (
                "Human-friendly Markdown to PDF requires 'pandoc' and 'typst' (or just 'typst').\n"
                "Install via: brew install pandoc typst\n"
                f"Error details: {err}"
            )
            
    return False, f"Unsupported target format: {target_ext}"
