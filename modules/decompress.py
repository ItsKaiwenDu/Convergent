import os
import subprocess
from pathlib import Path

def run_command(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)

def decompress(path, output_dir=None):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.exists():
        return False, f"Path does not exist: {path}"
    
    if not output_dir:
        output_dir = path_obj.parent / path_obj.stem
    else:
        output_dir = Path(output_dir).resolve()
        
    # Ensure output dir exists
    output_dir.mkdir(parents=True, exist_ok=True)
    cwd = path_obj.parent
    
    ext = path_obj.name.lower()
    
    if ext.endswith(".zip"):
        cmd = ["unzip", str(path_obj), "-d", str(output_dir)]
    elif ext.endswith(".tar.gz") or ext.endswith(".tgz"):
        cmd = ["tar", "-xzf", str(path_obj), "-C", str(output_dir)]
    elif ext.endswith(".7z"):
        # 7z x archive.7z -o/path/to/dir
        cmd = ["7z", "x", str(path_obj), f"-o{str(output_dir)}"]
    elif ext.endswith(".rar"):
        # unrar x archive.rar /path/to/dir/
        cmd = ["unrar", "x", str(path_obj), f"{str(output_dir)}/"]
    else:
        return False, f"Unsupported or unknown archive format: {path_obj.name}"

    return run_command(cmd, cwd=cwd)
