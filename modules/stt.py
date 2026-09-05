"""
Speech-to-Text (STT) Module for Convergent
-------------------------------------------
High-performance, local-first audio/video transcription utility.
Uses whisper.cpp / whisper-cli with local GGML model caching and FFmpeg audio preprocessing.
Zero heavy runtime dependencies (no PyTorch required).
"""

import os
import sys
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Tuple, Optional, List, Dict

# Local model cache directory
MODELS_DIR = Path.home() / ".cache" / "convergent" / "models"

# Standard GGML Whisper model download URLs
MODEL_URLS = {
    "tiny": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    "mini": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    "base": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    "standard": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    "small": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    "medium": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    "large-v3-turbo": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin",
    "turbo": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin",
    "large": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin",
}

# Approximate file sizes for display
MODEL_SIZES = {
    "tiny": "~75 MB",
    "mini": "~75 MB",
    "base": "~142 MB",
    "standard": "~142 MB",
    "small": "~466 MB",
    "medium": "~466 MB",
    "large-v3-turbo": "~1.5 GB",
    "turbo": "~1.5 GB",
    "large": "~1.5 GB",
}

# User-friendly display names for STT models
MODEL_DISPLAY_NAMES = {
    "base": "base (~142MB, daily use)",
    "standard": "base (~142MB, daily use)",
    "tiny": "tiny (~75MB, fastest speed)",
    "mini": "tiny (~75MB, fastest speed)",
    "small": "small (~466MB, better accuracy)",
    "medium": "small (~466MB, better accuracy)",
    "turbo": "turbo (~1.5GB, best accuracy)",
    "large": "turbo (~1.5GB, best accuracy)",
    "large-v3-turbo": "turbo (~1.5GB, best accuracy)",
}


def normalize_model_name(model_name: str) -> str:
    """Normalizes friendly model names and aliases to canonical Whisper model identifiers."""
    name = (model_name or "base").lower().strip()
    aliases = {
        "standard": "base",
        "mini": "tiny",
        "medium": "small",
        "large": "turbo",
        "large-turbo": "turbo",
    }
    return aliases.get(name, name)


def find_whisper_binary() -> Optional[str]:
    """
    Finds whisper binary in PATH or common Homebrew / system installation locations.
    Returns binary path or None if not found.
    """
    candidates = [
        "whisper-cli",
        "whisper-cpp",
        "whisper.cpp",
        "whisper",
    ]
    for cand in candidates:
        found = shutil.which(cand)
        if found:
            return found

    # Additional standard locations on macOS / Linux
    custom_paths = [
        "/opt/homebrew/bin/whisper-cli",
        "/opt/homebrew/bin/whisper-cpp",
        "/usr/local/bin/whisper-cli",
        "/usr/local/bin/whisper-cpp",
        Path.home() / ".local" / "bin" / "whisper-cli",
        Path.home() / ".local" / "bin" / "whisper-cpp",
    ]
    for p in custom_paths:
        p_obj = Path(p)
        if p_obj.exists() and os.access(p_obj, os.X_OK):
            return str(p_obj)

    return None


