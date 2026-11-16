#!/usr/bin/env python3
"""
Convergent Local MCP (Model Context Protocol) Server

Exposes Convergent file conversion capabilities as an MCP server over stdio.
Enables local AI models (OpenCode, Claude Desktop, Cursor, etc.) to convert,
extract, process, combine, split, resize, compress, decompress, and OCR local files.
"""

import os
import re
import sys
import math
import time
import json
import shutil
import tempfile
import asyncio
import zipfile
import tarfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Union, Literal

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.fastmcp.utilities.func_metadata import FuncMetadata
    _orig_call_fn = FuncMetadata.call_fn_with_arg_validation

    async def _async_call_fn_with_arg_validation(self, fn, fn_is_async, arguments_to_validate, arguments_to_pass_directly):
        if fn_is_async:
            return await _orig_call_fn(self, fn, fn_is_async, arguments_to_validate, arguments_to_pass_directly)
        arguments_pre_parsed = self.pre_parse_json(arguments_to_validate)
        if isinstance(arguments_pre_parsed, dict) and hasattr(self.arg_model, "model_fields"):
            allowed_fields = set(self.arg_model.model_fields.keys())
            unexpected = set(arguments_pre_parsed.keys()) - allowed_fields
            if unexpected:
                fn_name = getattr(fn, "__name__", str(fn))
                raise ValueError(
                    f"Unexpected argument(s) for tool '{fn_name}': {', '.join(sorted(unexpected))}. "
                    f"Allowed arguments: {', '.join(sorted(allowed_fields))}"
                )
        arguments_parsed_model = self.arg_model.model_validate(arguments_pre_parsed)
        arguments_parsed_dict = arguments_parsed_model.model_dump_one_level()
        arguments_parsed_dict |= arguments_to_pass_directly or {}

        import uuid
        import threading
        from customs.run_command import set_request_context, terminate_active_processes
        request_id = str(uuid.uuid4())
        cancel_event = threading.Event()
        set_request_context(request_id, cancel_event)

        try:
            return await asyncio.to_thread(fn, **arguments_parsed_dict)
        except asyncio.CancelledError:
            cancel_event.set()
            terminate_active_processes(request_id=request_id)
            raise

    FuncMetadata.call_fn_with_arg_validation = _async_call_fn_with_arg_validation
except ModuleNotFoundError as exc:
    if exc.name == "mcp":
        raise SystemExit("MCP support is optional. Install it with: make setup-mcp") from exc
    raise
from Convergent import Converter, clean_paths
from customs.file_process import FORMAT_REGISTRY
from customs.cache import CacheManager
from modules.combine import natural_sort_key
from customs.console import set_stderr_mode

set_stderr_mode(True)

