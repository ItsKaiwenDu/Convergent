import re
import subprocess
import functools
from pathlib import Path
from customs.run_command import run_command

def required_dependencies(source_format, target_format, **options):
    return ["ffmpeg"]


@functools.lru_cache(maxsize=1)
def get_ogg_audio_encoder_args():
    try:
        res = subprocess.run(["ffmpeg", "-h", "encoder=libvorbis"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if res.returncode == 0 and "not recognized" not in res.stdout and "not recognized" not in res.stderr:
            return ["-c:a", "libvorbis"]
    except Exception:
        pass
    return ["-c:a", "libopus"]


def convert_audio(source, target_ext, bitrate=None):
    output = source.with_suffix(f".{target_ext.lower()}")
    cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
    target_upper = target_ext.upper()
    if target_upper == "MP3":
        if bitrate and re.match(r"^\d+k?$", str(bitrate).lower()):
            b_val = str(bitrate).lower() if str(bitrate).lower().endswith("k") else f"{bitrate}k"
            cmd += ["-acodec", "libmp3lame", "-b:a", b_val]
        else:
            cmd += ["-acodec", "libmp3lame", "-q:a", "2"]
    elif target_upper == "M4A":
        cmd += ["-acodec", "aac", "-q:a", "2"]
    elif target_upper == "WAV":
        cmd += ["-acodec", "pcm_s16le"]
    elif target_upper == "FLAC":
        cmd += ["-acodec", "flac"]
    elif target_upper == "OGG":
        cmd += get_ogg_audio_encoder_args()
    
    cmd.append(str(output))
    return run_command(cmd)

