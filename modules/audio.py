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


def parse_audio_bitrate(bitrate):
    """
    Parses and normalizes audio bitrate strings to standard ffmpeg kbps format.
    Accepts:
      - '256k', '256K' -> '256k'
      - '1M', '1m', '0.256M' -> '1000k', '256k'
      - '256000' (raw bps) -> '256k'
      - '256' (kbps shorthand) -> '256k'
    Rejects:
      - 0, 0k, 0M, negative values, non-numeric strings
    Returns:
      (is_valid: bool, normalized_value: Optional[str])
    """
    if not bitrate:
        return True, None
    b_str = str(bitrate).strip()

    # Megabit format: 1M, 0.256M, 1m, 1.5M -> convert to integer kbps
    m_match = re.match(r"^(\d+(?:\.\d+)?)[mM]$", b_str)
    if m_match:
        val_m = float(m_match.group(1))
        if val_m <= 0:
            return False, None
        kbps = int(round(val_m * 1000))
        return True, f"{kbps}k"

    # Kilobit format: 256k, 256K, 128.5k
    k_match = re.match(r"^(\d+(?:\.\d+)?)[kK]$", b_str)
    if k_match:
        val_k = float(k_match.group(1))
        if val_k <= 0:
            return False, None
        kbps = int(round(val_k))
        return True, f"{kbps}k"

    # Raw integer without suffix: raw bps (>= 1000) or kbps shorthand (< 1000)
    if re.match(r"^\d+$", b_str):
        num = int(b_str)
        if num <= 0:
            return False, None
        if num >= 1000:
            return True, f"{num // 1000}k" if num % 1000 == 0 else f"{num}"
        else:
            return True, f"{num}k"

    return False, None


def convert_audio(source, target_ext, bitrate=None):
    output = source.with_suffix(f".{target_ext.lower()}")
    cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
    target_upper = target_ext.upper()
    if target_upper == "MP3":
        if bitrate is not None:
            valid, b_val = parse_audio_bitrate(bitrate)
            if not valid or not b_val:
                return False, f"Invalid bitrate '{bitrate}'. Examples of valid bitrates: '128k', '192k', '256k', '320k', '256000'."
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