mcp = FastMCP(
    "Convergent",
    instructions=(
        "Convergent Local MCP Server provides high-performance local file conversion, "
        "media processing (video/audio/image/resizing), document processing (PDF, Markdown, DOCX, HTML, RTF), "
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
    is_dest_input = original_inputs and (destination.resolve() in original_inputs)

    if is_dest_input:
        raise ValueError(
            f"Output destination '{destination}' resolves to an original input file. "
            "Overwriting original input files via output alias/symlink is not permitted."
        )

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


def _write_manifest_durable(file_list: List[Any], label: str, preferred_dir: Optional[Path]) -> Optional[str]:
    """
    Writes full list to a JSON manifest file.
    Tries preferred_dir first; falls back to tempdir if preferred_dir is read-only or invalid.
    Returns absolute manifest path string, or None if completely unable to write.
    """
    import uuid
    candidate_dirs = []
    if preferred_dir and preferred_dir.is_dir():
        candidate_dirs.append(preferred_dir)
    temp_dir = Path(tempfile.gettempdir())
    if temp_dir not in candidate_dirs:
        candidate_dirs.append(temp_dir)

    for target_dir in candidate_dirs:
        if preferred_dir and target_dir == preferred_dir and target_dir != temp_dir:
            manifest_file = target_dir / f".convergent_manifest_{label}.json"
        else:
            manifest_file = target_dir / f".convergent_manifest_{label}_{uuid.uuid4().hex[:8]}.json"
        try:
            manifest_file.write_text(json.dumps(file_list, indent=2), encoding="utf-8")
            return str(manifest_file.resolve())
        except Exception:
            continue
    return None


def _cap_list(items: List[Any], label: str, preferred_dir: Optional[Path], limit: int = 25, sample_size: int = 10) -> Tuple[List[Any], bool, Optional[str]]:
    """
    If items exceed limit:
      writes durable manifest (falling back to tempdir).
      If manifest write succeeds: returns (items[:sample_size], True, manifest_path).
      If manifest write fails: returns (items, False, None) without truncating so data is not lost.
    """
    if len(items) <= limit:
        return items, False, None
    manifest_path = _write_manifest_durable(items, label, preferred_dir)
    if manifest_path:
        return items[:sample_size], True, manifest_path
    return items, False, None


def _sanitize_mcp_error(msg: str) -> str:
    """Clean MCP error text: replace CLI-only hints and strip noisy FFmpeg/temp-path lines."""
    if not msg:
        return msg
    cli_hint = "Rerun conversion with --install-deps to download it."
    mcp_hint = "Run 'python Convergent.py --install-deps' in a terminal or choose an already-installed Whisper model."
    if cli_hint in msg:
        msg = msg.replace(cli_hint, mcp_hint)

    lines = [line.rstrip() for line in msg.splitlines() if line.strip()]
    if not lines:
        return msg.strip()

    ffmpeg_ptr_re = re.compile(r'\[[^\]]+@\s*0x[0-9a-fA-F]+\]\s*')
    tmp_path_re = re.compile(r'(?:[^\s"\']*/)?\.tmp_[A-Za-z0-9_-]+(?:/[^\s"\']*)?')

    cleaned_lines = []
    for line in lines:
        is_ffmpeg_bracket = bool(
            re.match(r'^\[(?:out|in|vost|aost|sost|fc|Parsed_|AVFilterGraph)[^\]]*@\s*0x[0-9a-fA-F]+\]', line)
        )
        has_tmp = ".tmp_" in line
        if is_ffmpeg_bracket or (
            has_tmp and ("Error opening output" in line or "Could not write header" in line or "Invalid data found" in line)
        ):
            continue
        cleaned_lines.append(line)

    if not cleaned_lines:
        cleaned_lines = lines

    final_lines = []
    seen = set()
    for line in cleaned_lines:
        line = ffmpeg_ptr_re.sub("", line).strip()
        line = tmp_path_re.sub("<temp>", line).strip()
        if line and line not in seen:
            seen.add(line)
            final_lines.append(line)

    return "\n".join(final_lines) if final_lines else msg.strip()


@mcp.tool(structured_output=False)
def convergent_convert(
    input_path: str,
    target_format: str,
    output_path: Optional[str] = None,
    fps: Optional[int] = None,
    bitrate: Optional[str] = None,
    md_pdf_mode: Literal["formatted", "raw"] = "formatted",
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
    Convert a file or directory of files to a target format.
    If output exceeds 25 items, 'converted_files' is truncated to 10 items with 'truncated': True and 'manifest_path'.

    Args:
        input_path: Path to input file or directory.
        target_format: Target extension (e.g. 'JPG', 'PNG', 'MP3', 'MP4', 'PDF', 'MD', 'TXT', 'DOCX', 'HTML', 'GIF', 'SRT', 'VTT').
        output_path: Output directory or file path. Defaults to input location.
        fps: Target FPS for video/GIF (e.g. 30).
        bitrate: Audio bitrate (e.g. '192k', '320k').
        md_pdf_mode: Markdown-to-PDF mode ('formatted' or 'raw').
        strip_metadata: Strip EXIF/IPTC metadata from images.
        ocr: Apply OCR on image/scanned PDF input.
        stt: Perform Speech-to-Text on audio/video input.
        model: Whisper model ('tiny'/'mini', 'base'/'standard', 'small'/'medium', 'large'/'turbo').
        language: STT language code (e.g. 'en', 'es', 'zh', 'auto').
        overwrite: Overwrite existing destination files.
        use_cache: Use content-addressable cache to skip unchanged files.
        dpi: DPI resolution for PDF-to-image conversion (e.g. 150, 300).
    """
    cleaned_input = os.path.expanduser(input_path)
    if not os.path.exists(cleaned_input):
        return {
            "success": False,
            "error": f"Input path does not exist: {input_path}",
            "converted_files": [],
        }

    target_fmt = target_format.upper().lstrip(".")
    if dpi is not None and dpi <= 0:
        return {
            "success": False,
            "error": f"Invalid dpi: {dpi}. Must be a positive integer.",
            "converted_files": [],
        }

    md_pdf_mode_val = None
    if md_pdf_mode is not None:
        mode_str = str(md_pdf_mode).lower().strip()
        if mode_str not in ("standard", "formatted", "raw", "typst"):
            return {
                "success": False,
                "error": f"Invalid md_pdf_mode: '{md_pdf_mode}'. Allowed modes: standard, formatted, raw, typst.",
                "converted_files": [],
            }
        md_pdf_mode_val = mode_str

    if fps is not None and fps <= 0:
        return {
            "success": False,
            "error": f"Invalid fps: {fps}. Must be a positive integer.",
            "converted_files": [],
        }

    fps_val = str(fps) if fps is not None else None
    bitrate_val = None
    if bitrate is not None:
        from modules.audio import parse_audio_bitrate
        valid_b, b_norm = parse_audio_bitrate(bitrate)
        if not valid_b or not b_norm:
            return {
                "success": False,
                "error": f"Invalid bitrate: '{bitrate}'. Examples of valid bitrates: '128k', '192k', '256k', '320k', '256000'.",
                "converted_files": [],
            }
        bitrate_val = b_norm

    # Determine source format and gather original input set for safety
    raw_input_path = Path(cleaned_input)
    is_input_symlink = raw_input_path.is_symlink()
    path_obj = raw_input_path.resolve()
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
    temp_stage_dir = None
    symlink_output_note = None
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
    elif is_input_symlink and path_obj.is_file() and raw_input_path.parent.resolve() != path_obj.parent.resolve():
        conv_output_dir = raw_input_path.parent.resolve()
        symlink_output_note = (
            f"Input '{raw_input_path.name}' is a symlink; output was written next to the symlink in '{conv_output_dir}'."
        )

    published_output_dir = dest_target if is_dest_dir else (path_obj if is_dir_input and not output_path else None)

    def _resolve_manifest_dest_dir() -> Path:
        if published_output_dir and published_output_dir.is_dir():
            return published_output_dir
        if dest_target and dest_target.parent.is_dir():
            return dest_target.parent
        if path_obj.parent.is_dir():
            return path_obj.parent
        return Path(tempfile.gettempdir())

    manifest_dest_dir = _resolve_manifest_dest_dir()

    params_for_cache = {
        "target": target_fmt,
        "fps": fps_val,
        "bitrate": bitrate_val,
        "md_pdf_mode": md_pdf_mode_val,
        "strip_metadata": strip_metadata,
        "ocr": ocr,
        "stt": stt,
        "model": model,
        "language": language,
        "dpi": dpi,
    }

    if output_path and not is_dest_dir:
        if dest_target and original_inputs and (dest_target.resolve() in original_inputs):
            return {
                "success": False,
                "error": f"Output destination '{dest_target}' resolves to an original input file. Overwriting original input files via output alias/symlink is not permitted.",
                "converted_files": [],
                "count": 0,
                "failed_files": [],
                "target_format": target_fmt,
            }
        if dest_target and (dest_target.exists() or dest_target.is_symlink()) and not overwrite:
            return {
                "success": False,
                "error": f"Destination already exists: {dest_target}. Choose another output path or set overwrite=True.",
                "converted_files": [],
                "count": 0,
                "failed_files": [],
                "target_format": target_fmt,
            }

    # If single file conversion targets a custom file path, check if already validly cached
    if use_cache and not is_dest_dir and path_obj.is_file() and dest_target and dest_target.exists():
        try:
            cache_mgr = CacheManager()
            is_valid, _ = cache_mgr.is_cached_valid(path_obj, dest_target, params_for_cache)
            cache_mgr.close()
            if is_valid:
                return {
                    "success": True,
                    "count": 1,
                    "converted_files": [str(dest_target)],
                    "target_format": target_fmt,
                    "cached": True,
                }
        except Exception:
            pass

    if output_path and not is_dest_dir:
        temp_stage_dir = tempfile.TemporaryDirectory()
        conv_output_dir = Path(temp_stage_dir.name)

    success_map: Dict[str, str] = {}
    failed_details: List[Dict[str, Any]] = []
    cached_out_list: List[str] = []
    skipped_out_list: List[str] = []

    try:
        converted = conv.process(
            source_formats=source_fmts,
            target_format=target_fmt,
            paths=[str(path_obj)],
            fps=fps_val,
            bitrate=bitrate_val,
            overwrite=overwrite,
            skip=not overwrite,
            md_pdf_mode=md_pdf_mode_val,
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
            cached_out_list=cached_out_list,
            skipped_out_list=skipped_out_list,
        )

        converted_list = [str(p) for p in (converted or list(success_map.keys()))]

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
                if original_inputs and (target_loc.resolve() in original_inputs):
                    raise ValueError(
                        f"Output destination '{target_loc}' resolves to an original input file. "
                        "Overwriting original input files via output alias/symlink is not permitted."
                    )
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
                        if use_cache:
                            try:
                                cache_mgr = CacheManager()
                                cache_mgr.update_output_path(out_p, target_loc)
                                if path_obj.is_file():
                                    cache_mgr.save(path_obj, target_loc, params_for_cache)
                                cache_mgr.close()
                            except Exception:
                                pass
                    final_converted_list.append(str(target_loc))
                elif target_loc.exists():
                    final_converted_list.append(str(target_loc))
            converted_list = final_converted_list

        manifest_dest_dir = _resolve_manifest_dest_dir()

        if converted_list:
            is_all_cached = bool(converted_list) and bool(cached_out_list) and all(
                str(Path(out_item).resolve()) in cached_out_list for out_item in converted_list
            )

            res: Dict[str, Any] = {
                "success": True,
                "count": len(converted_list),
                "target_format": target_fmt,
                "cached": is_all_cached,
            }
            if published_output_dir:
                res["output_directory"] = str(published_output_dir)
            if symlink_output_note:
                res["note"] = symlink_output_note
            if (
                not is_dir_input
                and not output_path
                and not strip_metadata
                and path_obj.is_file()
                and len(converted_list) == 1
                and Path(converted_list[0]).resolve() == path_obj.resolve()
            ):
                res["message"] = "Skipped (same format as input)."

            conv_files, conv_truncated, conv_manifest = _cap_list(converted_list, "converted", manifest_dest_dir)
            res["converted_files"] = conv_files
            res["truncated"] = conv_truncated
            if conv_manifest:
                res["manifest_path"] = conv_manifest

            if (target_fmt == "HTML" and (
                path_obj.suffix.upper() == ".PPTX"
                or (is_dir_input and any(p.suffix.upper() == ".PPTX" for p in original_inputs))
            )):
                res["warning"] = (
                    "PPTX to HTML conversion via LibreOffice may have limited visual fidelity for slides, shapes, or vector charts. "
                    "For presentation fidelity, converting PPTX to PDF or images (using pdf_to_images) is recommended."
                )

            if skipped_out_list:
                skipped_strs = [str(f) for f in skipped_out_list]
                sk_files, sk_truncated, sk_manifest = _cap_list(skipped_strs, "skipped", manifest_dest_dir)
                res["skipped_files"] = sk_files
                res["skipped_truncated"] = sk_truncated
                if sk_manifest:
                    res["skipped_manifest_path"] = sk_manifest

            if failed_details:
                sanitized_partial = [
                    {**item, "error": _sanitize_mcp_error(item["error"])} if isinstance(item, dict) and "error" in item else item
                    for item in failed_details
                ]
                res["partial_success"] = True
                fail_items, fail_truncated, fail_manifest = _cap_list(sanitized_partial, "failed", manifest_dest_dir)
                res["failed_files"] = fail_items
                if fail_truncated:
                    res["failed_truncated"] = True
                if fail_manifest:
                    res["failed_manifest_path"] = fail_manifest
            return res
        elif failed_details:
            sanitized_failures = [
                {**item, "error": _sanitize_mcp_error(item["error"])} if isinstance(item, dict) and "error" in item else item
                for item in failed_details
            ]
            raw_err = sanitized_failures[0]["error"] if sanitized_failures else f"Conversion failed for: {input_path}"
            if len(sanitized_failures) == 1 and not skipped_out_list:
                fname = sanitized_failures[0].get("name") or Path(input_path).name
                first_line = raw_err.splitlines()[0].strip() if raw_err else "Conversion failed."
                if len(first_line) > 160:
                    first_line = first_line[:157] + "..."
                error_msg = f"Conversion failed for {fname}: {first_line}"
            else:
                error_msg = raw_err
            fail_items, fail_truncated, fail_manifest = _cap_list(sanitized_failures, "failed", manifest_dest_dir)
            res_fail: Dict[str, Any] = {
                "success": False,
                "error": error_msg,
                "count": 0,
                "converted_files": [],
                "failed_files": fail_items,
                "target_format": target_fmt,
            }
            if fail_truncated:
                res_fail["failed_truncated"] = True
            if fail_manifest:
                res_fail["failed_manifest_path"] = fail_manifest
            if skipped_out_list:
                skipped_strs = [str(f) for f in skipped_out_list]
                sk_files, sk_truncated, sk_manifest = _cap_list(skipped_strs, "skipped", manifest_dest_dir)
                res_fail["skipped_files"] = sk_files
                res_fail["skipped_truncated"] = sk_truncated
                if sk_manifest:
                    res_fail["skipped_manifest_path"] = sk_manifest
            return res_fail
        elif skipped_out_list:
            skipped_strs = [str(f) for f in skipped_out_list]
            sk_files, sk_truncated, sk_manifest = _cap_list(skipped_strs, "skipped", manifest_dest_dir)
            res_skipped: Dict[str, Any] = {
                "success": True,
                "count": 0,
                "converted_files": [],
                "target_format": target_fmt,
                "cached": False,
                "message": f"All {len(skipped_out_list)} file(s) already exist and were skipped.",
                "skipped_files": sk_files,
                "skipped_truncated": sk_truncated,
            }
            if sk_manifest:
                res_skipped["skipped_manifest_path"] = sk_manifest
            return res_skipped
        else:
            error_msg = failed_details[0]["error"] if failed_details else f"No matching files found or conversion failed for: {input_path}"
            fail_items, fail_truncated, fail_manifest = _cap_list(failed_details, "failed", manifest_dest_dir)
            res_empty: Dict[str, Any] = {
                "success": False,
                "error": error_msg,
                "count": 0,
                "converted_files": [],
                "failed_files": fail_items,
                "target_format": target_fmt,
            }
            if fail_truncated:
                res_empty["failed_truncated"] = True
            if fail_manifest:
                res_empty["failed_manifest_path"] = fail_manifest
            return res_empty
    except Exception as e:
        manifest_dest_dir = _resolve_manifest_dest_dir()
        fail_items, fail_truncated, fail_manifest = _cap_list(failed_details, "failed", manifest_dest_dir)
        res_exc: Dict[str, Any] = {
            "success": False,
            "error": str(e),
            "converted_files": [],
            "failed_files": fail_items,
        }
        if fail_truncated:
            res_exc["failed_truncated"] = True
        if fail_manifest:
            res_exc["failed_manifest_path"] = fail_manifest
        return res_exc
    finally:
        if temp_stage_dir:
            try:
                temp_stage_dir.cleanup()
            except Exception:
                pass


@mcp.tool(structured_output=False)
def pdf_to_images(
    pdf_path: str,
    target_format: str = "JPG",
    output_path: Optional[str] = None,
    dpi: int = 150,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """
    Convert a multi-page PDF into individual page images (returns 'images', 'count', 'truncated').
    If > 25 pages, 'images' is truncated to 10 items with 'truncated': True and 'manifest_path'.

    Args:
        pdf_path: Path to a single PDF file.
        target_format: Output image format ('JPG', 'PNG', 'TIF', 'BMP'). Default 'JPG'.
        output_path: Destination directory path (creates '<stem>_images/' inside).
        dpi: DPI resolution (default 150).
        overwrite: Overwrite existing destination directory. Default True.
    """
    full_path = os.path.expanduser(pdf_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {pdf_path}", "images": []}

    path_obj = Path(full_path)
    if path_obj.is_dir():
        return {
            "success": False,
            "error": f"pdf_to_images expects a single PDF file, but received a directory: {pdf_path}. Use convergent_convert for batch directory conversions.",
            "images": [],
            "count": 0,
            "truncated": False,
        }
    if path_obj.suffix.lower() != ".pdf":
        return {
            "success": False,
            "error": f"pdf_to_images expects a .pdf file, but received: {pdf_path}. Use convergent_convert for other document conversions.",
            "images": [],
            "count": 0,
            "truncated": False,
        }

    target_fmt = target_format.upper().lstrip(".")
    if target_fmt not in ("JPG", "JPEG", "PNG", "TIF", "TIFF", "BMP"):
        return {
            "success": False,
            "error": f"Unsupported target image format '{target_format}'. Supported formats: JPG, PNG, TIF, BMP",
            "images": [],
            "count": 0,
            "truncated": False,
        }

    image_like_exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
    if output_path:
        out_p = Path(os.path.expanduser(str(output_path))).resolve()
        if not out_p.is_dir() and out_p.suffix.lower() in image_like_exts:
            return {
                "success": False,
                "count": 0,
                "images": [],
                "error": f"pdf_to_images expects a directory path for output_path (each page is written as page_001.<ext>), but received file-like path: {output_path}",
                "truncated": False,
            }
        target_images_dir = out_p / f"{path_obj.stem}_images"
    else:
        target_images_dir = path_obj.resolve().parent / f"{path_obj.stem}_images"

    if not overwrite and (target_images_dir.exists() or target_images_dir.is_symlink()):
        return {
            "success": False,
            "count": 0,
            "images": [],
            "error": f"Destination already exists: {target_images_dir}. Choose another output path or set overwrite=True.",
            "truncated": False,
        }

    res = convergent_convert(
        input_path=full_path,
        target_format=target_fmt,
        output_path=output_path,
        overwrite=overwrite,
        dpi=dpi,
    )

    if not res.get("success", False):
        return {
            "success": False,
            "count": 0,
            "images": [],
            "error": res.get("error") or "PDF conversion failed.",
            "truncated": False,
        }

    norm_target_exts = {"jpg", "jpeg"} if target_fmt in ("JPG", "JPEG") else {"tif", "tiff"} if target_fmt in ("TIF", "TIFF") else {target_fmt.lower()}
    converted_files = res.get("converted_files", [])
    image_files = []
    for item in converted_files:
        p = Path(item)
        if p.is_dir():
            for img in sorted(p.iterdir(), key=natural_sort_key):
                if img.is_file() and img.suffix.lower().lstrip(".") in norm_target_exts:
                    image_files.append(str(img))
        elif p.is_file() and p.suffix.lower().lstrip(".") in norm_target_exts:
            image_files.append(str(p))

    image_files.sort(key=natural_sort_key)
    total_count = len(image_files)

    if total_count == 0:
        return {
            "success": False,
            "count": 0,
            "images": [],
            "error": "No page images were generated.",
            "truncated": False,
        }

    manifest_dest = (
        Path(output_path).resolve()
        if output_path and Path(output_path).is_dir()
        else path_obj.parent
        if path_obj.parent.is_dir()
        else Path(tempfile.gettempdir())
    )
    returned_images, is_truncated, manifest_path = _cap_list(image_files, "pdf_pages", manifest_dest)

    result: Dict[str, Any] = {
        "success": True,
        "count": total_count,
        "images": returned_images,
        "truncated": is_truncated,
        "error": None,
    }
    if manifest_path:
        result["manifest_path"] = manifest_path

    return result


@mcp.tool(structured_output=False)
def extract_audio(
    video_path: str,
    target_format: str = "MP3",
    output_path: Optional[str] = None,
    bitrate: str = "192k",
    overwrite: bool = True,
) -> Dict[str, Any]:
    """
    Extract audio track from a video file.

    Args:
        video_path: Path to video file.
        target_format: Audio format ('MP3', 'WAV', 'AAC', 'FLAC', 'M4A', 'OGG'). Default 'MP3'.
        output_path: Output file or directory path.
        bitrate: Audio bitrate (e.g. '128k', '192k', '320k'). Default '192k'.
        overwrite: Overwrite existing destination file. Default True.
    """
    full_path = os.path.expanduser(video_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {video_path}"}

    target_upper = target_format.upper().lstrip(".")
    valid_audio_formats = {"MP3", "WAV", "AAC", "FLAC", "M4A", "OGG"}
    if target_upper not in valid_audio_formats:
        return {
            "success": False,
            "error": f"Invalid audio target format '{target_format}'. Supported audio formats are: {', '.join(sorted(valid_audio_formats))}",
        }

    res = convergent_convert(
        input_path=full_path,
        target_format=target_upper,
        output_path=output_path,
        bitrate=bitrate,
        overwrite=overwrite,
    )
    return res


@mcp.tool(structured_output=False)
def perform_ocr(
    input_path: str,
    target_format: str = "TXT",
    output_path: Optional[str] = None,
    preview_length: int = 500,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """
    Perform OCR on an image, scanned PDF, or directory of images/PDFs to extract text.

    Args:
        input_path: Path to image, scanned PDF, or directory.
        target_format: Output format ('TXT', 'MD', 'DOCX', 'PDF'). Default 'TXT'.
        output_path: Output file or directory path.
        preview_length: Max characters in 'extracted_text_preview' (default 500).
        overwrite: Overwrite existing destination file. Default True.
    """
    full_path = os.path.expanduser(input_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {input_path}"}

    audio_video_exts = {
        ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".opus",
        ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".3gp", ".flv"
    }
    input_ext = Path(full_path).suffix.lower()
    if input_ext in audio_video_exts:
        return {
            "success": False,
            "error": f"Invalid input format '{input_ext}' for OCR. perform_ocr does not accept audio or video files. For speech transcription, use 'perform_stt'.",
            "converted_files": [],
        }

    markup_exts = {".md", ".markdown", ".html", ".htm"}
    if input_ext in markup_exts:
        return {
            "success": False,
            "error": f"Invalid input format '{input_ext}' for OCR. perform_ocr is designed for image and scanned PDF inputs. For document format conversions (Markdown, HTML, DOCX), use 'convergent_convert'.",
            "converted_files": [],
        }

    target_upper = target_format.upper().lstrip(".")
    valid_ocr_targets = {"TXT", "MD", "DOCX", "PDF"}
    if target_upper not in valid_ocr_targets:
        return {
            "success": False,
            "error": f"Invalid target format '{target_format}' for OCR. Supported OCR text targets: {', '.join(sorted(valid_ocr_targets))}.",
            "converted_files": [],
        }

    res = convergent_convert(
        input_path=full_path,
        target_format=target_upper,
        output_path=output_path,
        ocr=True,
        overwrite=overwrite,
    )

    target_upper = target_format.upper().lstrip(".")
    extracted_text = None
    converted_files = res.get("converted_files", [])
    safe_preview_len = max(0, int(preview_length)) if preview_length is not None else 500

    if target_upper in ("TXT", "MD") and converted_files:
        if len(converted_files) == 1:
            if os.path.exists(converted_files[0]):
                try:
                    with open(converted_files[0], "r", encoding="utf-8", errors="ignore") as f:
                        full_text = f.read()
                        res["total_characters"] = len(full_text)
                        if len(full_text) > safe_preview_len:
                            extracted_text = full_text[:safe_preview_len] + f"\n... [truncated, {len(full_text)} total characters]"
                        else:
                            extracted_text = full_text
                except Exception:
                    pass
        else:
            total_chars = 0
            snippets = []
            readable_count = 0
            for cf in converted_files:
                if not os.path.exists(cf):
                    continue
                try:
                    with open(cf, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                    readable_count += 1
                    total_chars += len(text)
                    snippets.append(f"=== {Path(cf).name} ===\n{text}")
                except Exception:
                    pass
            if readable_count > 0:
                res["total_characters"] = total_chars
                combined = "\n\n".join(snippets)
                if len(combined) > safe_preview_len:
                    extracted_text = (
                        combined[:safe_preview_len]
                        + f"\n... [truncated, {total_chars} total characters across {readable_count} files]"
                    )
                else:
                    extracted_text = combined
    elif target_upper == "DOCX" and res.get("success", False):
        res["total_characters"] = None
        extracted_text = "[Text extracted and saved to DOCX document]"

    if extracted_text is not None and res.get("success", False):
        res["extracted_text_preview"] = extracted_text

    return res


@mcp.tool(structured_output=False)
def perform_stt(
    input_path: str,
    target_format: str = "TXT",
    output_path: Optional[str] = None,
    model: str = "base",
    language: Optional[str] = None,
    preview_length: int = 500,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """
    Transcribe speech from an audio or video file into text or subtitles.

    Args:
        input_path: Path to audio (MP3, WAV, M4A, FLAC, AAC, OGG) or video (MP4, MOV, MKV, AVI, WEBM) file.
        target_format: Output format ('TXT', 'SRT', 'VTT', 'MD'). Default 'TXT'.
        output_path: Output file or directory path.
        model: Whisper model ('tiny'/'mini', 'base'/'standard', 'small'/'medium', 'large'/'turbo'). Default 'base'.
        language: Language code (e.g. 'en', 'es', 'zh', 'auto').
        preview_length: Max characters in 'extracted_text_preview' (default 500).
        overwrite: Overwrite existing destination file. Default True.
    """
    full_path = os.path.expanduser(input_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {input_path}"}

    valid_stt_inputs = {
        ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg",
        ".mp4", ".mov", ".mkv", ".avi", ".webm"
    }
    input_ext = Path(full_path).suffix.lower()
    if input_ext not in valid_stt_inputs:
        image_pdf_exts = {".png", ".jpg", ".jpeg", ".pdf", ".tif", ".tiff", ".bmp", ".webp"}
        hint = " For text extraction from images or scanned PDFs, use 'perform_ocr'." if input_ext in image_pdf_exts else ""
        return {
            "success": False,
            "error": f"Invalid input format '{input_ext}' for Speech-to-Text. perform_stt only accepts audio and video files.{hint}",
            "converted_files": [],
        }

    target_upper = target_format.upper().lstrip(".")
    valid_stt_targets = {"TXT", "SRT", "VTT", "MD"}
    if target_upper not in valid_stt_targets:
        return {
            "success": False,
            "error": f"Invalid target format '{target_format}' for STT. Supported transcript/subtitle targets: {', '.join(sorted(valid_stt_targets))}.",
            "converted_files": [],
        }

    model_cleaned = (model or "base").strip().lower()
    valid_models = (
        "tiny", "mini", "base", "standard", "small", "medium",
        "large", "turbo", "large-turbo", "large-v3-turbo", "large-v3"
    )
    actual_model = model_cleaned
    warning = None
    if model_cleaned not in valid_models:
        warning = f"Model '{model}' is not a recognized Whisper model name ({', '.join(valid_models)}). Falling back to 'base'."
        actual_model = "base"

    from modules.stt import normalize_model_name
    resolved_model = normalize_model_name(actual_model)

    res = convergent_convert(
        input_path=full_path,
        target_format=target_upper,
        output_path=output_path,
        stt=True,
        model=resolved_model,
        language=language,
        overwrite=overwrite,
    )
    if res.get("success", False):
        res["model_used"] = resolved_model
        if resolved_model.lower() != model.lower():
            res["model_requested"] = model
    else:
        res["model_used"] = None
        res["model_requested"] = model
        res["model_resolved"] = resolved_model
        if isinstance(res.get("error"), str):
            res["error"] = _sanitize_mcp_error(res["error"])
    if warning:
        res["warning"] = warning

    extracted_text = None
    converted_files = res.get("converted_files", [])
    safe_preview_len = max(0, int(preview_length)) if preview_length is not None else 500
    if converted_files and os.path.exists(converted_files[0]):
        try:
            with open(converted_files[0], "r", encoding="utf-8", errors="ignore") as f:
                full_text = f.read()
                res["total_characters"] = len(full_text)
                if len(full_text) > safe_preview_len:
                    extracted_text = full_text[:safe_preview_len] + f"\n... [truncated, {len(full_text)} total characters]"
                else:
                    extracted_text = full_text
        except Exception:
            pass

    if extracted_text is not None:
        res["extracted_text_preview"] = extracted_text

    return res


@mcp.tool(structured_output=False)
def combine_files(
    file_paths: List[str],
    output_path: Optional[str] = None,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """
    Combine multiple PDF, video, audio, GIF, TXT, DOCX, or PPTX files into one file.
    DOCX/PPTX inputs are converted to PDF and merged into a '.pdf' output; mixed videos normalize to 1080p 30fps.

    Args:
        file_paths: List of compatible file paths to combine.
        output_path: Destination file or directory path.
        overwrite: Overwrite existing destination file. Default True.
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
        if len(missing_paths) > 5:
            missing_preview = ", ".join(missing_paths[:5]) + f", ... and {len(missing_paths) - 5} more ({len(missing_paths)} missing total)"
        else:
            missing_preview = ", ".join(missing_paths)
        return {"success": False, "error": f"The following file(s) do not exist: {missing_preview}"}

    if not expanded_paths:
        return {"success": False, "error": "No valid existing files provided to combine."}

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

    mismatched = [p for p in expanded_paths if Path(p).suffix.lower() not in target_group]
    if mismatched:
        distinct_exts = sorted(list(set(Path(p).suffix.lower() for p in expanded_paths)))
        return {
            "success": False,
            "error": f"Cannot combine mismatched file types: found {', '.join(distinct_exts)}. All files must be compatible {group_name} files.",
        }

    if output_path:
        out_p_resolved = Path(os.path.expanduser(str(output_path))).resolve()
        if any(Path(p).resolve() == out_p_resolved for p in expanded_paths):
            return {
                "success": False,
                "error": "Output destination cannot be one of input files to combine.",
            }
        if out_p_resolved.is_dir() or str(output_path).endswith(os.sep) or str(output_path).endswith("/"):
            default_name = (
                "combined.pdf" if first_ext in pdf_exts or first_ext in docx_exts or first_ext in pptx_exts
                else "combined.gif" if first_ext in gif_exts
                else "combined.txt" if first_ext in txt_exts
                else f"combined{first_ext}"
            )
            target_check = out_p_resolved / default_name
        else:
            if (first_ext in pdf_exts or first_ext in docx_exts or first_ext in pptx_exts) and out_p_resolved.suffix.lower() != ".pdf":
                got_ext = out_p_resolved.suffix.lower() or "<no extension>"
                return {
                    "success": False,
                    "error": (
                        f"Combining {group_name} files outputs a PDF document, so output_path must end with '.pdf' "
                        f"(got '{got_ext}' in '{output_path}'). Provide a '.pdf' filename or a directory path."
                    ),
                }
            target_check = out_p_resolved

        if (target_check.exists() or target_check.is_symlink()) and not overwrite:
            return {
                "success": False,
                "error": f"Destination already exists: {target_check}. Choose another output path or set overwrite=True.",
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
            from modules.combine import LAST_COMBINE_ERROR
            error_detail = LAST_COMBINE_ERROR.strip() if LAST_COMBINE_ERROR else "Check file compatibility and dependencies (ghostscript, ffmpeg, libreoffice)."
            return {
                "success": False,
                "error": _sanitize_mcp_error(f"Failed to combine files: {error_detail}"),
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(structured_output=False)
def split_file(
    file_path: str,
    mode: Literal["auto", "pages", "interval", "ranges", "parts", "frames"] = "auto",
    interval: Optional[float] = None,
    ranges: Optional[str] = None,
    num_parts: Optional[int] = None,
    frame_format: str = "png",
    output_dir: Optional[str] = None,
    accurate: bool = False,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """
    Split a PDF, video, audio, GIF, DOCX, or PPTX into pages, segments, frames, or parts.
    DOCX/PPTX inputs convert to PDF first and output PDF pages. If > 25 items, 'split_files' is truncated to 10 with 'truncated': True and 'manifest_path'.

    Args:
        file_path: Path to file to split.
        mode: Split mode ('auto', 'pages', 'interval', 'ranges', 'parts', 'frames'). 'auto' selects 'pages' for docs, 'interval' for media, 'frames' for GIF.
        interval: Interval in seconds for media/GIF interval split.
        ranges: Page or time ranges (e.g. '1-3,4-8' or '00:00:00-00:01:00').
        num_parts: Number of equal parts to split into.
        frame_format: Image format for GIF frames ('png', 'jpg'). Default 'png'.
        output_dir: Target directory for split files.
        accurate: Re-encode for frame-accurate video splitting instead of fast keyframe copy. Default False.
        overwrite: Remove stale split files in the output directory. Default True.
    """
    full_path = os.path.expanduser(file_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    ext = Path(full_path).suffix.lower()

    if mode and mode.lower() not in ('auto', 'pages', 'interval', 'ranges', 'parts', 'frames'):
        return {"success": False, "error": f"Invalid mode: '{mode}'. Allowed modes: 'auto', 'pages', 'interval', 'ranges', 'parts', 'frames'"}

    if num_parts is not None:
        try:
            num_parts_val = int(num_parts)
            if num_parts_val <= 0:
                return {"success": False, "error": f"Invalid num_parts: {num_parts}. Must be an integer greater than 0."}
        except (ValueError, TypeError):
            return {"success": False, "error": f"Invalid num_parts: {num_parts}. Must be an integer."}

    if interval is not None:
        try:
            interval_val = float(interval)
            if interval_val <= 0:
                return {"success": False, "error": f"Invalid interval: {interval}. Must be greater than 0."}
        except (ValueError, TypeError):
            return {"success": False, "error": f"Invalid interval: {interval}."}

    from modules.split import reset_split_diagnostics, get_split_failed_parts, get_split_generated_files
    reset_split_diagnostics()

    warnings = []
    if ranges is not None and ext == ".pdf":
        from modules.split import get_pdf_page_count
        total_pages = get_pdf_page_count(full_path)
        parts = [p.strip() for p in ranges.split(',')] if isinstance(ranges, str) else list(ranges)
        valid_ranges = []
        for p in parts:
            valid_entry = False
            try:
                if isinstance(p, (list, tuple)) and len(p) == 2:
                    s, e = int(p[0]), int(p[1])
                elif isinstance(p, str) and '-' in p:
                    s_str, e_str = p.split('-', 1)
                    s, e = int(s_str.strip()), int(e_str.strip())
                elif isinstance(p, (int, str)) and str(p).isdigit():
                    s = e = int(p)
                else:
                    s, e = None, None
                if s is not None and e is not None and 1 <= s <= total_pages and 1 <= e <= total_pages and s <= e:
                    valid_entry = True
                    valid_ranges.append((s, e))
            except Exception:
                valid_entry = False
            if not valid_entry:
                warnings.append(f"Invalid or out-of-bounds range dropped: {p}")
        if not valid_ranges and parts:
            return {"success": False, "error": f"No valid ranges provided. Rejected ranges: {', '.join(str(p) for p in parts)}"}
    elif ranges is not None and ext in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"):
        from modules.split import get_media_duration, parse_time_ranges
        duration = get_media_duration(full_path)
        if duration > 0:
            parsed = parse_time_ranges(ranges, duration)
            raw_parts = [p.strip() for p in ranges.split(',')] if isinstance(ranges, str) else list(ranges)
            if not parsed and raw_parts:
                return {"success": False, "error": f"No valid time ranges provided for media duration ({duration:.1f}s). Rejected ranges: {', '.join(str(p) for p in raw_parts)}"}
            elif len(parsed) < len(raw_parts):
                warnings.append(f"Some requested time ranges were out-of-bounds (media duration: {duration:.1f}s) and were dropped.")

    effective_mode = mode.lower() if mode else "auto"
    if effective_mode == "auto":
        if ext in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"):
            if num_parts is not None:
                effective_mode = "parts"
            elif ranges is not None:
                effective_mode = "ranges"
            else:
                effective_mode = "interval"
        elif ext == ".gif":
            if num_parts is not None:
                effective_mode = "parts"
            elif ranges is not None:
                effective_mode = "ranges"
            elif interval is not None:
                effective_mode = "interval"
            else:
                effective_mode = "frames"
        else:
            if num_parts is not None:
                effective_mode = "parts"
            elif ranges is not None:
                effective_mode = "ranges"
            else:
                effective_mode = "pages"
    elif effective_mode == "pages" and ext in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"):
        # Gracefully handle default or accidental 'pages' mode for media files
        if num_parts is not None:
            effective_mode = "parts"
        elif ranges is not None:
            effective_mode = "ranges"
        else:
            effective_mode = "interval"
    elif effective_mode == "frames" and ext in (".pdf", ".docx", ".pptx"):
        effective_mode = "pages"

    try:
        split_start = time.time()
        target_dir = Path(os.path.expanduser(output_dir)).resolve() if output_dir else None
        pre_existing = {}
        if target_dir and target_dir.exists():
            pre_existing = {f.resolve(): f.stat().st_mtime_ns for f in target_dir.iterdir() if f.is_file()}
        else:
            default_dir = Path(full_path).parent / f"{Path(full_path).stem}_split"
            if default_dir.exists():
                pre_existing = {f.resolve(): f.stat().st_mtime_ns for f in default_dir.iterdir() if f.is_file()}

        out_dir = None
        if ext == ".pdf":
            out_dir = conv.split_pdf(full_path, mode=effective_mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        elif ext in (".mp4", ".mov", ".mkv", ".avi", ".webm"):
            out_dir = conv.split_video(full_path, mode=effective_mode, interval=interval, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False, accurate=accurate)
        elif ext in (".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"):
            out_dir = conv.split_audio(full_path, mode=effective_mode, interval=interval, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        elif ext == ".gif":
            out_dir = conv.split_gif(full_path, mode=effective_mode, frame_format=frame_format, interval=interval, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        elif ext == ".docx":
            out_dir = conv.split_docx(full_path, mode=effective_mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        elif ext == ".pptx":
            out_dir = conv.split_pptx(full_path, mode=effective_mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=False)
        else:
            return {"success": False, "error": f"Unsupported file type for splitting: {ext}"}

        if out_dir and Path(out_dir).exists():
            out_path_obj = Path(out_dir)
            recorded_files = [
                Path(p) for p in get_split_generated_files()
                if Path(p).exists() and Path(p).is_file()
            ]
            if recorded_files:
                current_resolved = {p.resolve() for p in recorded_files}
                files = [str(p) for p in sorted(recorded_files, key=natural_sort_key)]
            else:
                all_files = [f for f in sorted(out_path_obj.iterdir(), key=natural_sort_key) if f.is_file()]
                new_files = [str(f) for f in all_files if f.resolve() not in pre_existing or f.stat().st_mtime_ns > pre_existing[f.resolve()]]
                files = new_files if new_files else [str(f) for f in all_files]
                current_resolved = {Path(p).resolve() for p in files} if new_files else set()

            if overwrite and current_resolved:
                for existing_f in out_path_obj.iterdir():
                    if not existing_f.is_file():
                        continue
                    is_split_pattern = (
                        existing_f.name.startswith("part_")
                        or (existing_f.name.startswith("page_") and existing_f.suffix.lower() == ".pdf")
                        or existing_f.name.startswith("frame_")
                    )
                    if is_split_pattern and existing_f.resolve() not in current_resolved:
                        try:
                            existing_f.unlink()
                        except OSError:
                            pass
            total_count = len(files)
            if total_count == 0:
                return {"success": False, "error": f"No split files were generated from {file_path}."}

            capped_files, is_truncated, manifest_path = _cap_list(files, "split", out_path_obj)
            res_dict = {
                "success": True,
                "output_dir": str(out_path_obj),
                "split_files": capped_files,
                "count": total_count,
                "truncated": is_truncated,
                "message": f"Successfully split {file_path} into {total_count} files." + (f" (showing first {len(capped_files)})" if is_truncated else ""),
            }
            if manifest_path:
                res_dict["manifest_path"] = manifest_path
            failed_parts = get_split_failed_parts()
            if failed_parts:
                res_dict["partial_success"] = True
                res_dict["failed_parts"] = failed_parts
                if warnings is None:
                    warnings = []
                warnings.append(f"{len(failed_parts)} segment(s) failed during splitting.")
            if warnings:
                res_dict["warnings"] = warnings
            reset_split_diagnostics()
            return res_dict
        else:
            failed_parts = get_split_failed_parts()
            err_msg = f"Failed to split {file_path}."
            if failed_parts:
                err_details = "; ".join(f"part {p.get('part', '?')}: {p.get('error', 'unknown error')}" for p in failed_parts[:3])
                err_msg += f" {len(failed_parts)} segment(s) failed: {err_details}."
            reset_split_diagnostics()
            res_fail = {"success": False, "error": err_msg}
            if failed_parts:
                res_fail["failed_parts"] = failed_parts
            return res_fail
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(structured_output=False)
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
        output_name: Resulting archive filename (e.g. 'archive.zip', 'backup.tar.gz').
        format: Archive format ('ZIP', 'TAR.GZ', 'TAR.BZ2', 'TAR.XZ', '7Z', 'RAR'). Default 'ZIP'.
        password: Optional encryption password for ZIP, 7Z, or RAR archives.
        output_dir: Destination directory for archive.
    """
    if not file_paths:
        return {"success": False, "error": "No valid existing files provided to compress."}

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


@mcp.tool(structured_output=False)
def decompress_archive(
    archive_path: str,
    output_dir: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract an archive file (ZIP, TAR.GZ, TGZ, TAR.BZ2, TAR.XZ, 7Z, RAR).

    Args:
        archive_path: Path to archive file to extract.
        output_dir: Target directory for extracted files. Defaults to archive stem folder.
        password: Optional password for encrypted ZIP, 7Z, or RAR archives.
    """
    full_path = os.path.expanduser(archive_path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"Archive file not found: {archive_path}"}

    archive_member_count = None
    try:
        if zipfile.is_zipfile(full_path):
            with zipfile.ZipFile(full_path, 'r') as zf:
                archive_member_count = len([
                    m for m in zf.namelist()
                    if not m.endswith('/') and not m.startswith('__MACOSX/') and not Path(m).name.startswith('._')
                ])
        elif tarfile.is_tarfile(full_path):
            with tarfile.open(full_path, 'r') as tf:
                archive_member_count = len([
                    m for m in tf.getmembers()
                    if m.isfile() and not m.name.startswith("._") and "/._" not in m.name
                ])
    except Exception:
        archive_member_count = None

    from modules.decompress import archive_stem

    start_decompress = time.time()
    dest_path_obj = Path(os.path.expanduser(output_dir)).resolve() if output_dir else Path(full_path).parent / archive_stem(Path(full_path))
    pre_existing_extracted = {}
    if dest_path_obj.exists():
        pre_existing_extracted = {f.resolve(): f.stat().st_mtime for f in dest_path_obj.rglob("*") if f.is_file()}

    try:
        success, message, out_dir = conv.decompress(
            path=full_path,
            output_dir=output_dir,
            interactive=False,
            password=password,
        )
        if success and out_dir and Path(out_dir).exists():
            out_p = Path(out_dir)
            all_files = [f for f in sorted(out_p.rglob("*")) if f.is_file() and not f.name.startswith("._")]
            new_extracted = [f for f in all_files if f.resolve() not in pre_existing_extracted or f.stat().st_mtime > pre_existing_extracted[f.resolve()]]
            if new_extracted:
                count = len(new_extracted)
            elif archive_member_count is not None:
                count = archive_member_count
            else:
                count = len(all_files)
            return {
                "success": True,
                "output_dir": str(out_p),
                "extracted_files_count": count,
            }
        else:
            return {
                "success": False,
                "error": message or "Decompression failed.",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(structured_output=False)
def resize_media(
    file_path: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    scale_percent: Optional[float] = None,
    aspect_ratio: Optional[Literal["16:9", "4:3", "1:1", "9:16"]] = None,
    fps: Optional[Union[int, float]] = None,
    output_path: Optional[str] = None,
    strip_metadata: bool = False,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """
    Resize, rescale, crop to aspect ratio, or strip metadata from images (JPG, PNG, HEIC, WEBP, etc.), video (MP4, MOV, AVI, MKV, WEBM), or PDF.

    Args:
        file_path: Path to image, video (MP4, MOV, AVI, MKV, WEBM), or PDF file.
        width: Target width in pixels (exact if height is also set, else proportional).
        height: Target height in pixels (proportional if width is omitted).
        scale_percent: Percentage scale (e.g. 50 for 50%, 200 for 200%).
        aspect_ratio: Aspect ratio crop ('16:9', '4:3', '1:1', '9:16').
        fps: Target FPS for video files.
        output_path: Output file or directory path.
        strip_metadata: Strip EXIF/IPTC metadata. Default False.
        overwrite: Overwrite existing destination file. Default True.
    """
    from modules.resize import SUPPORTED_RESIZE_EXTS, VIDEO_EXTS, resize_single_file
    full_path = Path(os.path.expanduser(file_path)).resolve()
    if not full_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    ext = full_path.suffix.lower()
    if ext not in SUPPORTED_RESIZE_EXTS:
        return {
            "success": False,
            "error": f"Unsupported file format for resize: '{full_path.suffix or full_path.name}'. Supported formats: images, videos ({', '.join(sorted(VIDEO_EXTS))}), and PDF (.pdf).",
        }

    if (
        width is None
        and height is None
        and scale_percent is None
        and aspect_ratio is None
        and fps is None
        and not strip_metadata
    ):
        return {
            "success": False,
            "error": "No operation specified. Provide at least one of: width, height, scale_percent, aspect_ratio, fps, or strip_metadata=True.",
        }

    if width is not None:
        try:
            width_val = int(width)
            if width_val <= 0:
                return {"success": False, "error": f"Invalid width: {width}. Width must be greater than 0."}
        except (ValueError, TypeError):
            return {"success": False, "error": f"Invalid width: {width}."}
    if height is not None:
        try:
            height_val = int(height)
            if height_val <= 0:
                return {"success": False, "error": f"Invalid height: {height}. Height must be greater than 0."}
        except (ValueError, TypeError):
            return {"success": False, "error": f"Invalid height: {height}."}
    if scale_percent is not None:
        try:
            scale_val_num = float(scale_percent)
            if scale_val_num <= 0:
                return {"success": False, "error": f"Invalid scale_percent: {scale_percent}. Must be greater than 0."}
        except (ValueError, TypeError):
            return {"success": False, "error": f"Invalid scale_percent: {scale_percent}."}
    if aspect_ratio is not None and aspect_ratio not in ("16:9", "4:3", "1:1", "9:16"):
        return {"success": False, "error": f"Unsupported aspect ratio: {aspect_ratio}. Allowed: '16:9', '4:3', '1:1', '9:16'"}
    if fps is not None:
        if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
            return {"success": False, "error": f"Invalid fps: {fps}. FPS must be a finite number greater than 0."}
        if ext not in VIDEO_EXTS:
            return {
                "success": False,
                "error": f"fps is only supported for video files ({', '.join(sorted(VIDEO_EXTS))}), not '{full_path.suffix or full_path.name}'.",
            }

    if output_path:
        out_p = Path(os.path.expanduser(str(output_path))).resolve()
        if out_p.is_dir() or str(output_path).endswith(os.sep) or str(output_path).endswith("/"):
            expected_dest = out_p / f"{full_path.stem}_resized{full_path.suffix}"
        else:
            expected_dest = out_p
    else:
        expected_dest = full_path.parent / f"{full_path.stem}_resized{full_path.suffix}"

    if (expected_dest.exists() or expected_dest.is_symlink()) and not overwrite:
        return {
            "success": False,
            "error": f"Destination already exists: {expected_dest}. Choose another output path or set overwrite=True.",
        }

    if width is not None and height is not None:
        method = '3'
        scale_val = (int(width), int(height))
    elif height is not None and width is None:
        method = '2'
        scale_val = int(height)
    elif width is not None and height is None:
        method = 'w'
        scale_val = int(width)
    elif scale_percent is not None:
        method = '1'
        scale_val = float(scale_percent)
    else:
        method = '4'
        scale_val = None

    target_aspect = aspect_ratio if aspect_ratio else '5'

    try:
        name, success, error, duration = resize_single_file(
            full_path,
            method=method,
            scale_val=scale_val,
            target_aspect=target_aspect,
            fps=fps,
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
                "error": _sanitize_mcp_error(error) if error else "Resize operation failed.",
            }
    except Exception as e:
        return {"success": False, "error": _sanitize_mcp_error(str(e))}


@mcp.tool(structured_output=False)
def list_supported_formats(
    category: Optional[str] = None,
    source_format: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List supported source formats and valid conversion targets.

    Args:
        category: Optional category filter ('image', 'video', 'audio', 'document').
        source_format: Optional source format filter (e.g. 'PNG', 'PDF', 'MP4').
    """
    from customs.file_process import normalize_format_alias

    cat_name_map = {"2": "image", "3": "video", "4": "audio", "5": "document"}
    semantic_categories = {
        "image": sorted(list(set(fd.name for fd in FORMAT_REGISTRY if fd.category_id == "2"))),
        "video": sorted(list(set(fd.name for fd in FORMAT_REGISTRY if fd.category_id == "3"))),
        "audio": sorted(list(set(fd.name for fd in FORMAT_REGISTRY if fd.category_id == "4"))),
        "document": sorted(list(set(fd.name for fd in FORMAT_REGISTRY if fd.category_id == "5"))),
    }

    formats = dict(conv.formats)
    cat_key = None
    cat_formats = None
    if category:
        cat_key = category.lower().strip()
        cat_key = cat_name_map.get(cat_key, cat_key)
        cat_formats = semantic_categories.get(cat_key)
        if not cat_formats:
            return {
                "success": False,
                "error": f"Category '{category}' not recognized. Available categories: {', '.join(semantic_categories.keys())}",
            }

    if source_format:
        sf_upper = normalize_format_alias(source_format.upper().lstrip("."))
        if sf_upper not in formats:
            return {
                "success": False,
                "error": f"Format '{source_format}' is not a recognized source format.",
                "available_formats": sorted(list(formats.keys())),
            }
        if cat_formats is not None and sf_upper not in cat_formats:
            return {
                "success": False,
                "error": f"Source format '{sf_upper}' does not belong to category '{cat_key}'.",
                "category": cat_key,
                "category_formats": cat_formats,
            }
        result: Dict[str, Any] = {
            "source_format": sf_upper,
            "target_formats": formats[sf_upper],
        }
        if cat_key is not None:
            result["category"] = cat_key
        return result

    if cat_formats is not None:
        filtered_mapping = {k: v for k, v in formats.items() if k in cat_formats}
        return {
            "category": cat_key,
            "source_formats": sorted(list(filtered_mapping.keys())),
            "format_mapping": filtered_mapping,
        }

    return {
        "source_formats": conv.source_formats,
        "categories": semantic_categories,
        "format_mapping": formats,
    }


def run_server():
    """Run FastMCP server over stdio."""
    set_stderr_mode(True)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
