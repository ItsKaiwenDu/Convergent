import subprocess
from pathlib import Path
from customs.run_command import run_command

def convert_office(source, target_ext):
    if target_ext.upper() == "PDF":
        output = source.with_suffix(".pdf")
        success, err = run_command(["pandoc", str(source), "-o", str(output)])
        if success: return True, ""
        return False, f"{source.suffix[1:].upper()} to PDF requires 'pandoc'.\nInstall via: brew install pandoc"
    return False, f"Unsupported target format: {target_ext}"
