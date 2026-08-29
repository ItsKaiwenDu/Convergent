#!/usr/bin/env python3
import subprocess
import sys
import re
import shutil

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
        },
        {
            "name": "7-Zip (7z)",
            "cmd": ["7zz"] if shutil.which("7zz") else ["7z"],
            "version_regex": r"7-Zip.*?([\d\.]+)",
            "install_hint": "brew install sevenzip"
        },
        {
            "name": "unrar",
            "cmd": ["unrar"],
            "version_regex": r"UNRAR.*?([\d\.]+)",
            "install_hint": "brew install sevenzip (as fallback) or install unrar"
        },
        {
            "name": "rar",
            "cmd": ["rar"],
            "version_regex": r"RAR.*?([\d\.]+)",
            "install_hint": "install manually (e.g., from rarlab.com)"
        },
        {
            "name": "Tesseract (OCR)",
            "cmd": ["tesseract", "--version"],
            "version_regex": r"tesseract ([\d\.]+)",
            "install_hint": "brew install tesseract (Optional for image to text OCR conversion)",
            "optional": True
        },
        {
            "name": "Whisper (STT)",
            "custom_func": get_whisper_version,
            "install_hint": "brew install whisper-cpp (Optional for local Speech-to-Text transcription)",
            "optional": True
        },
        {
            "name": "LibreOffice",
            "custom_func": get_libreoffice_version,
            "install_hint": "brew install --cask libreoffice (Recommended for 1-to-1 Office document PDF conversion)",
            "optional": True
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
            if dep.get("optional"):
                YELLOW = '\033[93m'
                print(f"{dep['name']:<13} {YELLOW}⚠{RESET}  OPTIONAL NOT FOUND - {dep['install_hint']}")
            else:
                all_found = False
                print(f"{dep['name']:<13} {RED}✗{RESET}  NOT FOUND - {dep['install_hint']}")
    print("")
    
    if not all_found:
        sys.exit(1)

if __name__ == "__main__":
    check_dependencies()

