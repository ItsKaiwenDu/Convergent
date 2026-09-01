#!/usr/bin/env python3
"""
Convergent Local MCP (Model Context Protocol) Server
---------------------------------------------------
Exposes Convergent file conversion capabilities as an MCP server over stdio.
Enables local AI models (OpenCode, Claude Desktop, Cursor, etc.) to convert,
extract, process, combine, split, and OCR local files.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mcp.server.fastmcp import FastMCP
from Convergent import Converter, clean_paths
from customs.file_process import FORMAT_REGISTRY
from customs.console import set_stderr_mode

set_stderr_mode(True)

# Initialize FastMCP Server
mcp = FastMCP(
    "Convergent",
    instructions=(
        "Convergent Local MCP Server provides high-performance local file conversion, "
        "media processing (video/audio/image), document processing (PDF, Markdown, DOCX, Typst), "
        "OCR, compression, splitting, and merging. All processing runs 100% locally."
    ),
)

conv = Converter()


@mcp.tool()
def convergent_convert(
    input_path: str,
    target_format: str,
    output_path: Optional[str] = None,
    fps: Optional[int] = None,
    bitrate: Optional[str] = None,
    md_pdf_mode: str = "formatted",
    strip_metadata: bool = False,
    ocr: bool = False,
    stt: bool = False,
    model: str = "base",
    language: Optional[str] = None,
    overwrite: bool = True,
    use_cache: bool = True,
    dpi: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Convert a file or directory of files to a target format using Convergent.

    Args:
        input_path: Absolute or relative path to file or directory to convert.
        target_format: Extension of target format (e.g., 'JPG', 'PNG', 'MP3', 'MP4', 'PDF', 'MD', 'TXT', 'DOCX', 'GIF', 'SRT', 'VTT').
        output_path: Optional output directory or file path. Defaults to input path location.
        fps: Target frames per second for video/GIF outputs (e.g. 30).
        bitrate: Audio bitrate for MP3/Audio outputs (e.g. '192k', '320k').
        md_pdf_mode: Rendering mode for Markdown to PDF ('formatted' or 'raw'). Default 'formatted'.
        strip_metadata: If True, strips EXIF/IPTC metadata from image outputs.
        ocr: If True, applies optical character recognition on image/scanned input.
        stt: If True, performs Speech-to-Text transcription on audio/video input.
        model: Whisper model size for STT ('standard' / 'base', 'mini' / 'tiny', 'medium' / 'small', 'large' / 'turbo'). Default 'base'.
        language: Language code for STT transcription (e.g. 'en', 'es', 'zh', 'auto').
        overwrite: If True, overwrites existing files without asking. Default True.
        use_cache: If True, uses content-addressable cache to skip unchanged files. Default True.
        dpi: Quality DPI resolution for PDF-to-image conversion (e.g. 150, 300).

    Returns:
        Dictionary containing status, list of converted output files, and any warnings.
    """
    cleaned_input = os.path.expanduser(input_path)
    if not os.path.exists(cleaned_input):
        return {
            "success": False,
            "error": f"Input path does not exist: {input_path}",
            "converted_files": [],
        }

    target_fmt = target_format.upper().lstrip(".")
    fps_val = str(fps) if fps is not None else None
    bitrate_val = str(bitrate) if bitrate is not None else None

    # Determine source format if possible
    path_obj = Path(cleaned_input)
    if path_obj.is_file():
        source_fmts = [path_obj.suffix.lstrip(".").upper()]
    else:
        source_fmts = sorted(list(conv.formats.keys()))

    success_map: Dict[str, str] = {}

    try:
        converted = conv.process(
            source_formats=source_fmts,
            target_format=target_fmt,
            paths=[cleaned_input],
            fps=fps_val,
            bitrate=bitrate_val,
            overwrite=overwrite,
            skip=not overwrite,
            md_pdf_mode=md_pdf_mode,
            strip_metadata=strip_metadata,
            interactive=False,
            ocr=ocr,
            stt=stt,
            model=model,
            language=language,
            success_map=success_map,
            use_cache=use_cache,
            dpi=dpi,
        )

        converted_list = [str(p) for p in (converted or list(success_map.keys()))]

        # Honor output_path parameter if specified
        if output_path and converted_list:
            import shutil
            dest_target = Path(os.path.expanduser(output_path)).resolve()
            final_converted_list = []

            is_dest_dir = (
                dest_target.is_dir()
                or output_path.endswith(os.sep)
                or output_path.endswith("/")
                or output_path.endswith("\\")
                or not dest_target.suffix
                or len(converted_list) > 1
            )

            if is_dest_dir:
                dest_target.mkdir(parents=True, exist_ok=True)
                for out_item in converted_list:
                    out_p = Path(out_item)
                    if out_p.exists():
                        target_loc = dest_target / out_p.name
                        if target_loc != out_p:
                            if target_loc.is_dir():
                                shutil.rmtree(target_loc)
                            elif target_loc.is_file():
                                target_loc.unlink()
                            shutil.move(str(out_p), str(target_loc))
                            final_converted_list.append(str(target_loc))
                        else:
                            final_converted_list.append(str(out_p))
            else:
                dest_target.parent.mkdir(parents=True, exist_ok=True)
                out_p = Path(converted_list[0])
                if out_p.exists():
                    if dest_target != out_p:
                        if dest_target.is_dir():
                            shutil.rmtree(dest_target)
                        elif dest_target.is_file():
                            dest_target.unlink()
                        shutil.move(str(out_p), str(dest_target))
                        final_converted_list.append(str(dest_target))
                    else:
                        final_converted_list.append(str(out_p))
                for out_item in converted_list[1:]:
                    final_converted_list.append(out_item)

            converted_list = final_converted_list

        if converted_list:
            return {
                "success": True,
                "count": len(converted_list),
                "converted_files": converted_list,
                "target_format": target_fmt,
            }
        else:
            return {
                "success": False,
                "error": f"No matching files found or conversion failed for: {input_path}",
                "count": 0,
                "converted_files": [],
                "target_format": target_fmt,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "converted_files": [str(p) for p in (converted if 'converted' in locals() and converted else list(success_map.keys()))],
        }


