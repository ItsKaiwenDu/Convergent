#!/usr/bin/env python3
"""
Convergent Local MCP (Model Context Protocol) Server

Exposes Convergent file conversion capabilities as an MCP server over stdio.
Enables local AI models (OpenCode, Claude Desktop, Cursor, etc.) to convert,
extract, process, combine, split, resize, compress, decompress, and OCR local files.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError as exc:
    if exc.name == "mcp":
        raise SystemExit("MCP support is optional. Install it with: make setup-mcp") from exc
    raise
from Convergent import Converter, clean_paths
from customs.file_process import FORMAT_REGISTRY
from customs.console import set_stderr_mode

set_stderr_mode(True)

# Initialize FastMCP Server
mcp = FastMCP(
    "Convergent",
    instructions=(
        "Convergent Local MCP Server provides high-performance local file conversion, "
        "media processing (video/audio/image/resizing), document processing (PDF, Markdown, DOCX, Typst), "
        "OCR, Speech-to-Text transcription, compression/decompression, splitting, and merging. "
        "All processing runs 100% locally."
    ),
)

conv = Converter()


def _relocate_output(source: Path, destination: Path, overwrite: bool, original_inputs: Optional[set] = None):
    """
    Safely relocates an output file or directory to its target destination.
    Guards against deleting or moving input source files (e.g. for in-place transforms or collocated targets).
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    is_source_input = original_inputs and (source.resolve() in original_inputs)

    if not overwrite:
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(
                f"Destination already exists: {destination}. "
                "Choose another output path or set overwrite=True."
            )
        if is_source_input:
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
            return

        if source.is_dir():
            shutil.copytree(source, destination)
            shutil.rmtree(source)
        else:
            with source.open("rb") as src, destination.open("xb") as dst:
                shutil.copyfileobj(src, dst)
            shutil.copystat(source, destination)
            source.unlink()
        return

    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    elif destination.is_dir():
        shutil.rmtree(destination)

    if is_source_input:
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    else:
        shutil.move(str(source), str(destination))


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
        target_format: Extension of target format (e.g., 'JPG', 'PNG', 'MP3', 'MP4', 'PDF', 'MD', 'TXT', 'DOCX', 'HTML', 'GIF', 'SRT', 'VTT').
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

    # Determine source format and gather original input set for safety
    path_obj = Path(cleaned_input).resolve()
    if path_obj.is_file():
        source_fmts = [path_obj.suffix.lstrip(".").upper()]
        original_inputs = {path_obj}
        is_dir_input = False
    else:
        source_fmts = sorted(list(conv.formats.keys()))
        original_inputs = {f.resolve() for f in path_obj.iterdir() if f.is_file()}
        is_dir_input = True

    # Pre-resolve output destination directory for direct generation & caching
    conv_output_dir = None
    dest_target = None
    is_dest_dir = False
    if output_path:
        dest_target = Path(os.path.expanduser(output_path)).resolve()
        is_dest_dir = (
            dest_target.is_dir()
            or output_path.endswith(os.sep)
            or output_path.endswith("/")
            or output_path.endswith("\\")
            or not dest_target.suffix
            or is_dir_input
        )
        if is_dest_dir:
            conv_output_dir = dest_target
        else:
            conv_output_dir = dest_target.parent

    success_map: Dict[str, str] = {}
    failed_details: List[Dict[str, Any]] = []

    try:
        converted = conv.process(
            source_formats=source_fmts,
            target_format=target_fmt,
            paths=[str(path_obj)],
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
            output_dir=str(conv_output_dir) if conv_output_dir else None,
            failed_details=failed_details,
        )

        converted_list = [str(p) for p in (converted or list(success_map.keys()))]

        # Honor output_path parameter if specified
        if output_path and converted_list:
            dest_target = Path(os.path.expanduser(output_path)).resolve()
            final_converted_list = []

            moves = []
            for out_item in converted_list:
                out_p = Path(out_item).resolve()
                target_loc = dest_target / out_p.name if is_dest_dir else dest_target
                moves.append((out_p, target_loc))

            for out_p, target_loc in moves:
                if out_p == target_loc:
                    continue
                if (target_loc.exists() or target_loc.is_symlink()) and not overwrite:
                    raise FileExistsError(
                        f"Destination already exists: {target_loc}. "
                        "Choose another output path or set overwrite=True. "
                        "Converted outputs remain at their original locations."
                    )

            for out_p, target_loc in moves:
                if out_p.exists():
                    if out_p != target_loc:
                        _relocate_output(out_p, target_loc, overwrite, original_inputs=original_inputs)
                    final_converted_list.append(str(target_loc))
                elif target_loc.exists():
                    final_converted_list.append(str(target_loc))
            converted_list = final_converted_list

        if converted_list:
            res: Dict[str, Any] = {
                "success": True,
                "count": len(converted_list),
                "converted_files": converted_list,
                "target_format": target_fmt,
            }
            if failed_details:
                res["partial_success"] = True
                res["failed_files"] = failed_details
            return res
        else:
            error_msg = failed_details[0]["error"] if failed_details else f"No matching files found or conversion failed for: {input_path}"
            return {
                "success": False,
                "error": error_msg,
                "count": 0,
                "converted_files": [],
                "failed_files": failed_details,
                "target_format": target_fmt,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "converted_files": [str(p) for p in (converted if 'converted' in locals() and converted else list(success_map.keys()))],
            "failed_files": failed_details,
        }


