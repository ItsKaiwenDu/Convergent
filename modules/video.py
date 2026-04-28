import subprocess
from pathlib import Path

def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)

def convert_video(source, target_ext, fps=None):
    output = source.with_suffix(f".{target_ext.lower()}")
    cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
    if target_ext.upper() == "MP4":
        cmd += ["-c:v", "libx264", "-c:a", "aac", "-strict", "experimental"]
    elif target_ext.upper() == "GIF":
        vf = "scale=480:-1:flags=lanczos"
        if fps:
            vf = f"fps={fps}," + vf
        cmd += ["-vf", vf]
    elif target_ext.upper() == "MP3":
        cmd += ["-vn", "-acodec", "libmp3lame", "-q:a", "2"]
    
    cmd.append(str(output))
    return run_command(cmd)
