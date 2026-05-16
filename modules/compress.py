import os
import subprocess
from pathlib import Path
from customs.run_command import run_command

try:
    from rich.console import Console
    console = Console()
except ImportError:
    from customs.console import MockConsole
    console = MockConsole()

def compress(paths, output_name, format_choice, password=None):
    if isinstance(paths, str):
        paths = [paths]
        
    path_objs = [Path(os.path.expanduser(p)).resolve() for p in paths]
    valid_paths = [p for p in path_objs if p.exists()]
    
    if not valid_paths:
        return False, "No valid paths provided for compression."
    
    if format_choice == "ZIP" and not output_name.lower().endswith(".zip"):
        output_name += ".zip"
    elif format_choice == "TAR.GZ" and not (output_name.lower().endswith(".tar.gz") or output_name.lower().endswith(".tgz")):
        output_name += ".tar.gz"
    elif format_choice == "7Z" and not output_name.lower().endswith(".7z"):
        output_name += ".7z"
    elif format_choice == "RAR" and not output_name.lower().endswith(".rar"):
        output_name += ".rar"
        
    output_path = valid_paths[0].parent / output_name
    cwd = valid_paths[0].parent
    
    # Use relative paths for the command to avoid absolute paths in the archive
    rel_paths = []
    for p in valid_paths:
        try:
            rel_paths.append(str(p.relative_to(cwd)))
        except ValueError:
            # If not in the same directory tree, use absolute path (less ideal but necessary)
            rel_paths.append(str(p))
    
    if format_choice == "ZIP":
        if password:
            cmd = ["zip", "-P", password, "-r", str(output_path)] + rel_paths
        else:
            cmd = ["zip", "-r", str(output_path)] + rel_paths
    elif format_choice == "TAR.GZ":
        cmd = ["tar", "-czf", str(output_path)] + rel_paths
    elif format_choice == "7Z":
        cmd = ["7z", "a", str(output_path)] + rel_paths
        if password:
            cmd.insert(2, f"-p{password}")
    elif format_choice == "RAR":
        cmd = ["rar", "a", str(output_path)] + rel_paths
        if password:
            cmd.insert(2, f"-p{password}")
    else:
        return False, f"Unsupported format: {format_choice}"

    return run_command(cmd, cwd=cwd)