@mcp.tool()
def pdf_to_images(
    pdf_path: str,
    target_format: str = "JPG",
    output_path: Optional[str] = None,
    dpi: int = 150,
) -> Dict[str, Any]:
    """
    Convert a multi-page PDF into individual image files (one image per page).
    Ideal for feeding visual model context page by page.

    Args:
        pdf_path: Absolute or relative path to PDF file.
        target_format: Output image extension ('JPG', 'PNG'). Default 'JPG'.
        output_path: Optional destination directory or file path.
        dpi: Quality DPI resolution (default 150).

    Returns:
        Dictionary with list of generated page image file paths.
    """
    full_path = os.path.expanduser(pdf_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {pdf_path}", "images": []}

    target_fmt = target_format.upper().lstrip(".")
    if target_fmt not in ("JPG", "PNG"):
        target_fmt = "JPG"

    res = convergent_convert(
        input_path=full_path,
        target_format=target_fmt,
        output_path=output_path,
        overwrite=True,
        dpi=dpi,
    )

    converted_files = res.get("converted_files", [])
    image_files = []
    for item in converted_files:
        p = Path(item)
        if p.is_dir():
            for img in sorted(p.iterdir()):
                if img.is_file() and img.suffix.lower().lstrip(".") in ("jpg", "png", "tif", "bmp"):
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
    output_path: Optional[str] = None,
    bitrate: str = "192k",
) -> Dict[str, Any]:
    """
    Extract audio track from a video file. Useful for pre-processing video for audio transcription.

    Args:
        video_path: Absolute or relative path to video file.
        target_format: Target audio format ('MP3', 'WAV', 'AAC', 'FLAC', 'M4A'). Default 'MP3'.
        output_path: Optional output file or directory path.
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
        output_path=output_path,
        bitrate=bitrate,
        overwrite=True,
    )
    return res


@mcp.tool()
def perform_ocr(
    input_path: str,
    target_format: str = "TXT",
    output_path: Optional[str] = None,
    preview_length: int = 500,
) -> Dict[str, Any]:
    """
    Perform Optical Character Recognition (OCR) on an image or scanned PDF document to extract text.

    Args:
        input_path: Path to image or scanned PDF file.
        target_format: Output text format ('TXT', 'MD', 'DOCX'). Default 'TXT'.
        output_path: Optional output file or directory path.
        preview_length: Maximum characters to return in preview snippet (default 500).

    Returns:
        Dictionary with status, extracted file paths, and extracted text snippet if available.
    """
    full_path = os.path.expanduser(input_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {input_path}"}

    res = convergent_convert(
        input_path=full_path,
        target_format=target_format.upper(),
        output_path=output_path,
        ocr=True,
        overwrite=True,
    )

    extracted_text = None
    converted_files = res.get("converted_files", [])
    if converted_files and os.path.exists(converted_files[0]):
        try:
            with open(converted_files[0], "r", encoding="utf-8", errors="ignore") as f:
                full_text = f.read()
                res["total_characters"] = len(full_text)
                if len(full_text) > preview_length:
                    extracted_text = full_text[:preview_length] + f"\n... [truncated, {len(full_text)} total characters]"
                else:
                    extracted_text = full_text
        except Exception:
            pass

    if extracted_text is not None:
        res["extracted_text_preview"] = extracted_text

    return res


@mcp.tool()
def perform_stt(
    input_path: str,
    target_format: str = "TXT",
    output_path: Optional[str] = None,
    model: str = "base",
    language: Optional[str] = None,
    preview_length: int = 500,
) -> Dict[str, Any]:
    """
    Perform Speech-to-Text (STT) transcription on an audio or video file to extract text or generate subtitles.

    Args:
        input_path: Path to audio (MP3, WAV, M4A, FLAC, AAC, OGG) or video (MP4, MOV, MKV, etc.) file.
        target_format: Output text/subtitle format ('TXT', 'SRT', 'VTT', 'MD'). Default 'TXT'.
        output_path: Optional output file or directory path.
        model: Whisper model size ('standard' / 'base', 'mini' / 'tiny', 'medium' / 'small', 'large' / 'turbo'). Default 'base'.
        language: Language code (e.g. 'en', 'es', 'zh', 'auto'). Default None ('auto').
        preview_length: Maximum characters to return in transcript preview snippet (default 500).

    Returns:
        Dictionary with status, extracted file paths, transcript preview snippet, and model metadata.
    """
    full_path = os.path.expanduser(input_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {input_path}"}

    valid_models = ("tiny", "mini", "base", "standard", "small", "medium", "large", "turbo")
    actual_model = model
    warning = None
    if model.lower() not in valid_models:
        warning = f"Model '{model}' is not a recognized Whisper model name ({', '.join(valid_models)}). Falling back to 'base'."
        actual_model = "base"

    res = convergent_convert(
        input_path=full_path,
        target_format=target_format.upper(),
        output_path=output_path,
        stt=True,
        model=actual_model,
        language=language,
        overwrite=True,
    )
    res["model_used"] = actual_model
    if warning:
        res["warning"] = warning

    extracted_text = None
    converted_files = res.get("converted_files", [])
    if converted_files and os.path.exists(converted_files[0]):
        try:
            with open(converted_files[0], "r", encoding="utf-8", errors="ignore") as f:
                full_text = f.read()
                res["total_characters"] = len(full_text)
                if len(full_text) > preview_length:
                    extracted_text = full_text[:preview_length] + f"\n... [truncated, {len(full_text)} total characters]"
                else:
                    extracted_text = full_text
        except Exception:
            pass

    if extracted_text is not None:
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
        Dictionary with status and path to combined output file.
    """
    if not file_paths:
        return {"success": False, "error": "No valid existing files provided to combine."}

    expanded_paths = []
    missing_paths = []
    for p in file_paths:
        ep = os.path.expanduser(p)
        if os.path.exists(ep):
            expanded_paths.append(ep)
        else:
            missing_paths.append(p)

    if missing_paths:
        return {"success": False, "error": f"The following file(s) do not exist: {', '.join(missing_paths)}"}

    if not expanded_paths:
        return {"success": False, "error": "No valid existing files provided to combine."}

    # Format category definitions for validation
    pdf_exts = {".pdf"}
    video_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
    audio_exts = {".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"}
    gif_exts = {".gif"}
    docx_exts = {".docx"}
    pptx_exts = {".pptx"}
    txt_exts = {".txt"}

    first_ext = Path(expanded_paths[0]).suffix.lower()

    if first_ext in pdf_exts:
        target_group = pdf_exts
        group_name = "PDF"
    elif first_ext in video_exts:
        target_group = video_exts
        group_name = "video"
    elif first_ext in audio_exts:
        target_group = audio_exts
        group_name = "audio"
    elif first_ext in gif_exts:
        target_group = gif_exts
        group_name = "GIF"
    elif first_ext in docx_exts:
        target_group = docx_exts
        group_name = "DOCX"
    elif first_ext in pptx_exts:
        target_group = pptx_exts
        group_name = "PPTX"
    elif first_ext in txt_exts:
        target_group = txt_exts
        group_name = "TXT"
    else:
        return {"success": False, "error": f"Unsupported file type for combination: {first_ext}"}

    # Verify all files belong to the same compatible group
    mismatched = [p for p in expanded_paths if Path(p).suffix.lower() not in target_group]
    if mismatched:
        distinct_exts = sorted(list(set(Path(p).suffix.lower() for p in expanded_paths)))
        return {
            "success": False,
            "error": f"Cannot combine mismatched file types: found {', '.join(distinct_exts)}. All files must be compatible {group_name} files.",
        }

    try:
        out_file = None
        if first_ext in pdf_exts:
            out_file = conv.combine_pdfs(expanded_paths, output_path=output_path, interactive=False)
        elif first_ext in video_exts:
            out_file = conv.combine_videos(expanded_paths, output_path=output_path, interactive=False)
        elif first_ext in audio_exts:
            out_file = conv.combine_audios(expanded_paths, output_path=output_path, interactive=False)
        elif first_ext in gif_exts:
            out_file = conv.combine_gifs(expanded_paths, output_path=output_path, interactive=False)
        elif first_ext in docx_exts:
            out_file = conv.combine_docx(expanded_paths, output_path=output_path, interactive=False)
        elif first_ext in pptx_exts:
            out_file = conv.combine_pptx(expanded_paths, output_path=output_path, interactive=False)
        elif first_ext in txt_exts:
            out_file = conv.combine_txt(expanded_paths, output_path=output_path, interactive=False)

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
    Note: When splitting document formats such as DOCX or PPTX, Convergent converts the document to PDF first and outputs individual PDF pages.

    Args:
        file_path: Path to file to split.
        mode: Split mode. Options:
              - For PDF / DOCX / PPTX: 'pages' (default, 1 page per file), 'ranges' (e.g. ranges='1-5,6-10'), 'parts' (num_parts=N)
              - For Video / Audio: 'interval' (default, e.g. interval=60), 'ranges' (e.g. ranges='0-10,60-120'), 'parts' (num_parts=N)
              - For GIF: 'frames' (default, extracts frame images), 'interval', 'ranges', 'parts'
        interval: Interval in seconds for video/audio/GIF interval split (e.g. 30, 60).
        ranges: Page or time ranges string (e.g. '1-3,4-8' for PDF, '00:00:00-00:01:00,00:02:00-00:03:00' for video).
        num_parts: Total number of parts to split into equally.
        frame_format: Image format for GIF frame extraction ('png', 'jpg'). Default 'png'.
        output_dir: Optional target directory path to save split files.

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
def compress_files(
    file_paths: List[str],
    output_name: str = "archive.zip",
    format: str = "ZIP",
    password: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compress files or directories into an archive (ZIP, TAR.GZ, TAR.BZ2, TAR.XZ, 7Z, RAR).

    Args:
        file_paths: List of file or folder paths to compress.
        output_name: Name of the resulting archive file (e.g. 'archive.zip', 'backup.tar.gz').
        format: Archive format ('ZIP', 'TAR.GZ', 'TAR.BZ2', 'TAR.XZ', '7Z', 'RAR'). Default 'ZIP'.
        password: Optional encryption password for ZIP or 7Z archives.
        output_dir: Optional destination directory for the archive.

    Returns:
        Dictionary with status and output archive path.
    """
    expanded_paths = [os.path.expanduser(p) for p in file_paths if os.path.exists(os.path.expanduser(p))]
    if not expanded_paths:
        return {"success": False, "error": "No valid existing files provided to compress."}

    fmt = format.upper().lstrip(".")
    if fmt == "TGZ":
        fmt = "TAR.GZ"
    elif fmt == "TBZ2":
        fmt = "TAR.BZ2"
    elif fmt == "TXZ":
        fmt = "TAR.XZ"

    try:
        success, message, archive_path = conv.compress(
            paths=expanded_paths,
            output_name=output_name,
            format_choice=fmt,
            password=password,
            output_dir=output_dir,
            interactive=False,
        )
        if success and archive_path:
            return {
                "success": True,
                "archive_path": str(archive_path),
                "format": fmt,
            }
        else:
            return {
                "success": False,
                "error": message or "Compression failed.",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def decompress_archive(
    archive_path: str,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Decompress/extract an archive file (ZIP, TAR.GZ, TGZ, TAR.BZ2, TAR.XZ, 7Z, RAR).

    Args:
        archive_path: Path to archive file to extract.
        output_dir: Optional target directory to extract files into. Defaults to a folder named after the archive stem.

    Returns:
        Dictionary with status, output directory, and extracted file count.
    """
    full_path = os.path.expanduser(archive_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"Archive file not found: {archive_path}"}

    try:
        success, message, out_dir = conv.decompress(
            path=full_path,
            output_dir=output_dir,
            interactive=False,
        )
        if success and out_dir and Path(out_dir).exists():
            out_p = Path(out_dir)
            files = [str(f) for f in sorted(out_p.rglob("*")) if f.is_file()]
            return {
                "success": True,
                "output_dir": str(out_p),
                "extracted_files_count": len(files),
            }
        else:
            return {
                "success": False,
                "error": message or "Decompression failed.",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def resize_media(
    file_path: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    scale_percent: Optional[float] = None,
    aspect_ratio: Optional[str] = None,
    output_path: Optional[str] = None,
    strip_metadata: bool = False,
) -> Dict[str, Any]:
    """
    Resize, rescale, crop to aspect ratio, or strip metadata from images (JPG, PNG, HEIC) or video (MP4).

    Args:
        file_path: Path to image or MP4 video file.
        width: Optional target width in pixels. If height is also provided, resizes to exact (width, height).
        height: Optional target height in pixels. If width is omitted, scales proportionally to height.
        scale_percent: Optional percentage scaling (e.g. 50 for 50%, 200 for 200%).
        aspect_ratio: Optional aspect ratio crop ('16:9', '4:3', '1:1', '9:16').
        output_path: Optional output file or directory path.
        strip_metadata: If True, strips EXIF/IPTC metadata. Default False.

    Returns:
        Dictionary with status, output file path, and duration.
    """
    from modules.resize import resize_single_file
    full_path = Path(os.path.expanduser(file_path)).resolve()
    if not full_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    # Determine method and scale_val
    if width and height:
        method = '3'
        scale_val = (int(width), int(height))
    elif height and not width:
        method = '2'
        scale_val = int(height)
    elif scale_percent is not None:
        method = '1'
        scale_val = float(scale_percent)
    else:
        # Aspect crop only or strip metadata only
        method = '4'
        scale_val = None

    target_aspect = aspect_ratio if aspect_ratio else '5'

    try:
        name, success, error, duration = resize_single_file(
            full_path,
            method=method,
            scale_val=scale_val,
            target_aspect=target_aspect,
            strip_metadata=strip_metadata,
            output_path=output_path,
        )
        if success:
            if output_path:
                out_p = Path(os.path.expanduser(str(output_path))).resolve()
                if out_p.is_dir() or str(output_path).endswith(os.sep) or str(output_path).endswith("/"):
                    final_path = out_p / f"{full_path.stem}_resized{full_path.suffix}"
                else:
                    final_path = out_p
            else:
                final_path = full_path.parent / f"{full_path.stem}_resized{full_path.suffix}"
            return {
                "success": True,
                "output_file": str(final_path),
                "duration_seconds": round(duration, 2),
            }
        else:
            return {
                "success": False,
                "error": error or "Resize operation failed.",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def list_supported_formats(
    category: Optional[str] = None,
    source_format: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List supported source formats and available conversion targets in Convergent.

    Args:
        category: Optional category filter ('image', 'video', 'audio', 'document').
        source_format: Optional source format filter (e.g. 'PNG', 'PDF', 'MP4').

    Returns:
        Dictionary mapping input extension to list of valid target output extensions, with optional filtering.
    """
    semantic_categories = {
        "image": ["JPG", "JPEG", "PNG", "WEBP", "GIF", "HEIC", "BMP", "TIFF", "TIF", "SVG", "ICO", "AVIF"],
        "video": ["MP4", "MOV", "MKV", "AVI", "WEBM", "FLV", "WMV"],
        "audio": ["MP3", "WAV", "AAC", "FLAC", "M4A", "OGG", "WMA"],
        "document": ["PDF", "DOCX", "PPTX", "XLSX", "MD", "TXT", "HTML", "HTM", "TYP", "EPUB", "RTF", "ODT", "ODS", "ODP"],
    }

    formats = dict(conv.formats)
    if source_format:
        sf_upper = source_format.upper().lstrip(".")
        if sf_upper in formats:
            return {
                "source_format": sf_upper,
                "target_formats": formats[sf_upper],
            }
        else:
            return {
                "error": f"Format '{source_format}' is not a recognized source format.",
                "available_formats": sorted(list(formats.keys())),
            }

    if category:
        cat_key = category.lower().strip()
        num_to_semantic = {"1": "document", "2": "image", "3": "video", "4": "audio"}
        cat_key = num_to_semantic.get(cat_key, cat_key)
        cat_formats = semantic_categories.get(cat_key)
        if cat_formats:
            filtered_mapping = {k: v for k, v in formats.items() if k in cat_formats}
            return {
                "category": cat_key,
                "source_formats": sorted(list(filtered_mapping.keys())),
                "format_mapping": filtered_mapping,
            }
        else:
            return {
                "error": f"Category '{category}' not recognized. Available categories: {', '.join(semantic_categories.keys())}",
            }

    merged_categories = dict(conv.categories)
    merged_categories.update(semantic_categories)

    return {
        "source_formats": conv.source_formats,
        "categories": merged_categories,
        "format_mapping": formats,
    }


def run_server():
    """Run FastMCP server over stdio."""
    set_stderr_mode(True)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
