import subprocess
import sys
from pathlib import Path
from customs.run_command import run_command

def convert_heic(source, target_ext, strip_metadata=False):
    output = source.with_suffix(f".{target_ext.lower()}")
    cmd = ["magick", str(source), "-auto-orient"]
    if strip_metadata:
        cmd.append("-strip")
    cmd.append(str(output))
    return run_command(cmd)

def convert_image(source, target_ext, strip_metadata=False):
    output = source.with_suffix(f".{target_ext.lower()}")
    
    # SVG conversion with high quality density and transparency flattening settings
    if source.suffix.lower() == ".svg":
        target_upper = target_ext.upper()
        if target_upper in ("JPG", "BMP"):
            # For JPG/BMP, since they do not support transparency, flatten on a clean white background
            cmd = ["magick", "-density", "300", "-background", "white", str(source), "-alpha", "remove", "-alpha", "off"]
            if strip_metadata:
                cmd.append("-strip")
            cmd.append(str(output))
            return run_command(cmd)
        else:
            # For formats supporting transparency (PNG, WEBP, PDF), maintain transparent background
            cmd = ["magick", "-density", "300", "-background", "none", str(source)]
            if strip_metadata:
                cmd.append("-strip")
            cmd.append(str(output))
            return run_command(cmd)

    # Use sips on macOS for better RAW support if magick fails or specifically for ARW/DNG
    if sys.platform == "darwin" and source.suffix.lower() in (".arw", ".dng"):
        # sips supports: jpeg, tiff, png, gif, jp2, pict, bmp, qtif, psd, sgi, tga, pdf
        sips_targets = {
            "JPG": "jpeg",
            "PNG": "png",
            "TIFF": "tiff",
            "TIF": "tiff",
            "BMP": "bmp",
            "GIF": "gif",
            "PDF": "pdf"
        }
        target_upper = target_ext.upper()
        if target_upper in sips_targets:
            res, err = run_command(["sips", "-s", "format", sips_targets[target_upper], str(source), "--out", str(output)])
            if res and strip_metadata:
                # Strip output file post-hoc using magick
                run_command(["magick", str(output), "-strip", str(output)])
            return res, err
        elif target_upper == "WEBP":
            # Convert to temp PNG first using sips, then use magick to convert PNG to WEBP
            temp_png = source.with_suffix(".temp.png")
            try:
                success, err = run_command(["sips", "-s", "format", "png", str(source), "--out", str(temp_png)])
                if not success:
                    return False, f"Failed to convert raw to temp PNG: {err}"
                
                cmd = ["magick", str(temp_png), "-auto-orient"]
                if strip_metadata:
                    cmd.append("-strip")
                cmd.append(str(output))
                success, err = run_command(cmd)
                return success, err
            finally:
                if temp_png.exists():
                    temp_png.unlink()
            
    cmd = ["magick", str(source), "-auto-orient"]
    if strip_metadata:
        cmd.append("-strip")
    cmd.append(str(output))
    return run_command(cmd)
