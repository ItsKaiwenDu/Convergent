from pathlib import Path
from customs.run_command import run_command

def convert_video(source, target_ext, fps=None, bitrate=None):
    output = source.with_suffix(f".{target_ext.lower()}")
    cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
    if target_ext.upper() == "MP4":
        cmd += ["-c:v", "libx264", "-c:a", "aac", "-strict", "experimental"]
    elif target_ext.upper() == "WEBM":
        cmd += ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30", "-c:a", "libopus"]
    elif target_ext.upper() == "MKV":
        cmd += ["-c:v", "libx264", "-c:a", "aac"]
    elif target_ext.upper() == "GIF":
        vf = "scale=480:-1:flags=lanczos"
        if fps:
            vf = f"fps={fps}," + vf
        cmd += ["-vf", vf]
    elif target_ext.upper() == "MP3":
        if bitrate in ["128k", "192k", "320k"]:
            cmd += ["-vn", "-acodec", "libmp3lame", "-b:a", bitrate]
        else:
            cmd += ["-vn", "-acodec", "libmp3lame", "-q:a", "2"]
    elif target_ext.upper() == "WAV":
        cmd += ["-vn", "-acodec", "pcm_s16le"]
    elif target_ext.upper() == "M4A":
        cmd += ["-vn", "-acodec", "aac", "-q:a", "2"]
    
    cmd.append(str(output))
    return run_command(cmd)
