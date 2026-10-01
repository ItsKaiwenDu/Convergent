from pathlib import Path
from customs.run_command import run_command
from customs.hwaccel import get_video_encoder

def required_dependencies(source_format, target_format, **options):
    return ["ffmpeg"]


def convert_video(source, target_ext, fps=None, bitrate=None, hwaccel="auto"):
    output = source.with_suffix(f".{target_ext.lower()}")
    target_upper = target_ext.upper()
    cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]

    if target_upper in ("MP4", "MOV", "MKV"):
        encoder, extra_flags, mode_tag = get_video_encoder(target_upper, hwaccel)
        if bitrate:
            filtered_flags = []
            skip_next = False
            for flag in extra_flags:
                if skip_next:
                    skip_next = False
                    continue
                if flag == "-b:v":
                    skip_next = True
                    continue
                filtered_flags.append(flag)
            extra_flags = filtered_flags
        cmd += ["-c:v", encoder] + extra_flags + ["-c:a", "aac"]
        if fps:
            cmd += ["-r", str(fps)]
        if bitrate:
            cmd += ["-b:v", str(bitrate)]
        cmd.append(str(output))

        success, err = run_command(cmd)
        if success:
            return True, ""
        
        # Hardware transcode failed; fallback to software libx264
        if encoder != "libx264":
            fallback_cmd = [
                "ffmpeg", "-i", str(source), "-y", "-loglevel", "error",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-strict", "experimental"
            ]
            if fps:
                fallback_cmd += ["-r", str(fps)]
            if bitrate:
                fallback_cmd += ["-b:v", str(bitrate)]
            fallback_cmd.append(str(output))
            success_fb, err_fb = run_command(fallback_cmd)
            if success_fb:
                return True, ""
            return False, f"Hardware encoding failed ({err}); software fallback also failed ({err_fb})"
        return False, err

    elif target_upper == "WEBM":
        if bitrate:
            cmd += ["-c:v", "libvpx-vp9", "-c:a", "libopus"]
        else:
            cmd += ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30", "-c:a", "libopus"]
        if fps:
            cmd += ["-r", str(fps)]
        if bitrate:
            cmd += ["-b:v", str(bitrate)]
    elif target_upper == "GIF":
        vf = "scale=480:-1:flags=lanczos"
        if fps:
            vf = f"fps={fps}," + vf
        cmd += ["-vf", vf]
    elif target_upper == "MP3":
        import re
        if bitrate and re.match(r"^\d+k?$", str(bitrate).lower()):
            b_val = str(bitrate).lower() if str(bitrate).lower().endswith("k") else f"{bitrate}k"
            cmd += ["-vn", "-acodec", "libmp3lame", "-b:a", b_val]
        else:
            cmd += ["-vn", "-acodec", "libmp3lame", "-q:a", "2"]
    elif target_upper == "WAV":
        cmd += ["-vn", "-acodec", "pcm_s16le"]
    elif target_upper == "M4A":
        cmd += ["-vn", "-acodec", "aac", "-q:a", "2"]
    elif target_upper == "AAC":
        import re
        if bitrate and re.match(r"^\d+k?$", str(bitrate).lower()):
            b_val = str(bitrate).lower() if str(bitrate).lower().endswith("k") else f"{bitrate}k"
            cmd += ["-vn", "-c:a", "aac", "-b:a", b_val]
        else:
            cmd += ["-vn", "-c:a", "aac", "-b:a", "192k"]
    elif target_upper == "FLAC":
        cmd += ["-vn", "-c:a", "flac"]
    elif target_upper == "OGG":
        from modules.audio import get_ogg_audio_encoder_args
        cmd += ["-vn"] + get_ogg_audio_encoder_args()

    cmd.append(str(output))
    return run_command(cmd)

