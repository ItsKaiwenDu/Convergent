from pathlib import Path
from customs.run_command import run_command

def convert_audio(source, target_ext, bitrate=None):
    output = source.with_suffix(f".{target_ext.lower()}")
    cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
    if target_ext.upper() == "MP3":
        if bitrate in ["128k", "192k", "320k"]:
            cmd += ["-acodec", "libmp3lame", "-b:a", bitrate]
        else:
            cmd += ["-acodec", "libmp3lame", "-q:a", "2"]
    elif target_ext.upper() == "M4A":
        cmd += ["-acodec", "aac", "-q:a", "2"]
    elif target_ext.upper() == "WAV":
        cmd += ["-acodec", "pcm_s16le"]
    elif target_ext.upper() == "FLAC":
        cmd += ["-acodec", "flac"]
    
    cmd.append(str(output))
    return run_command(cmd)
