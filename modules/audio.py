import subprocess
from pathlib import Path
from customs.run_command import run_command

def convert_audio(source, target_ext):
    output = source.with_suffix(f".{target_ext.lower()}")
    cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
    if target_ext.upper() == "MP3":
        cmd += ["-acodec", "libmp3lame", "-q:a", "2"]
    elif target_ext.upper() == "M4A":
        cmd += ["-acodec", "aac", "-q:a", "2"]
    elif target_ext.upper() == "WAV":
        cmd += ["-acodec", "pcm_s16le"]
    
    cmd.append(str(output))
    return run_command(cmd)