def get_model_path(model_name: str = "base", auto_download: bool = True) -> Path:
    """
    Resolves local path for a GGML Whisper model.
    If model does not exist locally and auto_download is True, downloads it to MODELS_DIR.
    """
    raw_name = (model_name or "base").lower().strip()
    normalized_name = normalize_model_name(raw_name)
    if normalized_name not in MODEL_URLS:
        normalized_name = "base"

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_filename = f"ggml-{normalized_name}.bin"
    if normalized_name in ("turbo", "large-v3-turbo"):
        model_filename = "ggml-large-v3-turbo.bin"

    model_path = MODELS_DIR / model_filename
    if model_path.exists() and model_path.stat().st_size > 1024 * 1024:
        return model_path

    # Check common system whisper.cpp model locations
    alt_locations = [
        Path.home() / ".cache" / "whisper" / model_filename,
        Path("/opt/homebrew/share/whisper-cpp/models") / model_filename,
        Path("/usr/local/share/whisper.cpp/models") / model_filename,
    ]
    for alt in alt_locations:
        if alt.exists() and alt.stat().st_size > 1024 * 1024:
            return alt

    if not auto_download:
        raise FileNotFoundError(f"Whisper model '{normalized_name}' not found at {model_path}")

    url = MODEL_URLS[normalized_name]
    display_title = MODEL_DISPLAY_NAMES.get(raw_name, MODEL_DISPLAY_NAMES.get(normalized_name, normalized_name))
    print(f"\n[STT] Downloading Whisper '{display_title}' model ({MODEL_SIZES.get(normalized_name, '')})...", file=sys.stderr)
    print(f"      Saving to: {model_path}", file=sys.stderr)

    temp_dest = model_path.with_suffix(".tmp")
    try:
        download_success = False
        if shutil.which("curl"):
            cmd = ["curl", "-L", "-f", "--progress-bar", "-o", str(temp_dest), url]
            res = subprocess.run(cmd)
            if res.returncode == 0 and temp_dest.exists() and temp_dest.stat().st_size > 1024 * 1024:
                download_success = True

        if not download_success:
            import ssl
            try:
                import certifi
                ssl_context = ssl.create_default_context(cafile=certifi.where())
            except Exception:
                try:
                    ssl_context = ssl._create_unverified_context()
                except Exception:
                    ssl_context = None

            req = urllib.request.Request(url, headers={"User-Agent": "Convergent/1.0"})
            with urllib.request.urlopen(req, context=ssl_context) as response, open(temp_dest, "wb") as out_file:
                totalsize = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                blocksize = 1024 * 1024
                while True:
                    chunk = response.read(blocksize)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    out_file.write(chunk)
                    if totalsize > 0:
                        percent = min(100.0, downloaded * 100.0 / totalsize)
                        sys.stderr.write(f"\r[STT] Downloading: {percent:5.1f}% ({downloaded / (1024*1024):.1f} MB / {totalsize / (1024*1024):.1f} MB)")
                        sys.stderr.flush()

        print("\n[STT] Model download complete!\n", file=sys.stderr)
        temp_dest.replace(model_path)
    except Exception as e:
        if temp_dest.exists():
            temp_dest.unlink()
        raise RuntimeError(f"Failed to download Whisper model '{normalized_name}' from {url}: {e}")

    return model_path


