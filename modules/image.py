import subprocess
from pathlib import Path
from customs.run_command import run_command

def convert_heic(source, target_ext):
    output = source.with_suffix(f".{target_ext.lower()}")
    return run_command(["magick", str(source), str(output)])

def convert_image(source, target_ext):
    output = source.with_suffix(f".{target_ext.lower()}")
    return run_command(["magick", str(source), str(output)])
