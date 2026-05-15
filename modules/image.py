import subprocess
import sys
from pathlib import Path
from customs.run_command import run_command

def convert_heic(source, target_ext):
    output = source.with_suffix(f".{target_ext.lower()}")
    return run_command(["magick", str(source), str(output)])

def convert_image(source, target_ext):
    output = source.with_suffix(f".{target_ext.lower()}")
    
    # Use sips on macOS for better RAW support if magick fails or specifically for ARW
    if sys.platform == "darwin" and source.suffix.lower() == ".arw":
        # sips supports: jpeg, tiff, png, gif, jp2, pict, bmp, qtif, psd, sgi, tga
        sips_targets = {
            "JPG": "jpeg",
            "JPEG": "jpeg",
            "PNG": "png",
            "TIFF": "tiff",
            "TIF": "tiff",
            "BMP": "bmp",
            "GIF": "gif"
        }
        target_upper = target_ext.upper()
        if target_upper in sips_targets:
            return run_command(["sips", "-s", "format", sips_targets[target_upper], str(source), "--out", str(output)])
            
    return run_command(["magick", str(source), str(output)])
