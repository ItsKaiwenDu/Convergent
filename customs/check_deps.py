#!/usr/bin/env python3
import subprocess
import sys
import re

GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

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

def check_dependencies():
    deps = [
        {
            "name": "FFmpeg",
            "cmd": ["ffmpeg", "-version"],
            "version_regex": r"ffmpeg version ([\d\.]+)",
            "install_hint": "brew install ffmpeg"
        },
        {
            "name": "ImageMagick",
            "custom_func": get_imagemagick_version,
            "install_hint": "brew install imagemagick"
        },
        {
            "name": "Ghostscript",
            "cmd": ["gs", "--version"],
            "version_regex": r"([\d\.]+)",
            "install_hint": "brew install ghostscript"
        },
        {
            "name": "Pandoc",
            "cmd": ["pandoc", "--version"],
            "version_regex": r"pandoc ([\d\.]+)",
            "install_hint": "brew install pandoc"
        },
        {
            "name": "Typst",
            "cmd": ["typst", "--version"],
            "version_regex": r"typst ([\d\.]+)",
            "install_hint": "brew install typst"
        }
    ]

    all_found = True
    print("")
    for dep in deps:
        if "custom_func" in dep:
            version = dep["custom_func"]()
        else:
            output = get_command_output(dep["cmd"])
            if output:
                match = re.search(dep["version_regex"], output)
                version = match.group(1) if match else "Found"
            else:
                version = None

        if version:
            print(f"{dep['name']:<13} {GREEN}✓{RESET}  {version}")
        else:
            all_found = False
            print(f"{dep['name']:<13} {RED}✗{RESET}  NOT FOUND - {dep['install_hint']}")
    print("")
    
    if not all_found:
        sys.exit(1)

if __name__ == "__main__":
    check_dependencies()
