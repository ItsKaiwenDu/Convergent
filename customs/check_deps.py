#!/usr/bin/env python3
import subprocess
import sys
import re
import shutil
import os
import shlex
import importlib.util
from pathlib import Path

from customs.console import console, get_char

def get_command_output(cmd):
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return result.stdout.strip()
    except FileNotFoundError:
        return None

def get_imagemagick_version():
    output = get_command_output(["magick", "-version"])
    if not output:
        output = get_command_output(["convert", "-version"])
    if output:
        match = re.search(r"Version: ImageMagick ([\d\.\-]+)", output)
        return match.group(1) if match else "Found"
    return None

def get_libreoffice_version():
    import os
    soffice_path = None
    if sys.platform == "darwin":
        app_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        if os.path.exists(app_path):
            soffice_path = app_path
            
    if not soffice_path:
        soffice_path = shutil.which("soffice") or shutil.which("libreoffice")
        
    if soffice_path:
        output = get_command_output([soffice_path, "--version"])
        if output:
            match = re.search(r"LibreOffice ([\d\.]+)", output)
            return match.group(1) if match else "Found"
    return None

def get_whisper_version():
    import os
    candidates = [
        "whisper-cli",
        "whisper-cpp",
        "whisper.cpp",
        "whisper",
    ]
    for cand in candidates:
        if shutil.which(cand):
            return "Found"
    for p in ["/opt/homebrew/bin/whisper-cli", "/opt/homebrew/bin/whisper-cpp", "/usr/local/bin/whisper-cli"]:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return "Found"
    return None

DEPENDENCIES = {
    "ffmpeg": ("FFmpeg", ("ffmpeg", "ffprobe")),
    "imagemagick": ("ImageMagick", ("magick", "convert")),
    "imagemagick7": ("ImageMagick 7", ("magick",)),
    "ghostscript": ("Ghostscript", ("gs",)),
    "pandoc": ("Pandoc", ("pandoc",)),
    "typst": ("Typst", ("typst",)),
    "libreoffice": ("LibreOffice", ("soffice", "libreoffice")),
    "tesseract": ("Tesseract", ("tesseract",)),
    "whisper": ("whisper.cpp", ("whisper-cli", "whisper-cpp", "whisper.cpp")),
    "sevenzip": ("7-Zip", ("7zz", "7z")),
    "rar": ("RAR", ("rar",)),
    "zip": ("ZIP", ("zip",)),
    "unzip": ("Unzip", ("unzip",)),
    "tar": ("Tar", ("tar",)),
    "mcp": ("MCP Python SDK", ()),
}

PACKAGES = {
    "brew": dict(ffmpeg="ffmpeg", imagemagick="imagemagick", imagemagick7="imagemagick",
                 ghostscript="ghostscript", pandoc="pandoc", typst="typst",
                 libreoffice="libreoffice", tesseract="tesseract", whisper="whisper-cpp",
                 sevenzip="sevenzip", rar="rar", zip="zip", unzip="unzip", tar="gnu-tar"),
    "apt": dict(ffmpeg="ffmpeg", imagemagick="imagemagick", ghostscript="ghostscript",
                pandoc="pandoc", libreoffice="libreoffice", tesseract="tesseract-ocr",
                sevenzip="p7zip-full", rar="rar", zip="zip", unzip="unzip", tar="tar"),
    "dnf": dict(ffmpeg="ffmpeg", imagemagick="ImageMagick", imagemagick7="ImageMagick",
                ghostscript="ghostscript", pandoc="pandoc", typst="typst",
                libreoffice="libreoffice", tesseract="tesseract", sevenzip="p7zip",
                rar="rar", zip="zip", unzip="unzip", tar="tar"),
    "pacman": dict(ffmpeg="ffmpeg", imagemagick="imagemagick", imagemagick7="imagemagick",
                   ghostscript="ghostscript", pandoc="pandoc", typst="typst",
                   libreoffice="libreoffice-fresh", tesseract="tesseract", sevenzip="7zip",
                   zip="zip", unzip="unzip", tar="tar"),
}


class MissingDependencyError(RuntimeError):
    pass


