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

def convert_heic(source, target_ext):
    output = source.with_suffix(f".{target_ext.lower()}")
    return run_command(["magick", str(source), str(output)])

def convert_image(source, target_ext):
    output = source.with_suffix(f".{target_ext.lower()}")
    return run_command(["magick", str(source), str(output)])
