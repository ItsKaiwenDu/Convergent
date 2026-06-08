import os
import subprocess
import shutil
from pathlib import Path
from customs.run_command import run_command, send_to_trash

def decompress(path, output_dir=None):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.exists():
        return False, f"Path does not exist: {path}", None
    
    if not output_dir:
        output_dir = path_obj.parent / path_obj.stem
    else:
        output_dir = Path(output_dir).resolve()
        
    send_to_trash(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cwd = path_obj.parent
    
    sevenzip_exec = "7z"
    if not shutil.which("7z") and shutil.which("7zz"):
        sevenzip_exec = "7zz"

    ext = path_obj.name.lower()
    
    if ext.endswith(".zip"):
        if not shutil.which("unzip"):
            return False, "Required utility 'unzip' is not installed on your system.", None
        cmd = ["unzip", str(path_obj), "-d", str(output_dir)]
    elif ext.endswith(".tar.gz") or ext.endswith(".tgz") or ext.endswith(".tar.bz2") or ext.endswith(".tbz2") or ext.endswith(".tar.xz") or ext.endswith(".txz"):
        if not shutil.which("tar"):
            return False, "Required utility 'tar' is not installed on your system.", None
        if ext.endswith(".tar.gz") or ext.endswith(".tgz"):
            cmd = ["tar", "-xzf", str(path_obj), "-C", str(output_dir)]
        elif ext.endswith(".tar.bz2") or ext.endswith(".tbz2"):
            cmd = ["tar", "-xjf", str(path_obj), "-C", str(output_dir)]
        else:
            cmd = ["tar", "-xJf", str(path_obj), "-C", str(output_dir)]
    elif ext.endswith(".7z"):
        if not shutil.which(sevenzip_exec):
            return False, "7-Zip is not installed on your system.\nTo install it, run:\n   brew install sevenzip", None
        cmd = [sevenzip_exec, "x", str(path_obj), f"-o{str(output_dir)}"]
    elif ext.endswith(".rar"):
        if shutil.which("unrar"):
            cmd = ["unrar", "x", str(path_obj), f"{str(output_dir)}/"]
        elif shutil.which(sevenzip_exec):
            cmd = [sevenzip_exec, "x", str(path_obj), f"-o{str(output_dir)}"]
        else:
            return False, f"Neither 'unrar' nor '{sevenzip_exec}' is installed on your system.\nTo extract RAR archives, please install 7-Zip by running:\n   brew install sevenzip", None
    else:
        return False, f"Unsupported or unknown archive format: {path_obj.name}", None

    success, error = run_command(cmd, cwd=cwd)
    return success, error, output_dir
