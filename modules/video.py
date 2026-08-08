from pathlib import Path
from customs.run_command import run_command
from customs.hwaccel import get_video_encoder

def convert_video(source, target_ext, fps=None, bitrate=None, hwaccel="auto"):
    output = source.with_suffix(f".{target_ext.lower()}")
    target_upper = target_ext.upper()
    cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]

    if target_upper in ("MP4", "MOV", "MKV"):
        encoder, extra_flags, mode_tag = get_video_encoder(target_upper, hwaccel)
        cmd += ["-c:v", encoder] + extra_flags + ["-c:a", "aac"]
        cmd.append(str(output))

        success, err = run_command(cmd)
        if success:
            return True, ""
        
        # Hardware transcode failed; fallback to software libx264
        if encoder != "libx264":
            fallback_cmd = [
                "ffmpeg", "-i", str(source), "-y", "-loglevel", "error",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-strict", "experimental", str(output)
            ]
            success_fb, err_fb = run_command(fallback_cmd)
            if success_fb:
                return True, ""
            return False, f"Hardware encoding failed ({err}); software fallback also failed ({err_fb})"
        return False, err

    elif target_upper == "WEBM":
        cmd += ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30", "-c:a", "libopus"]
    elif target_upper == "GIF":
        vf = "scale=480:-1:flags=lanczos"
        if fps:
            vf = f"fps={fps}," + vf
        cmd += ["-vf", vf]
    elif target_upper == "MP3":
        if bitrate in ["128k", "192k", "320k"]:
            cmd += ["-vn", "-acodec", "libmp3lame", "-b:a", bitrate]
        else:
            cmd += ["-vn", "-acodec", "libmp3lame", "-q:a", "2"]
    elif target_upper == "WAV":
        cmd += ["-vn", "-acodec", "pcm_s16le"]
    elif target_upper == "M4A":
        cmd += ["-vn", "-acodec", "aac", "-q:a", "2"]

    cmd.append(str(output))
    return run_command(cmd)