@mcp.tool()
def pdf_to_images(
    pdf_path: str,
    target_format: str = "JPG",
    dpi: int = 150,
) -> Dict[str, Any]:
    """
    Convert a multi-page PDF into individual image files (one image per page).
    Ideal for feeding visual model context page by page.

    Args:
        pdf_path: Absolute or relative path to PDF file.
        target_format: Output image extension ('JPG', 'PNG'). Default 'JPG'.
        dpi: Quality DPI resolution (default 150).

    Returns:
        Dictionary with list of generated page image file paths.
    """
    full_path = os.path.expanduser(pdf_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {pdf_path}", "images": []}

    target_fmt = target_format.upper().lstrip(".")
    if target_fmt not in ("JPG", "JPEG", "PNG"):
        target_fmt = "JPG"

    res = convergent_convert(
        input_path=full_path,
        target_format=target_fmt,
        overwrite=True,
        dpi=dpi,
    )

    converted_files = res.get("converted_files", [])
    image_files = []
    for item in converted_files:
        p = Path(item)
        if p.is_dir():
            for img in sorted(p.iterdir()):
                if img.is_file() and img.suffix.lower().lstrip(".") in ("jpg", "jpeg", "png", "tiff", "tif", "bmp"):
                    image_files.append(str(img))
        elif p.is_file():
            image_files.append(str(p))

    return {
        "success": res.get("success", False),
        "count": len(image_files) if image_files else res.get("count", 0),
        "images": image_files if image_files else converted_files,
        "error": res.get("error"),
    }


@mcp.tool()
def extract_audio(
    video_path: str,
    target_format: str = "MP3",
    bitrate: str = "192k",
) -> Dict[str, Any]:
    """
    Extract audio track from a video file. Useful for pre-processing video for audio transcription.

    Args:
        video_path: Absolute or relative path to video file.
        target_format: Target audio format ('MP3', 'WAV', 'AAC', 'FLAC', 'M4A'). Default 'MP3'.
        bitrate: Audio bitrate (e.g. '128k', '192k', '320k'). Default '192k'.

    Returns:
        Dictionary containing path to extracted audio file.
    """
    full_path = os.path.expanduser(video_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {video_path}"}

    res = convergent_convert(
        input_path=full_path,
        target_format=target_format.upper(),
        bitrate=bitrate,
        overwrite=True,
    )
    return res


@mcp.tool()
def perform_ocr(
    input_path: str,
    target_format: str = "TXT",
) -> Dict[str, Any]:
    """
    Perform Optical Character Recognition (OCR) on an image or scanned PDF document to extract text.

    Args:
        input_path: Path to image or scanned PDF file.
        target_format: Output text format ('TXT', 'MD', 'DOCX'). Default 'TXT'.

    Returns:
        Dictionary with status, extracted file paths, and extracted text snippet if available.
    """
    full_path = os.path.expanduser(input_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {input_path}"}

    res = convergent_convert(
        input_path=full_path,
        target_format=target_format.upper(),
        ocr=True,
        overwrite=True,
    )

    # Read extracted text if single text file generated
    extracted_text = None
    converted_files = res.get("converted_files", [])
    if converted_files and os.path.exists(converted_files[0]):
        try:
            with open(converted_files[0], "r", encoding="utf-8", errors="ignore") as f:
                extracted_text = f.read(4000)  # first 4k chars snippet
        except Exception:
            pass

    if extracted_text:
        res["extracted_text_preview"] = extracted_text

    return res


@mcp.tool()
def perform_stt(
    input_path: str,
    target_format: str = "TXT",
    model: str = "base",
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Perform Speech-to-Text (STT) transcription on an audio or video file to extract text or generate subtitles.

    Args:
        input_path: Path to audio (MP3, WAV, M4A, FLAC, AAC, OGG) or video (MP4, MOV, MKV, etc.) file.
        target_format: Output text/subtitle format ('TXT', 'SRT', 'VTT', 'MD'). Default 'TXT'.
        model: Whisper model size ('standard' / 'base', 'mini' / 'tiny', 'medium' / 'small', 'large' / 'turbo'). Default 'base'.
        language: Language code (e.g. 'en', 'es', 'zh', 'auto'). Default None ('auto').

    Returns:
        Dictionary with status, extracted file paths, and transcript preview snippet if available.
    """
    full_path = os.path.expanduser(input_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {input_path}"}

    res = convergent_convert(
        input_path=full_path,
        target_format=target_format.upper(),
        stt=True,
        model=model,
        language=language,
        overwrite=True,
    )

    extracted_text = None
    converted_files = res.get("converted_files", [])
    if converted_files and os.path.exists(converted_files[0]):
        try:
            with open(converted_files[0], "r", encoding="utf-8", errors="ignore") as f:
                extracted_text = f.read(4000)  # first 4k chars snippet
        except Exception:
            pass

    if extracted_text:
        res["extracted_text_preview"] = extracted_text

    return res


@mcp.tool()
def combine_files(
    file_paths: List[str],
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Combine multiple PDF, video, audio, GIF, or document files into a single merged file non-interactively.

    Args:
        file_paths: List of file paths to combine (must all share compatible file types).
        output_path: Optional destination file or directory path.

    Returns:
        Dictionary with status and path to the combined output file.
    """
    expanded_paths = [os.path.expanduser(p) for p in file_paths if os.path.exists(os.path.expanduser(p))]
    if not expanded_paths:
        return {"success": False, "error": "No valid existing files provided to combine."}

    ext = Path(expanded_paths[0]).suffix.lower()

    try:
        out_file = None
        if ext == ".pdf":
            out_file = conv.combine_pdfs(expanded_paths, output_path=output_path, interactive=False)
        elif ext in (".mp4", ".mov", ".mkv", ".avi", ".webm"):
            out_file = conv.combine_videos(expanded_paths, output_path=output_path, interactive=False)
        elif ext in (".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"):
            out_file = conv.combine_audios(expanded_paths, output_path=output_path, interactive=False)
        elif ext == ".gif":
            out_file = conv.combine_gifs(expanded_paths, output_path=output_path, interactive=False)
        elif ext == ".docx":
            out_file = conv.combine_docx(expanded_paths, output_path=output_path, interactive=False)
        elif ext == ".pptx":
            out_file = conv.combine_pptx(expanded_paths, output_path=output_path, interactive=False)
        elif ext == ".txt":
            out_file = conv.combine_txt(expanded_paths, output_path=output_path, interactive=False)
        else:
            return {"success": False, "error": f"Unsupported file type for combination: {ext}"}

        if out_file:
            return {
                "success": True,
                "output_file": str(out_file),
            }
        else:
            return {
                "success": False,
                "error": "Failed to combine files. Check dependencies (ghostscript, ffmpeg, libreoffice).",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def split_file(
    file_path: str,
    mode: str = "pages",
    interval: Optional[float] = None,
    ranges: Optional[str] = None,
    num_parts: Optional[int] = None,
    frame_format: str = "png",
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Split a PDF, video, audio, GIF, or document into individual pages, segments, frames, or parts non-interactively.

    Args:
        file_path: Path to the file to split.
        mode: Split mode. Options:
              - For PDF / DOCX / PPTX: 'pages' (default, 1 page per file), 'ranges' (e.g. ranges='1-5,6-10'), 'parts' (num_parts=N)
              - For Video / Audio: 'interval' (default, e.g. interval=60), 'ranges' (e.g. ranges='0-10,60-120'), 'parts' (num_parts=N)
              - For GIF: 'frames' (default, extracts frame images), 'interval', 'ranges', 'parts'
        interval: Interval in seconds for video/audio/GIF interval split (e.g. 30, 60).
        ranges: Page or time ranges string (e.g. '1-3,4-8' for PDF, '00:00:00-00:01:00,00:02:00-00:03:00' for video).
        num_parts: Total number of parts to split into equally.
        frame_format: Image format for GIF frame extraction ('png', 'jpg'). Default 'png'.
        output_dir: Optional target directory path to save the split files.

    Returns:
        Dictionary with status, output directory, and list of generated files.
    """
    full_path = os.path.expanduser(file_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    ext = Path(full_path).suffix.lower()
    try:
        out_dir = None
        if ext == ".pdf":
            out_dir = conv.split_pdf(full_path, mode=mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        elif ext in (".mp4", ".mov", ".mkv", ".avi", ".webm"):
            out_dir = conv.split_video(full_path, mode=mode, interval=interval, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        elif ext in (".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"):
            out_dir = conv.split_audio(full_path, mode=mode, interval=interval, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        elif ext == ".gif":
            out_dir = conv.split_gif(full_path, mode=mode, frame_format=frame_format, interval=interval, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        elif ext == ".docx":
            out_dir = conv.split_docx(full_path, mode=mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        elif ext == ".pptx":
            out_dir = conv.split_pptx(full_path, mode=mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        else:
            return {"success": False, "error": f"Unsupported file type for splitting: {ext}"}

        if out_dir and Path(out_dir).exists():
            out_path_obj = Path(out_dir)
            files = [str(f) for f in sorted(out_path_obj.iterdir(), key=lambda p: p.name) if f.is_file()]
            return {
                "success": True,
                "output_dir": str(out_path_obj),
                "split_files": files,
                "count": len(files),
                "message": f"Successfully split {file_path} into {len(files)} files.",
            }
        else:
            return {"success": False, "error": f"Failed to split {file_path}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def list_supported_formats() -> Dict[str, Any]:
    """
    List all source formats and available target conversion formats in Convergent.

    Returns:
        Dictionary mapping input extension to list of valid target output extensions.
    """
    return {
        "source_formats": conv.source_formats,
        "categories": conv.categories,
        "format_mapping": conv.formats,
    }


def run_server():
    """Run the FastMCP server over stdio."""
    set_stderr_mode(True)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
