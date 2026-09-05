import subprocess
import sys
import shutil
from pathlib import Path
from customs.run_command import run_command

def convert_heic(source, target_ext, strip_metadata=False):
    output = source.with_suffix(f".{target_ext.lower()}")
    target_upper = target_ext.upper()
    
    # On macOS, sips natively handles HEIC conversion to common formats
    if sys.platform == "darwin" and shutil.which("sips"):
        sips_targets = {
            "JPG": "jpeg",
            "PNG": "png",
            "TIF": "tiff",
            "BMP": "bmp",
            "GIF": "gif",
            "PDF": "pdf"
        }
        if target_upper in sips_targets:
            res, err = run_command(["sips", "-s", "format", sips_targets[target_upper], str(source), "--out", str(output)])
            if res:
                if strip_metadata and shutil.which("magick"):
                    run_command(["magick", str(output), "-strip", str(output)])
                return True, ""

    cmd_name = "magick" if shutil.which("magick") else ("convert" if shutil.which("convert") else "magick")
    cmd = [cmd_name, str(source), "-auto-orient"]
    if strip_metadata:
        cmd.append("-strip")
    cmd.append(str(output))
    return run_command(cmd)

def convert_image(source, target_ext, strip_metadata=False):
    output = source.with_suffix(f".{target_ext.lower()}")
    target_upper = target_ext.upper()
    cmd_name = "magick" if shutil.which("magick") else ("convert" if shutil.which("convert") else "magick")
    
    is_inplace = (source.resolve() == output.resolve())
    target_dest = output
    if is_inplace:
        output = source.with_name(f"{source.stem}.tmp_conv_{target_ext.lower()}")
    
    res, err = False, ""
    try:
        # SVG conversion with high quality density and transparency flattening settings
        if source.suffix.lower() == ".svg":
            if target_upper in ("JPG", "BMP"):
                # For JPG/BMP, since they do not support transparency, flatten on a clean white background
                cmd = [cmd_name, "-density", "300", "-background", "white", str(source), "-alpha", "remove", "-alpha", "off"]
                if strip_metadata:
                    cmd.append("-strip")
                cmd.append(str(output))
                res, err = run_command(cmd)
            else:
                # For formats supporting transparency (PNG, WEBP, PDF), maintain transparent background
                cmd = [cmd_name, "-density", "300", "-background", "none", str(source)]
                if strip_metadata:
                    cmd.append("-strip")
                cmd.append(str(output))
                res, err = run_command(cmd)

        # Use sips on macOS when available for supported formats
        elif sys.platform == "darwin" and shutil.which("sips"):
            sips_targets = {
                "JPG": "jpeg",
                "PNG": "png",
                "TIF": "tiff",
                "BMP": "bmp",
                "GIF": "gif",
                "PDF": "pdf"
            }
            if target_upper in sips_targets:
                res, err = run_command(["sips", "-s", "format", sips_targets[target_upper], str(source), "--out", str(output)])
                if res and strip_metadata and shutil.which("magick"):
                    run_command(["magick", str(output), "-strip", str(output)])
            elif target_upper == "WEBP" and source.suffix.lower() in (".arw", ".dng"):
                # Convert to temp PNG first using sips, then use magick to convert PNG to WEBP
                temp_png = source.with_suffix(".temp.png")
                try:
                    success, sips_err = run_command(["sips", "-s", "format", "png", str(source), "--out", str(temp_png)])
                    if not success:
                        res, err = False, f"Failed to convert raw to temp PNG: {sips_err}"
                    else:
                        cmd = [cmd_name, str(temp_png), "-auto-orient"]
                        if strip_metadata:
                            cmd.append("-strip")
                        cmd.append(str(output))
                        res, err = run_command(cmd)
                finally:
                    if temp_png.exists():
                        temp_png.unlink()
            else:
                cmd = [cmd_name, str(source), "-auto-orient"]
                if strip_metadata:
                    cmd.append("-strip")
                cmd.append(str(output))
                res, err = run_command(cmd)
        else:
            cmd = [cmd_name, str(source), "-auto-orient"]
            if strip_metadata:
                cmd.append("-strip")
            cmd.append(str(output))
            res, err = run_command(cmd)

        if is_inplace:
            if res and output.exists():
                output.replace(target_dest)
            elif output.exists():
                output.unlink()

        return res, err
    except Exception as e:
        if is_inplace and output.exists():
            output.unlink()
        return False, str(e)

