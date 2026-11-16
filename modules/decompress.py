import os
import subprocess
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple
from customs.run_command import run_command, run_command_output, send_to_trash

COMPOUND_ARCHIVE_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst")


def archive_stem(path: Path) -> str:
    """Return archive stem, stripping compound tar suffixes like .tar.gz."""
    name = path.name
    lower_name = name.lower()
    for suffix in COMPOUND_ARCHIVE_SUFFIXES:
        if lower_name.endswith(suffix):
            return name[: -len(suffix)] or path.stem
    return path.stem


def required_dependencies(path):
    name = str(path).lower()
    if name.endswith(".zip"):
        return ["unzip"]
    if name.endswith((".rar", ".7z")):
        return [] if name.endswith(".rar") and shutil.which("unrar") else ["sevenzip"]
    return ["tar"]


def decompress(path, output_dir=None, password=None):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.exists():
        return False, f"Path does not exist: {path}", None
    
    if not output_dir:
        output_dir = path_obj.parent / archive_stem(path_obj)
        send_to_trash(output_dir)
    else:
        output_dir = Path(os.path.expanduser(str(output_dir))).resolve()
        
    output_dir.mkdir(parents=True, exist_ok=True)
    cwd = path_obj.parent
    
    sevenzip_exec = "7z"
    if not shutil.which("7z") and shutil.which("7zz"):
        sevenzip_exec = "7zz"

    ext = path_obj.name.lower()
    
    if ext.endswith(".zip"):
        if not shutil.which("unzip"):
            return False, "Required utility 'unzip' is not installed on your system.", None
        cmd = ["unzip", "-o"]
        if password:
            cmd.extend(["-P", str(password)])
        cmd.extend([str(path_obj), "-d", str(output_dir)])
    elif ext.endswith(".tar") or ext.endswith(".tar.gz") or ext.endswith(".tgz") or ext.endswith(".tar.bz2") or ext.endswith(".tbz2") or ext.endswith(".tar.xz") or ext.endswith(".txz"):
        if not shutil.which("tar"):
            return False, "Required utility 'tar' is not installed on your system.", None
        if ext.endswith(".tar.gz") or ext.endswith(".tgz"):
            cmd = ["tar", "-xzf", str(path_obj), "-C", str(output_dir)]
        elif ext.endswith(".tar.bz2") or ext.endswith(".tbz2"):
            cmd = ["tar", "-xjf", str(path_obj), "-C", str(output_dir)]
        elif ext.endswith(".tar.xz") or ext.endswith(".txz"):
            cmd = ["tar", "-xJf", str(path_obj), "-C", str(output_dir)]
        else:
            cmd = ["tar", "-xf", str(path_obj), "-C", str(output_dir)]
    elif ext.endswith(".7z"):
        if not shutil.which(sevenzip_exec):
            return False, "7-Zip is not installed on your system.\nTo install it, run:\n   brew install sevenzip", None
        cmd = [sevenzip_exec, "x", "-y"]
        if password:
            cmd.append(f"-p{password}")
        cmd.extend([str(path_obj), f"-o{str(output_dir)}"])
    elif ext.endswith(".rar"):
        if shutil.which("unrar"):
            cmd = ["unrar", "x", "-o+"]
            if password:
                cmd.append(f"-p{password}")
            cmd.extend([str(path_obj), f"{str(output_dir)}/"])
        elif shutil.which(sevenzip_exec):
            cmd = [sevenzip_exec, "x", "-y"]
            if password:
                cmd.append(f"-p{password}")
            cmd.extend([str(path_obj), f"-o{str(output_dir)}"])
        else:
            return False, f"Neither 'unrar' nor '{sevenzip_exec}' is installed on your system.\nTo extract RAR archives, please install 7-Zip by running:\n   brew install sevenzip", None
    else:
        return False, f"Unsupported or unknown archive format: {path_obj.name}", None

    success, error = run_command(cmd, cwd=cwd)
    return success, error, output_dir


def _sevenzip_exec() -> str:
    if not shutil.which("7z") and shutil.which("7zz"):
        return "7zz"
    return "7z"


