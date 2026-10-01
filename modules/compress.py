import os
import uuid
import subprocess
import shutil
from pathlib import Path
from customs.run_command import run_command, send_to_trash

from customs.console import console

def required_dependencies(format_choice):
    if format_choice.startswith("TAR"):
        return ["tar"]
    return {"ZIP": ["zip"], "7Z": ["sevenzip"], "RAR": ["rar"]}.get(format_choice, [])


def compress(paths, output_name, format_choice, password=None, output_dir=None):
    if isinstance(paths, str):
        paths = [paths]
        
    path_objs = [Path(os.path.expanduser(p)).resolve() for p in paths]
    valid_paths = [p for p in path_objs if p.exists()]
    
    if not valid_paths:
        return False, "No valid paths provided for compression.", None
    
    if password and format_choice.startswith("TAR"):
        return False, "TAR archives do not support password encryption. Use ZIP or 7Z for password-protected archives.", None

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
        
    out_name_path = Path(os.path.expanduser(str(output_name)))
    if out_name_path.is_absolute() or out_name_path.parent != Path("."):
        output_path = out_name_path
    elif output_dir:
        dest_dir = Path(os.path.expanduser(str(output_dir))).resolve()
        output_path = dest_dir / output_name
    else:
        output_path = valid_paths[0].parent / output_name

    output_path = output_path.resolve()
    if any(p.resolve() == output_path for p in valid_paths):
        return False, "Output archive cannot be one of the input files to compress.", None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output_path.parent / f".tmp_{uuid.uuid4().hex[:8]}_{output_path.name}"
    
    staging_temp_dir = None
    try:
        try:
            common_root = Path(os.path.commonpath([p.parent.resolve() for p in valid_paths]))
            if common_root != Path(common_root.anchor):
                cwd = common_root
                rel_paths = [str(p.resolve().relative_to(cwd)) for p in valid_paths]
            else:
                raise ValueError("Common root is root directory")
        except Exception:
            import tempfile
            staging_temp_dir = tempfile.TemporaryDirectory()
            staging_path = Path(staging_temp_dir.name)
            cwd = staging_path
            rel_paths = []
            used_names = set()
            for p in valid_paths:
                target_name = p.name
                if target_name in used_names:
                    counter = 1
                    while f"{p.stem}_{counter}{p.suffix}" in used_names:
                        counter += 1
                    target_name = f"{p.stem}_{counter}{p.suffix}"
                used_names.add(target_name)
                staged_dest = staging_path / target_name
                if p.is_dir():
                    shutil.copytree(p, staged_dest)
                else:
                    try:
                        os.link(p, staged_dest)
                    except Exception:
                        shutil.copy2(p, staged_dest)
                rel_paths.append(target_name)
        
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
                cmd = ["zip", "-P", password, "-r", str(tmp_output)] + rel_paths
            else:
                cmd = ["zip", "-r", str(tmp_output)] + rel_paths
        elif format_choice == "TAR.GZ":
            cmd = ["tar", "-czf", str(tmp_output)] + rel_paths
        elif format_choice == "TAR.BZ2":
            cmd = ["tar", "-cjf", str(tmp_output)] + rel_paths
        elif format_choice == "TAR.XZ":
            cmd = ["tar", "-cJf", str(tmp_output)] + rel_paths
        elif format_choice == "7Z":
            cmd = [sevenzip_exec, "a", str(tmp_output)] + rel_paths
            if password:
                cmd.insert(2, f"-p{password}")
        elif format_choice == "RAR":
            cmd = ["rar", "a", str(tmp_output)] + rel_paths
            if password:
                cmd.insert(2, f"-p{password}")
        else:
            return False, f"Unsupported format: {format_choice}", None

        success, error = run_command(cmd, cwd=cwd)
        if success and tmp_output.exists():
            try:
                shutil.move(str(tmp_output), str(output_path))
                return True, "", output_path
            except Exception as e:
                if tmp_output.exists():
                    try:
                        tmp_output.unlink()
                    except Exception:
                        pass
                return False, str(e), None
        else:
            if tmp_output.exists():
                try:
                    tmp_output.unlink()
                except Exception:
                    pass
            return False, error or "Compression failed", None
    finally:
        if staging_temp_dir:
            staging_temp_dir.cleanup()