def extract_audio_for_stt(source: Path) -> Path:
    """
    Extracts and converts any audio or video container to a 16kHz, 16-bit mono WAV file
    for Whisper speech recognition using FFmpeg.
    Returns temporary Path (caller must remove).
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is required for audio extraction. Install via: brew install ffmpeg")

    temp_wav = Path(tempfile.mktemp(suffix="_convergent_stt_16k.wav"))
    cmd = [
        "ffmpeg",
        "-i", str(source),
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        "-y",
        "-loglevel", "error",
        str(temp_wav)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not temp_wav.exists():
        if temp_wav.exists():
            temp_wav.unlink()
        raise RuntimeError(f"FFmpeg audio extraction failed: {res.stderr.strip() or 'Unknown error'}")

    return temp_wav


def convert_audio_to_text(
    source_path: Path,
    target_ext: str = "TXT",
    model: str = "base",
    language: Optional[str] = None,
    **kwargs
) -> Tuple[bool, str]:
    """
    Transcribes audio or video file to TXT, SRT, VTT, or MD format.

    Args:
        source_path: Path to audio or video file.
        target_ext: Target extension ('TXT', 'SRT', 'VTT', 'MD').
        model: Whisper model size ('standard' / 'base', 'mini' / 'tiny', 'medium' / 'small', 'large' / 'turbo').
        language: Language code (e.g. 'en', 'auto').

    Returns:
        (success: bool, error_message: str)
    """
    source = Path(source_path)
    target_ext = target_ext.upper().lstrip(".")
    output = source.with_suffix(f".{target_ext.lower()}")

    if target_ext not in ("TXT", "SRT", "VTT", "MD"):
        return False, f"Unsupported STT target format: {target_ext}. Choose from TXT, SRT, VTT, MD."

    # 1. Check for whisper-cli or alternative whisper binary
    binary = find_whisper_binary()
    if not binary:
        return False, (
            "No Speech-to-Text engine found. "
            "Please install whisper.cpp via: brew install whisper-cpp"
        )

    # 2. Extract 16kHz mono audio via FFmpeg
    temp_wav = None
    temp_out_prefix = None
    try:
        temp_wav = extract_audio_for_stt(source)
        temp_out_prefix = Path(tempfile.mktemp(prefix="convergent_stt_out_"))

        # 3. Resolve or download model
        try:
            model_path = get_model_path(model_name=model, auto_download=True)
        except Exception as e:
            return False, f"Could not load Whisper model: {e}"

        # 4. Build command for whisper-cli / whisper.cpp
        # Determine output flags based on target_ext
        cmd = [
            binary,
            "-m", str(model_path),
            "-f", str(temp_wav),
            "-of", str(temp_out_prefix),
            "-nt",  # No timestamps in plain text output
        ]

        if target_ext == "TXT":
            cmd.append("-otxt")
        elif target_ext == "SRT":
            cmd.append("-osrt")
        elif target_ext == "VTT":
            cmd.append("-ovtt")
        elif target_ext == "MD":
            cmd.append("-otxt")
            cmd.append("-osrt")

        if language and language.lower() not in ("auto", "none"):
            cmd.extend(["-l", language.lower()])

        # Run transcription
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            err_msg = result.stderr.strip() or result.stdout.strip()
            return False, f"Whisper transcription failed: {err_msg}"

        # 5. Move or format generated output to destination
        generated_txt = Path(f"{temp_out_prefix}.txt")
        generated_srt = Path(f"{temp_out_prefix}.srt")
        generated_vtt = Path(f"{temp_out_prefix}.vtt")

        if target_ext == "TXT":
            if generated_txt.exists():
                shutil.move(str(generated_txt), str(output))
                return True, ""
            return False, "Whisper failed to produce TXT output"

        elif target_ext == "SRT":
            if generated_srt.exists():
                shutil.move(str(generated_srt), str(output))
                return True, ""
            return False, "Whisper failed to produce SRT output"

        elif target_ext == "VTT":
            if generated_vtt.exists():
                shutil.move(str(generated_vtt), str(output))
                return True, ""
            return False, "Whisper failed to produce VTT output"

        elif target_ext == "MD":
            # Compose a formatted Markdown transcript with title & content
            content = ""
            if generated_txt.exists():
                with open(generated_txt, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
            
            srt_content = ""
            if generated_srt.exists():
                with open(generated_srt, "r", encoding="utf-8", errors="ignore") as f:
                    srt_content = f.read().strip()

            md_text = f"# Transcript: {source.name}\n\n"
            md_text += f"> **Source**: `{source.name}`  \n"
            md_text += f"> **Model**: Whisper `{model}`  \n\n"
            md_text += "## Text\n\n"
            md_text += content if content else "_No speech detected._\n"
            
            if srt_content:
                md_text += "\n\n<details>\n<summary><b>Subtitles with Timestamps (SRT)</b></summary>\n\n```srt\n"
                md_text += srt_content
                md_text += "\n```\n</details>\n"

            with open(output, "w", encoding="utf-8") as f:
                f.write(md_text)
            return True, ""

        return False, f"Unknown target format: {target_ext}"

    except Exception as e:
        return False, str(e)
    finally:
        # Cleanup temporary files
        if temp_wav and temp_wav.exists():
            try:
                temp_wav.unlink()
            except Exception:
                pass
        if temp_out_prefix:
            for ext in (".txt", ".srt", ".vtt", ".csv", ".json", ".wts"):
                t_f = Path(f"{temp_out_prefix}{ext}")
                if t_f.exists():
                    try:
                        t_f.unlink()
                    except Exception:
                        pass
