import json
import time
import subprocess
from pathlib import Path
from customs.run_command import run_command

CACHE_FILE = Path.home() / ".convergent_hwcache.json"
CACHE_TTL = 7 * 86400  # 7 days in seconds

_cached_capabilities = None


def detect_capabilities(force_refresh=False):
    """
    Probes FFmpeg for hardware acceleration capabilities and caches the result.
    """
    global _cached_capabilities

    if not force_refresh and _cached_capabilities is not None:
        return _cached_capabilities

    if not force_refresh and CACHE_FILE.exists():
        try:
            mtime = CACHE_FILE.stat().st_mtime
            if time.time() - mtime < CACHE_TTL:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    _cached_capabilities = json.load(f)
                    return _cached_capabilities
        except Exception:
            pass

    capabilities = {
        "videotoolbox": False,
        "nvenc": False,
        "qsv": False,
        "vaapi": False,
    }

    try:
        # Check encoders
        res = subprocess.run(
            ["ffmpeg", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        encoders_output = res.stdout if res.returncode == 0 else ""

        if "h264_videotoolbox" in encoders_output:
            capabilities["videotoolbox"] = True
        if "h264_nvenc" in encoders_output:
            capabilities["nvenc"] = True
        if "h264_qsv" in encoders_output:
            capabilities["qsv"] = True
        if "h264_vaapi" in encoders_output:
            capabilities["vaapi"] = True

    except Exception:
        pass

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(capabilities, f)
    except Exception:
        pass

    _cached_capabilities = capabilities
    return capabilities


def get_video_encoder(target_ext, mode="auto"):
    """
    Returns a tuple of (encoder_name, extra_flags, mode_tag) for the target format
    based on system hardware acceleration capabilities and user mode choice.

    - target_ext: e.g. "MP4", "MOV", "MKV", "WEBM"
    - mode: "auto", "videotoolbox", "nvenc", "qsv", "none"
    """
    ext = target_ext.upper()
    mode = (mode or "auto").lower()

    if ext not in ("MP4", "MOV", "MKV"):
        if ext == "WEBM":
            return ("libvpx-vp9", ["-b:v", "0", "-crf", "30"], "🐢 libvpx-vp9")
        return (None, [], "")

    if mode == "none":
        return ("libx264", ["-pix_fmt", "yuv420p"], "🐢 libx264")

    caps = detect_capabilities()

    use_vt = (mode == "videotoolbox") or (mode == "auto" and caps.get("videotoolbox"))
    use_nvenc = (mode == "nvenc") or (mode == "auto" and not use_vt and caps.get("nvenc"))
    use_qsv = (mode == "qsv") or (mode == "auto" and not use_vt and not use_nvenc and caps.get("qsv"))

    if use_vt:
        if ext in ("MP4", "MOV", "MKV"):
            return (
                "h264_videotoolbox",
                ["-allow_sw", "1", "-b:v", "8M", "-pix_fmt", "yuv420p"],
                "⚡ videotoolbox",
            )
    elif use_nvenc:
        return ("h264_nvenc", ["-pix_fmt", "yuv420p"], "⚡ nvenc")
    elif use_qsv:
        return ("h264_qsv", ["-pix_fmt", "yuv420p"], "⚡ qsv")

    return ("libx264", ["-pix_fmt", "yuv420p"], "🐢 libx264")
