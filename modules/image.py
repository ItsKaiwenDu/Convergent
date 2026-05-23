import subprocess
import sys
from pathlib import Path
from customs.run_command import run_command

def convert_heic(source, target_ext):
    output = source.with_suffix(f".{target_ext.lower()}")
    return run_command(["magick", str(source), str(output)])

def convert_image(source, target_ext):
    output = source.with_suffix(f".{target_ext.lower()}")
    
    # SVG conversion with high quality density and transparency flattening settings
    if source.suffix.lower() == ".svg":
        target_upper = target_ext.upper()
        if target_upper in ("JPG", "JPEG"):
            # For JPG/JPEG, since they do not support transparency, flatten on a clean white background
            return run_command(["magick", "-density", "300", "-background", "white", str(source), "-alpha", "remove", "-alpha", "off", str(output)])
        else:
            # For formats supporting transparency (PNG, WEBP, PDF), maintain transparent background
            return run_command(["magick", "-density", "300", "-background", "none", str(source), str(output)])

    # Use sips on macOS for better RAW support if magick fails or specifically for ARW/DNG
    if sys.platform == "darwin" and source.suffix.lower() in (".arw", ".dng"):
        # sips supports: jpeg, tiff, png, gif, jp2, pict, bmp, qtif, psd, sgi, tga, pdf
        sips_targets = {
            "JPG": "jpeg",
            "JPEG": "jpeg",
            "PNG": "png",
            "TIFF": "tiff",
            "TIF": "tiff",
            "BMP": "bmp",
            "GIF": "gif",
            "PDF": "pdf"
        }
        target_upper = target_ext.upper()
        if target_upper in sips_targets:
            return run_command(["sips", "-s", "format", sips_targets[target_upper], str(source), "--out", str(output)])
        elif target_upper == "WEBP":
            # Convert to temp PNG first using sips, then use magick to convert PNG to WEBP
            temp_png = source.with_suffix(".temp.png")
            try:
                success, err = run_command(["sips", "-s", "format", "png", str(source), "--out", str(temp_png)])
                if not success:
                    return False, f"Failed to convert raw to temp PNG: {err}"
                
                success, err = run_command(["magick", str(temp_png), str(output)])
                return success, err
            finally:
                if temp_png.exists():
                    temp_png.unlink()
            
    return run_command(["magick", str(source), str(output)])