def _parse_7z_slt_members(stdout: str) -> List[Tuple[str, bool]]:
    members: List[Tuple[str, bool]] = []
    in_entries = False
    cur_path: Optional[str] = None
    cur_is_dir = False

    def _flush():
        nonlocal cur_path, cur_is_dir
        if cur_path:
            members.append((cur_path, cur_is_dir))
        cur_path = None
        cur_is_dir = False

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not in_entries:
            if line == "----------":
                in_entries = True
            continue
        if not line:
            _flush()
            continue
        if line.startswith("Path = "):
            cur_path = line[len("Path = "):]
        elif line == "Folder = +":
            cur_is_dir = True
        elif line.startswith("Attributes = ") and line[len("Attributes = "):].startswith("D"):
            cur_is_dir = True
    _flush()
    return members


def _parse_unrar_lt_members(stdout: str) -> List[Tuple[str, bool]]:
    members: List[Tuple[str, bool]] = []
    cur_path: Optional[str] = None
    cur_is_dir = False

    def _flush():
        nonlocal cur_path, cur_is_dir
        if cur_path:
            members.append((cur_path, cur_is_dir))
        cur_path = None
        cur_is_dir = False

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("Name:"):
            _flush()
            cur_path = line[len("Name:"):].strip()
        elif line.startswith("Type:") and cur_path is not None:
            cur_is_dir = line[len("Type:"):].strip().lower() == "directory"
    _flush()
    return members


def list_archive_members(path, password=None) -> Optional[List[Tuple[str, bool]]]:
    """
    Lists archive entries as (relative_path, is_dir) tuples when inspection is supported.
    Returns None if the archive format/encryption prevents member inspection.
    """
    path_obj = Path(os.path.expanduser(str(path))).resolve()
    if not path_obj.is_file():
        return None

    ext = path_obj.name.lower()
    if ext.endswith(".zip"):
        try:
            with zipfile.ZipFile(path_obj, "r") as zf:
                return [(info.filename, info.is_dir()) for info in zf.infolist()]
        except Exception:
            return None

    if ext.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
        try:
            with tarfile.open(path_obj, "r:*") as tf:
                return [(m.name, m.isdir()) for m in tf.getmembers()]
        except Exception:
            return None

    pw_flag = f"-p{password}" if password else "-p-"
    if ext.endswith(".rar") and shutil.which("unrar"):
        code, stdout, _ = run_command_output(["unrar", "lt", pw_flag, str(path_obj)])
        if code == 0:
            return _parse_unrar_lt_members(stdout)

    sevenzip_exec = _sevenzip_exec()
    if ext.endswith((".7z", ".rar")) and shutil.which(sevenzip_exec):
        code, stdout, _ = run_command_output([sevenzip_exec, "l", "-slt", pw_flag, str(path_obj)])
        if code == 0:
            return _parse_7z_slt_members(stdout)

    return None


def find_extraction_collisions(archive_path, dest_dir: Path, password=None) -> Tuple[Optional[List[str]], bool]:
    """
    Checks whether extracting archive_path into dest_dir would overwrite existing files.
    Returns (colliding_relative_paths, inspected_successfully).
    """
    if not (dest_dir.exists() or dest_dir.is_symlink()):
        return [], True
    if not dest_dir.is_dir():
        return [dest_dir.name], True
    if not any(dest_dir.iterdir()):
        return [], True

    members = list_archive_members(archive_path, password=password)
    if members is None:
        return None, False

    collisions: List[str] = []
    seen = set()

    def _add(rel_str: str):
        if rel_str not in seen:
            seen.add(rel_str)
            collisions.append(rel_str)

    for member_name, is_dir in members:
        parts = [p for p in member_name.replace("\\", "/").split("/") if p not in ("", ".")]
        if not parts or any(p == ".." for p in parts):
            continue
        rel = Path(*parts)
        for parent in rel.parents:
            if parent == Path("."):
                continue
            p_target = dest_dir / parent
            if (p_target.exists() or p_target.is_symlink()) and not p_target.is_dir():
                _add(str(parent))
        target = dest_dir / rel
        if is_dir:
            if (target.exists() or target.is_symlink()) and not target.is_dir():
                _add(str(rel))
        elif target.exists() or target.is_symlink():
            _add(str(rel))

    return collisions, True
