import subprocess
import shutil
import sys
from pathlib import Path
from customs.run_command import run_command

def convert_office(source, target_ext):
    if target_ext.upper() == "PDF":
        output = source.with_suffix(".pdf")
        success, err = run_command(["pandoc", str(source), "-o", str(output)])
        if success: return True, ""
        return False, f"{source.suffix[1:].upper()} to PDF requires 'pandoc'.\nInstall via: brew install pandoc"
    return False, f"Unsupported target format: {target_ext}"

def convert_markdown(source, target_ext, md_pdf_mode=None):
    """
    Converts a Markdown (.md) file to PDF, HTML, or TXT format.
    
    Args:
        source (Path): The path to the source .md file.
        target_ext (str): The target format extension (PDF, HTML, TXT).
        md_pdf_mode (str, optional): 'formatted' or 'raw' for PDF conversion.
        
    Returns:
        tuple: (success (bool), error_message (str))
    """
    target_ext = target_ext.upper()
    output = source.with_suffix(f".{target_ext.lower()}")
    
    if target_ext == "HTML":
        # HTML conversion using pandoc
        success, err = run_command(["pandoc", str(source), "-o", str(output)])
        if success:
            return True, ""
        return False, f"Markdown to HTML requires 'pandoc'.\nInstall via: brew install pandoc\nError details: {err}"
        
    elif target_ext == "TXT":
        # Convert to plain text (strip markdown styling symbols) using pandoc if available
        success, err = run_command(["pandoc", str(source), "-t", "plain", "-o", str(output)])
        if success:
            return True, ""
        # Fallback to copy the file if pandoc fails or is missing
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
            try:
                # Redirect cupsfilter output to the PDF file
                with open(output, "wb") as out_file:
                    result = subprocess.run(["/usr/sbin/cupsfilter", str(source)], stdout=out_file, stderr=subprocess.PIPE)
                if result.returncode == 0:
                    return True, ""
                else:
                    return False, f"cupsfilter failed: {result.stderr.decode('utf-8')}"
            except Exception as e:
                return False, f"Raw PDF conversion failed: {e}"
        else:
            # Human-friendly PDF conversion via pandoc and typst
            # First try pandoc with typst PDF engine
            success, err = run_command(["pandoc", str(source), "-o", str(output), "--pdf-engine=typst"])
            if success:
                return True, ""
            
            # Direct fallback to typst CLI directly (typst compile source output)
            success, err = run_command(["typst", "compile", str(source), str(output)])
            if success:
                return True, ""
                
            return False, (
                "Human-friendly Markdown to PDF requires 'pandoc' and 'typst' (or just 'typst').\n"
                "Install via: brew install pandoc typst\n"
                f"Error details: {err}"
            )
            
    return False, f"Unsupported target format: {target_ext}"
