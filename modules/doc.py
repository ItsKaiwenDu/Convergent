import subprocess
from pathlib import Path

def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)

def convert_office(source, target_ext):
    if target_ext.upper() == "PDF":
        output = source.with_suffix(".pdf")
        success, err = run_command(["pandoc", str(source), "-o", str(output)])
        if success: return True, ""
        return False, f"{source.suffix[1:].upper()} to PDF requires 'pandoc'.\nInstall via: brew install pandoc"
    return False, f"Unsupported target format: {target_ext}"
