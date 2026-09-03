import os
import subprocess
import shutil
from pathlib import Path
from customs.run_command import run_command, send_to_trash

from customs.console import console

def compress(paths, output_name, format_choice, password=None):
    if isinstance(paths, str):
        paths = [paths]
        
    path_objs = [Path(os.path.expanduser(p)).resolve() for p in paths]
    valid_paths = [p for p in path_objs if p.exists()]
    
    if not valid_paths:
        return False, "No valid paths provided for compression.", None
    
    if format_choice == "ZIP" and not output_name.lower().endswith(".zip"):
        output_name += ".zip"
    elif format_choice == "TAR.GZ" and not (output_name.lower().endswith(".tar.gz") or output_name.lower().endswith(".tgz")):
        output_name += ".tar.gz"
    elif format_choice == "TAR.BZ2" and not (output_name.lower().endswith(".tar.bz2") or output_name.lower().endswith(".tbz2")):
        output_name += ".tar.bz2"
    elif format_choice == "TAR.XZ" and not (output_name.lower().endswith(".tar.xz") or output_name.lower().endswith(".txz")):
        output_name += ".tar.xz"
    elif format_choice == "7Z" and not output_name.lower().endswith(".7z"):
        output_name += ".7z"
    elif format_choice == "RAR" and not output_name.lower().endswith(".rar"):
        output_name += ".rar"
        
    output_path = valid_paths[0].parent / output_name
    send_to_trash(output_path)
    cwd = valid_paths[0].parent
    
    # Use relative paths for command to avoid absolute paths in archive
    rel_paths = []
    for p in valid_paths:
        try:
            rel_paths.append(str(p.relative_to(cwd)))
        except ValueError:
            # If not in same directory tree, use absolute path (less ideal but necessary)
            rel_paths.append(str(p))
    
    sevenzip_exec = "7z"
    if not shutil.which("7z") and shutil.which("7zz"):
        sevenzip_exec = "7zz"

    required_exec = {
        "ZIP": "zip",
        "TAR.GZ": "tar",
        "TAR.BZ2": "tar",
        "TAR.XZ": "tar",
        "7Z": sevenzip_exec,
        "RAR": "rar",
    }.get(format_choice)

    if required_exec:
        if not shutil.which(required_exec):
            if format_choice == "7Z":
                return False, "7-Zip is not installed on your system.\nTo install it, run:\n   brew install sevenzip", None
            elif required_exec == "rar":
                return False, "RAR archiver is not installed on your system.\nTo install it, run:\n   brew install --cask rar\nOr download it from: https://www.rarlab.com/download.htm", None
            else:
                return False, f"Required utility '{required_exec}' is not installed on your system.", None

    if format_choice == "ZIP":
        if password:
            cmd = ["zip", "-P", password, "-r", str(output_path)] + rel_paths
        else:
            cmd = ["zip", "-r", str(output_path)] + rel_paths
    elif format_choice == "TAR.GZ":
        cmd = ["tar", "-czf", str(output_path)] + rel_paths
    elif format_choice == "TAR.BZ2":
        cmd = ["tar", "-cjf", str(output_path)] + rel_paths
    elif format_choice == "TAR.XZ":
        cmd = ["tar", "-cJf", str(output_path)] + rel_paths
    elif format_choice == "7Z":
        cmd = [sevenzip_exec, "a", str(output_path)] + rel_paths
        if password:
            cmd.insert(2, f"-p{password}")
    elif format_choice == "RAR":
        cmd = ["rar", "a", str(output_path)] + rel_paths
        if password:
            cmd.insert(2, f"-p{password}")
    else:
        return False, f"Unsupported format: {format_choice}", None

    success, error = run_command(cmd, cwd=cwd)
    return success, error, output_path