def dependency_available(name):
    if name == "mcp":
        return importlib.util.find_spec("mcp") is not None
    if name == "libreoffice" and sys.platform == "darwin":
        if Path("/Applications/LibreOffice.app/Contents/MacOS/soffice").is_file():
            return True
    commands = DEPENDENCIES[name][1]
    if name == "ffmpeg":
        return all(shutil.which(command) for command in commands)
    return any(shutil.which(command) for command in commands)


def install_command(name, interactive=False):
    if name == "mcp":
        return [sys.executable, "-m", "pip", "install", "mcp>=1.0.0,<2.0.0"]
    managers = ("brew",) if sys.platform == "darwin" else ("apt", "dnf", "pacman")
    for manager in managers:
        executable = shutil.which(manager)
        if not executable:
            continue
        package = PACKAGES[manager].get(name)
        if not package:
            return None
        if manager == "brew":
            cask = ["--cask"] if name in ("libreoffice", "rar") else []
            return [executable, "install", *cask, package]
        prefix = [] if os.geteuid() == 0 else ["sudo", *([] if interactive else ["-n"])]
        flags = ["-S", "--noconfirm", "--needed"] if manager == "pacman" else ["install", "-y"]
        return [*prefix, executable, *flags, package]
    return None


def ensure_dependencies(names, interactive=False, install=False):
    missing = [name for name in dict.fromkeys(names) if not dependency_available(name)]
    if not missing:
        return True
    interactive = interactive and sys.stdin.isatty()
    labels = ", ".join(DEPENDENCIES[name][0] for name in missing)
    hint = "python3 -m customs.check_deps --install " + " ".join(missing)
    if not interactive and not install:
        raise MissingDependencyError(f"This operation requires: {labels}. Install with: {hint}")

    commands = [(name, install_command(name, interactive=interactive)) for name in missing]
    unavailable = [DEPENDENCIES[name][0] for name, command in commands if command is None]
    if unavailable:
        message = ("Automatic installation is unavailable for: " + ", ".join(unavailable)
                   + ". Install these tools manually and retry.")
        if not interactive:
            raise MissingDependencyError(message)
        console.print(f"[bold red]{message}[/bold red]")
        return False

    console.print(f"\n[bold yellow]This operation requires: {labels}[/bold yellow]")
    for _, command in commands:
        console.print(shlex.join(command), style="dim", markup=False)
    if interactive and not install:
        console.print(" [bold cyan]Y.[/bold cyan] Install and continue   [bold white]N.[/bold white] Cancel")
        choice = get_char("\nSelect Option: ").lower()
        console.print()
        if choice != "y":
            console.print("[dim]Installation cancelled.[/dim]")
            return False

    for name, command in commands:
        label = DEPENDENCIES[name][0]
        console.print(f"[bold cyan]Installing {label}...[/bold cyan]")
        try:
            result = subprocess.run(command, stdin=None if interactive else subprocess.DEVNULL,
                                    stdout=sys.stderr, stderr=sys.stderr)
            if result.returncode or not dependency_available(name):
                raise MissingDependencyError(f"Could not install {label}. Check installer output and retry: {hint}")
        except (OSError, MissingDependencyError) as exc:
            if not interactive:
                raise MissingDependencyError(str(exc)) from exc
            console.print(str(exc), style="bold red", markup=False)
            return False
        console.print(f"[bold green]✓ {label} is ready.[/bold green]")
    return True


def check_dependencies():
    for name, (label, _) in DEPENDENCIES.items():
        if name == "imagemagick7":
            continue
        if dependency_available(name):
            console.print(f"[bold green]✓[/bold green] {label}")
        else:
            console.print(f"[dim]○ {label} — installed when needed[/dim]")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Check or install Convergent's optional tools")
    parser.add_argument("--install", nargs="+", choices=DEPENDENCIES, metavar="TOOL")
    args = parser.parse_args()
    if args.install:
        from customs.console import set_stderr_mode
        set_stderr_mode(True)
        try:
            ensure_dependencies(args.install, interactive=sys.stdin.isatty(), install=True)
        except MissingDependencyError as exc:
            console.print(str(exc), style="bold red", markup=False)
            sys.exit(1)
    else:
        check_dependencies()
