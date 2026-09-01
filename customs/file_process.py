import os
import sys
import json
import time
import uuid
import datetime
import shlex
import shutil
import concurrent.futures
import multiprocessing
from pathlib import Path
from dataclasses import dataclass
from typing import List
from customs.run_command import send_to_trash

FAILED_RUN_FILE = Path.home() / ".convergent_failed.json"

def save_failed_run(failed_files, source_formats, target_format, fps=None, bitrate=None, md_pdf_mode=None, strip_metadata=False, use_cache=True):
    if not failed_files:
        clear_failed_run()
        return
    
    data = {
        "paths": [str(f.resolve()) for f in failed_files],
        "source_formats": source_formats,
        "target_format": target_format,
        "fps": fps,
        "bitrate": bitrate,
        "md_pdf_mode": md_pdf_mode,
        "strip_metadata": strip_metadata,
        "use_cache": use_cache
    }
    try:
        with open(FAILED_RUN_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

def load_failed_run():
    if FAILED_RUN_FILE.exists():
        try:
            with open(FAILED_RUN_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and "paths" in data:
                    return data
        except Exception:
            pass
    return None

def clear_failed_run():
    if FAILED_RUN_FILE.exists():
        try:
            FAILED_RUN_FILE.unlink()
        except Exception:
            pass


try:
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

@dataclass
class FormatDef:
    name: str
    category_id: str
    targets: List[str]
    handler_method: str

FORMAT_REGISTRY = [
    # Image Category ("2")
    FormatDef("ARW", "2", ["JPG", "PNG", "WEBP", "PDF", "TIFF", "BMP", "HEIC", "HEIF", "AVIF"], "convert_image"),
    FormatDef("AVIF", "2", ["JPG", "PNG", "WEBP", "PDF", "TIFF", "BMP", "HEIC", "HEIF"], "convert_image"),
    FormatDef("BMP", "2", ["JPG", "PNG", "WEBP", "PDF", "TIFF", "HEIC", "HEIF", "AVIF"], "convert_image"),
    FormatDef("DNG", "2", ["JPG", "PNG", "WEBP", "PDF", "TIFF", "BMP", "HEIC", "HEIF", "AVIF"], "convert_image"),
    FormatDef("HEIC", "2", ["JPG", "PNG", "WEBP", "PDF", "TIFF", "BMP", "HEIF", "AVIF", "TXT", "MD", "DOCX"], "convert_image"),
    FormatDef("HEIF", "2", ["JPG", "PNG", "WEBP", "PDF", "TIFF", "BMP", "HEIC", "AVIF"], "convert_image"),
    FormatDef("JPG", "2", ["PNG", "WEBP", "PDF", "TIFF", "BMP", "HEIC", "HEIF", "AVIF", "TXT", "MD", "DOCX"], "convert_image"),
    FormatDef("PNG", "2", ["JPG", "WEBP", "PDF", "TIFF", "BMP", "HEIC", "HEIF", "AVIF", "TXT", "MD", "DOCX"], "convert_image"),
    FormatDef("SVG", "2", ["JPG", "PNG", "WEBP", "PDF", "TIFF", "BMP", "HEIC", "HEIF", "AVIF"], "convert_image"),
    FormatDef("TIF", "2", ["JPG", "PNG", "WEBP", "PDF", "BMP", "HEIC", "HEIF", "AVIF"], "convert_image"),
    FormatDef("TIFF", "2", ["JPG", "PNG", "WEBP", "PDF", "BMP", "HEIC", "HEIF", "AVIF"], "convert_image"),
    FormatDef("WEBP", "2", ["JPG", "PNG", "PDF", "TIFF", "BMP", "HEIC", "HEIF", "AVIF"], "convert_image"),

    # Video Category ("3")
    FormatDef("AVI", "3", ["MOV", "MP4", "WEBM", "GIF", "MKV", "MP3", "WAV", "M4A", "FLAC", "TXT", "SRT", "VTT", "MD"], "convert_video"),
    FormatDef("GIF", "3", ["MOV", "MP4", "WEBM", "AVI", "MKV"], "convert_video"),
    FormatDef("MKV", "3", ["MOV", "MP4", "WEBM", "GIF", "AVI", "MP3", "WAV", "M4A", "FLAC", "TXT", "SRT", "VTT", "MD"], "convert_video"),
    FormatDef("MOV", "3", ["MP4", "WEBM", "GIF", "AVI", "MKV", "MP3", "WAV", "M4A", "FLAC", "TXT", "SRT", "VTT", "MD"], "convert_video"),
    FormatDef("MP4", "3", ["MOV", "WEBM", "GIF", "MKV", "MP3", "WAV", "M4A", "FLAC", "TXT", "SRT", "VTT", "MD"], "convert_video"),
    FormatDef("WEBM", "3", ["MOV", "MP4", "GIF", "AVI", "MKV", "MP3", "WAV", "M4A", "FLAC", "TXT", "SRT", "VTT", "MD"], "convert_video"),

    # Audio Category ("4")
    FormatDef("AAC", "4", ["MP3", "WAV", "M4A", "FLAC", "TXT", "SRT", "VTT", "MD"], "convert_audio"),
    FormatDef("FLAC", "4", ["MP3", "WAV", "M4A", "TXT", "SRT", "VTT", "MD"], "convert_audio"),
    FormatDef("M4A", "4", ["MP3", "WAV", "FLAC", "TXT", "SRT", "VTT", "MD"], "convert_audio"),
    FormatDef("MP3", "4", ["WAV", "M4A", "FLAC", "TXT", "SRT", "VTT", "MD"], "convert_audio"),
    FormatDef("OGG", "4", ["MP3", "WAV", "M4A", "FLAC", "TXT", "SRT", "VTT", "MD"], "convert_audio"),
    FormatDef("WAV", "4", ["MP3", "M4A", "FLAC", "TXT", "SRT", "VTT", "MD"], "convert_audio"),

    # Document Category ("5")
    FormatDef("DOCX", "5", ["PDF"], "convert_office"),
    FormatDef("MD", "5", ["PDF", "HTML", "TXT"], "convert_markdown"),
    FormatDef("NTB", "5", ["PDF"], "convert_ntb"),
    FormatDef("PDF", "5", ["JPG", "PNG", "TIFF", "BMP", "TXT", "MD", "DOCX"], "convert_pdf"),
    FormatDef("PPTX", "5", ["PDF"], "convert_office"),
    FormatDef("RTF", "5", ["PDF"], "convert_office"),
]

def get_expected_output_path(source_file: Path, target_format: str) -> Path:
    """
    Returns the expected output Path (file or directory) for a given source file and target format.
    PDF to images (JPG/PNG/etc.) creates a directory named '{stem}_images', whereas PDF to text (OCR)
    or standard conversions create a file named '{stem}.{target_format.lower()}'.
    """
    target_upper = str(target_format).upper().lstrip(".")
    if source_file.suffix.lower() == ".pdf" and target_upper in ("JPG", "PNG", "TIFF", "TIF", "BMP"):
        return source_file.parent / f"{source_file.stem}_images"
    return source_file.with_suffix(f".{target_format.lower()}")


def process_single_file(conv, f, target_format, fps=None, bitrate=None, md_pdf_mode=None, strip_metadata=False, ocr=False, stt=False, model="base", language=None, hwaccel="auto", dpi=None):
    """
    Processes a single file conversion using the provided Converter instance.
    """
    start_time = time.perf_counter()
    source_fmt = f.suffix.lower()[1:].upper()
    
    if target_format not in conv.formats.get(source_fmt, []):
        duration = time.perf_counter() - start_time
        if source_fmt == target_format:
            return f.name, True, "Skipped (Same format)", duration
        return f.name, False, f"Target {target_format} not supported for {source_fmt}", duration

    # Move existing single output file to Trash if it exists
    output_file = get_expected_output_path(f, target_format)
    if output_file.is_file():
        send_to_trash(output_file)

    success = False
    error = ""

    fmt_def = next((fd for fd in FORMAT_REGISTRY if fd.name == source_fmt), None)
    if fmt_def:
        handler = getattr(conv, fmt_def.handler_method, None)
        if handler:
            success, error = handler(
                f,
                target_format,
                fps=fps,
                bitrate=bitrate,
                md_pdf_mode=md_pdf_mode,
                strip_metadata=strip_metadata,
                ocr=ocr,
                stt=stt,
                model=model,
                language=language,
                hwaccel=hwaccel,
                dpi=dpi
            )
        else:
            error = f"Handler method {fmt_def.handler_method} not found on Converter"
    else:
        error = f"Source format {source_fmt} not supported"
    
    duration = time.perf_counter() - start_time
    return f.name, success, error, duration

def process(conv, console, get_char, source_formats, target_format, paths, fps=None, bitrate=None, jobs=None, overwrite=False, skip=False, md_pdf_mode=None, strip_metadata=False, interactive=True, ocr=False, stt=False, model="base", language=None, success_map=None, use_cache=True, hwaccel="auto", dpi=None):
    """
    Processes a batch of files for conversion.
    """
    if isinstance(paths, str):
        paths = [paths]
        
    files = []
    source_fmts_upper = [fmt.upper() for fmt in source_formats]
    found_extensions = set()
    
    for p in paths:
        path_obj = Path(os.path.expanduser(p))
        if path_obj.is_file():
            ext = path_obj.suffix.lower()[1:].upper()
            if ext in source_fmts_upper:
                files.append(path_obj)
            else:
                if path_obj.suffix:
                    found_extensions.add(path_obj.suffix.lower())
        elif path_obj.is_dir():
            for item in path_obj.iterdir():
                if item.is_file():
                    ext = item.suffix.lower()[1:].upper()
                    if ext in source_fmts_upper:
                        files.append(item)
                    if item.suffix:
                        found_extensions.add(item.suffix.lower())
    
    if not files:
        if len(source_formats) == 1:
            msg = f"No {source_formats[0]} files found in the provided paths."
        else:
            msg = "No matching files found in the provided paths."
        
        if found_extensions:
            sorted_exts = sorted(list(found_extensions))
            msg += f" Found: {', '.join(sorted_exts)}"
            
        console.print(f"[bold red]{msg}[/bold red]")
        return []

    # Content-Addressable Cache pre-filter (automatic by default, bypass via --no-cache)
    cached_count = 0
    cached_skipped_files = []  # list of (src, out, reason)
    cache_mgr = None
    if use_cache:
        try:
            from customs.cache import CacheManager
            cache_mgr = CacheManager()
            params_for_cache = {
                "target": target_format,
                "fps": fps,
                "bitrate": bitrate,
                "md_pdf_mode": md_pdf_mode,
                "strip_metadata": strip_metadata,
                "ocr": ocr,
                "stt": stt,
                "model": model,
                "language": language,
                "dpi": dpi,
            }
            remaining_after_cache = []
            for f in files:
                out_path = get_expected_output_path(f, target_format)
                is_valid, reason = cache_mgr.is_cached_valid(f, out_path, params_for_cache)
                if is_valid:
                    cached_count += 1
                    cached_skipped_files.append((f, out_path, reason))
                    # Keep success_map in sync for move/undo flows – treat cached outputs as "converted" for post-actions
                    if isinstance(success_map, dict):
                        success_map[out_path] = f
                    try:
                        console.print(f" [dim]↷ {f.name} → cached ({reason})[/dim]")
                    except Exception:
                        pass
                else:
                    remaining_after_cache.append(f)
            if cached_count > 0:
                console.print(f"[bold cyan]⚡ Cache: {cached_count} file(s) already up-to-date, skipping...[/bold cyan]")
            files = remaining_after_cache
            if not files:
                # All files cached – report and return cached outputs
                if cache_mgr:
                    try:
                        cache_mgr.close()
                    except Exception:
                        pass
                if cached_skipped_files:
                    console.print(f"[bold green]✓ All {cached_count} file(s) cached — no conversion needed.[/bold green]")
                    return [out for _, out, _ in cached_skipped_files]
                return []
        except Exception as e:
            # Cache failures must never break conversion
            try:
                console.print(f"[dim]Cache check failed ({e}), proceeding without cache.[/dim]")
            except Exception:
                pass
            # Ensure files list unchanged if cache init failed
            # (already filtered partially – if error after filtering, keep remaining)
            if 'remaining_after_cache' not in locals():
                pass

    final_files = []
    temp_symlinks = {}
    skipped_count = 0
    batch_start_time = time.perf_counter()
    success_count = 0
    fail_count = 0
    converted_files = []
    failed_files = []
    completed_files = set()
    
    # 1. Identify conflicts
    conflicts = []
    for f in files:
        output = get_expected_output_path(f, target_format)
        if output.exists():
            conflicts.append((f, output))

    keep_all = False
    
    try:
        # Determine global action if multiple conflicts exist
        if len(conflicts) > 1 and not overwrite and not skip:
            is_mock = (console.__class__.__name__ == 'MockConsole')
            if HAS_RICH and not is_mock:
                table = Table(title="\n[bold yellow]⚠ Collision Preview: The following files already exist[/bold yellow]", show_header=True, header_style="bold magenta")
                table.add_column("Source File", style="cyan")
                table.add_column("Existing Output File", style="green")
                table.add_column("Size", justify="right")
                table.add_column("Last Modified", justify="right")
                
                for src, out in conflicts:
                    try:
                        stat = out.stat()
                        mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                        size = stat.st_size
                        # human readable size
                        for unit in ['B', 'KB', 'MB', 'GB']:
                            if size < 1024:
                                size_str = f"{size:.1f} {unit}"
                                break
                            size /= 1024
                        else:
                            size_str = f"{size:.1f} TB"
                    except Exception:
                        size_str = "Unknown"
                        mtime = "Unknown"
                    table.add_row(src.name, out.name, size_str, mtime)
                
                console.print(table)
            else:
                console.print("\n[bold yellow]⚠ Collision Preview: The following files already exist[/bold yellow]")
                console.print(f"   {'Source File':<30} | {'Existing Output':<30} | {'Size':<10} | {'Last Modified'}")
                console.print(f"   {'-'*90}")
                for src, out in conflicts:
                    try:
                        stat = out.stat()
                        mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                        size = stat.st_size
                        for unit in ['B', 'KB', 'MB', 'GB']:
                            if size < 1024:
                                size_str = f"{size:.1f} {unit}"
                                break
                            size /= 1024
                        else:
                            size_str = f"{size:.1f} TB"
                    except Exception:
                        size_str = "Unknown"
                        mtime = "Unknown"
                    console.print(f"   {src.name:<30} | {out.name:<30} | {size_str:<10} | {mtime}")



        for f in files:
            output = get_expected_output_path(f, target_format)
            if output.exists() and not overwrite and not skip and not keep_all:
                console.print(f"\n[bold yellow]⚠  File already exists: {output.name}[/bold yellow]")
                console.print("   [bold]\\[o][/bold] Overwrite   [bold]\\[s][/bold] Skip   [bold]\\[k][/bold] Keep both   [bold]\\[c][/bold] Cancel")
                console.print("   [dim](Or hold SHIFT for all: \\[O] Overwrite All  \\[S] Skip All  \\[K] Keep All)[/dim]")
                
                while True:
                    choice = get_char("   Choice: ")
                    if choice == 'o':
                        console.print()
                        final_files.append(f)
                        break
                    elif choice == 'O':
                        console.print()
                        overwrite = True
                        final_files.append(f)
                        break
                    elif choice == 's':
                        console.print()
                        break
                    elif choice == 'S':
                        console.print()
                        skip = True
                        break
                    elif choice == 'k':
                        console.print()
                        counter = 1
                        stem = f.stem
                        suffix = f.suffix
                        target_suffix = f".{target_format.lower()}"
                        while True:
                            candidate_output = f.parent / f"{stem} ({counter}){target_suffix}"
                            if not candidate_output.exists():
                                break
                            counter += 1
                        
                        temp_source = f.parent / f"{stem} ({counter}){suffix}"
                        try:
                            if temp_source.exists() or temp_source.is_symlink():
                                temp_source.unlink()
                            os.symlink(f.name, str(temp_source))
                            final_files.append(temp_source)
                            temp_symlinks[temp_source] = f
                            console.print(f"   [dim]Will save as: {candidate_output.name}[/dim]")
                        except Exception as e:
                            console.print(f"   [bold red]Error creating temporary file: {e}[/bold red]")
                        break
                    elif choice == 'K':
                        console.print()
                        keep_all = True
                        counter = 1
                        stem = f.stem
                        suffix = f.suffix
                        target_suffix = f".{target_format.lower()}"
                        while True:
                            candidate_output = f.parent / f"{stem} ({counter}){target_suffix}"
                            if not candidate_output.exists():
                                break
                            counter += 1
                        
                        temp_source = f.parent / f"{stem} ({counter}){suffix}"
                        try:
                            if temp_source.exists() or temp_source.is_symlink():
                                temp_source.unlink()
                            os.symlink(f.name, str(temp_source))
                            final_files.append(temp_source)
                            temp_symlinks[temp_source] = f
                            console.print(f"   [dim]Will save as: {candidate_output.name}[/dim]")
                        except Exception as e:
                            console.print(f"   [bold red]Error creating temporary file: {e}[/bold red]")
                        break
                    elif choice.lower() == 'c':
                        console.print()
                        console.print("[yellow]Operation cancelled.[/yellow]")
                        return []
                    else:
                        console.print(" [dim]Invalid choice[/dim]")
                        time.sleep(0.5)
            else:
                if output.exists():
                    if overwrite:
                        final_files.append(f)
                    elif keep_all:
                        counter = 1
                        stem = f.stem
                        suffix = f.suffix
                        target_suffix = f".{target_format.lower()}"
                        while True:
                            candidate_output = f.parent / f"{stem} ({counter}){target_suffix}"
                            if not candidate_output.exists():
                                break
                            counter += 1
                        
                        temp_source = f.parent / f"{stem} ({counter}){suffix}"
                        try:
                            if temp_source.exists() or temp_source.is_symlink():
                                temp_source.unlink()
                            os.symlink(f.name, str(temp_source))
                            final_files.append(temp_source)
                            temp_symlinks[temp_source] = f
                        except Exception as e:
                            console.print(f"   [bold red]Error creating temporary file: {e}[/bold red]")
                else:
                    final_files.append(f)
        
        skipped_count = len(files) - len(final_files)
        if skipped_count > 0 and skip:
            console.print(f"[dim]Skipped {skipped_count} already existing files.[/dim]")
                
        files = final_files
        
        if not files:
            console.print("[bold green]All files already exist and were skipped.[/bold green]")
            return []

        num_files = len(files)
        if num_files > 50:
            console.print(f"\n[bold yellow]Found {num_files} files. Proceed? (y/n)[/bold yellow]")
            if get_char("   Choice: ").lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return []

        console.print(f"[bold cyan]Found {num_files} files to convert...[/bold cyan]")
        
        if not jobs:
            jobs = min(multiprocessing.cpu_count(), len(files))
            
        success_count = 0
        fail_count = 0
        batch_start_time = time.perf_counter()
        converted_files = []
        failed_files = []
        completed_files = set()
        
        if HAS_RICH:
            actual_source_formats = sorted(list(set(f.suffix.lower()[1:].upper() for f in files if f.suffix)))
            if not actual_source_formats:
                actual_source_formats = [fmt.upper() for fmt in source_formats]
            source_label = " + ".join(actual_source_formats) if actual_source_formats else "Files"
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"{source_label} → {target_format}...", total=len(files))
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
                    futures = {executor.submit(process_single_file, conv, f, target_format, fps, bitrate, md_pdf_mode, strip_metadata, ocr, stt, model, language, hwaccel, dpi): f for f in files}
                    
                    try:
                        for future in concurrent.futures.as_completed(futures):
                            orig_file = futures[future]
                            completed_files.add(orig_file)
                            name, success, error, duration = future.result()
                            if success:
                                success_count += 1
                                out_path = get_expected_output_path(orig_file, target_format)
                                converted_files.append(out_path)
                                if isinstance(success_map, dict):
                                    success_map[out_path] = orig_file
                                # Cache: save successful conversion
                                if use_cache and cache_mgr:
                                    try:
                                        if 'params_for_cache' not in locals():
                                            params_for_cache_local = {
                                                "target": target_format,
                                                "fps": fps,
                                                "bitrate": bitrate,
                                                "md_pdf_mode": md_pdf_mode,
                                                "strip_metadata": strip_metadata,
                                                "ocr": ocr,
                                                "stt": stt,
                                                "model": model,
                                                "language": language,
                                                "dpi": dpi,
                                            }
                                        else:
                                            params_for_cache_local = params_for_cache
                                        cache_mgr.save(orig_file, out_path, params_for_cache_local)
                                    except Exception:
                                        pass
                                
                                if error != "Skipped (Same format)":
                                    progress.console.print(f" [bold green]✓[/bold green] {name} [dim]→ {duration:.1f}s[/dim]")
                            else:
                                fail_count += 1
                                failed_files.append(orig_file)
                                error_lines = error.strip().splitlines()
                                if len(error_lines) > 1:
                                    formatted_error = error_lines[0] + "\n" + "\n".join("   " + line for line in error_lines[1:])
                                else:
                                    formatted_error = error.strip()
                                progress.console.print(f" [bold red]✗[/bold red] {name}: [dim]{formatted_error} ({duration:.1f}s)[/dim]")
                            progress.update(task, advance=1)
                    except KeyboardInterrupt:
                        # Cancel remaining futures
                        for fut in futures:
                            fut.cancel()
                        raise
        else:
            # Fallback for systems without rich
            for f in files:
                completed_files.add(f)
                name, success, error, duration = process_single_file(conv, f, target_format, fps, bitrate, md_pdf_mode, strip_metadata, ocr, stt, model, language, hwaccel, dpi)
                if success:
                    success_count += 1
                    out_path = get_expected_output_path(f, target_format)
                    converted_files.append(out_path)
                    if isinstance(success_map, dict):
                        success_map[out_path] = f
                    if use_cache and cache_mgr:
                        try:
                            # Ensure params_for_cache exists (may not if cache init failed earlier)
                            if 'params_for_cache' not in locals():
                                params_for_cache_local = {
                                    "target": target_format,
                                    "fps": fps,
                                    "bitrate": bitrate,
                                    "md_pdf_mode": md_pdf_mode,
                                    "strip_metadata": strip_metadata,
                                    "ocr": ocr,
                                    "stt": stt,
                                    "model": model,
                                    "language": language,
                                }
                            else:
                                params_for_cache_local = params_for_cache
                            cache_mgr.save(f, out_path, params_for_cache_local)
                        except Exception:
                            pass
                    
                    if error != "Skipped (Same format)":
                        console.print(f" > {name}... [bold green]DONE[/bold green] [dim]({duration:.1f}s)[/dim]")
                else:
                    fail_count += 1
                    failed_files.append(f)
                    console.print(f" > {name}... [bold red]FAILED[/bold red] [dim]({duration:.1f}s)[/dim]")
                    if error:
                        error_lines = error.strip().splitlines()
                        formatted_error = "\n".join("   " + line for line in error_lines)
                        console.print(f"[dim]{formatted_error}[/dim]")
    except KeyboardInterrupt:
        # For fallback mode or general handling, gather remaining uncompleted files
        for f in files:
            if f not in completed_files:
                failed_files.append(f)
        raise
    finally:
        if failed_files:
            save_failed_run(failed_files, source_formats, target_format, fps, bitrate, md_pdf_mode, strip_metadata, use_cache=use_cache)
        else:
            clear_failed_run()
        
        for sym in temp_symlinks:
            try:
                sym.unlink()
            except:
                pass

        # Close cache manager
        if use_cache and cache_mgr:
            try:
                cache_mgr.close()
            except Exception:
                pass
            
    total_time = time.perf_counter() - batch_start_time
    summary_parts = [
        f"[bold green]✓ {success_count} converted[/bold green]",
        f"[bold red]✗ {fail_count} failed[/bold red]"
    ]
    if cached_count > 0:
        summary_parts.append(f"[bold cyan]↷ {cached_count} cached[/bold cyan]")
    if skipped_count > 0:
        summary_parts.append(f"[bold yellow]↷ {skipped_count} skipped[/bold yellow]")
    summary_parts.append(f"[bold cyan]⏱ {total_time:.1f}s total[/bold cyan]")
    
    console.print(f"\n{', '.join(summary_parts)}")

    # Include cached outputs in returned list so post-move/undo sees them
    if use_cache and cached_skipped_files:
        try:
            cached_outs = [out for _, out, _ in cached_skipped_files]
            # Avoid duplicates if some were reconverted (shouldn't happen)
            for co in cached_outs:
                if co not in converted_files:
                    converted_files.append(co)
        except Exception:
            pass
    
    if failed_files and interactive and sys.stdin.isatty():
        console.print(f"\n[bold yellow]Retry {len(failed_files)} failed file(s)? (y/n): [/bold yellow]", end="")
        choice = get_char("")
        if choice.lower() == 'y':
            console.print("\n[bold cyan]Retrying failed files...[/bold cyan]")
            retry_paths = [str(f) for f in failed_files]
            retry_converted = process(
                conv, console, get_char, source_formats, target_format, retry_paths,
                fps=fps, bitrate=bitrate, jobs=jobs, overwrite=overwrite, skip=skip,
                md_pdf_mode=md_pdf_mode, strip_metadata=strip_metadata, interactive=interactive, ocr=ocr,
                success_map=success_map, use_cache=use_cache
            )
            converted_files.extend(retry_converted)
            
    return converted_files


def prompt_move_files(console, get_char, get_input, file_paths, original_files=None):
    """
    Prompts the user to optionally move the converted files/folders to another directory,
    or delete the original files.
    If the user presses 'm'/'M', they can enter a folder path to move converted files.
    If the user presses 'd'/'D' and original files are provided, the original files are sent to Trash.
    Otherwise, they can press any other key to continue.
    """
    if not file_paths:
        get_char("\nPress any key to continue...")
        return

    console.print("\n[bold yellow]Post-Convert Options:[/bold yellow]")
    if original_files:
        console.print(" [bold cyan]D.[/bold cyan] Delete original files")
    console.print(" [bold cyan]M.[/bold cyan] Move converted files")
    console.print(" [bold cyan]U.[/bold cyan] Undo")
    console.print(" [bold cyan]Q.[/bold cyan] Quit")
    choice = get_char("\nSelect Option (or any other key to continue): ")
    
    if choice.lower() == 'm':
        console.print()  # Move to new line after char input
        while True:
            dest_dir_str = get_input("[bold yellow]Enter target folder path: [/bold yellow]")
            if not dest_dir_str:
                console.print("[yellow]Move cancelled.[/yellow]")
                get_char("\nPress any key to continue...")
                break
                
            dest_dir_clean = dest_dir_str.strip()
            try:
                parts = shlex.split(dest_dir_clean)
                if parts:
                    dest_dir_clean = parts[0]
            except:
                dest_dir_clean = dest_dir_clean.strip("'\"").strip()
                
            dest_dir = Path(os.path.expanduser(dest_dir_clean))
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                console.print(f"[bold red]Error: Could not create folder '{dest_dir}': {e}[/bold red]")
                continue
                
            moved_count = 0
            for path in file_paths:
                path_obj = Path(path)
                if not path_obj.exists():
                    continue
                try:
                    dest_path = dest_dir / path_obj.name
                    if dest_path.exists():
                        if dest_path.is_dir():
                            shutil.rmtree(dest_path)
                        else:
                            dest_path.unlink()
                    shutil.move(str(path_obj), str(dest_dir))
                    moved_count += 1
                except Exception as e:
                    console.print(f"[bold red]Error: Failed to move {path_obj.name} to {dest_dir}: {e}[/bold red]")
            
            if moved_count > 0:
                console.print(f"[bold green]Successfully moved {moved_count} file(s) to: {dest_dir}[/bold green]")
            else:
                console.print("[yellow]No files were moved.[/yellow]")
            
            get_char("\nPress any key to continue...")
            break
    elif choice.lower() == 'd' and original_files:
        console.print()  # Move to new line after char input
        deleted_count = 0
        for path in original_files:
            path_obj = Path(os.path.expanduser(path))
            if path_obj.exists() or path_obj.is_symlink():
                if send_to_trash(path_obj):
                    deleted_count += 1
                else:
                    try:
                        if path_obj.is_dir():
                            shutil.rmtree(path_obj)
                        else:
                            path_obj.unlink()
                        deleted_count += 1
                    except Exception as e:
                        console.print(f"[bold red]Error deleting {path_obj.name}: {e}[/bold red]")
        if deleted_count > 0:
            console.print(f"[bold green]Successfully deleted {deleted_count} original file(s) (moved to Trash).[/bold green]")
        else:
            console.print("[yellow]No original files were deleted.[/yellow]")
        get_char("\nPress any key to continue...")
    elif choice.lower() == 'u':
        console.print()  # Move to new line after char input
        undone_count = 0
        for path in file_paths:
            path_obj = Path(path)
            if path_obj.exists() or path_obj.is_symlink():
                if send_to_trash(path_obj):
                    undone_count += 1
                else:
                    try:
                        if path_obj.is_dir():
                            shutil.rmtree(path_obj)
                        else:
                            path_obj.unlink()
                        undone_count += 1
                    except Exception as e:
                        console.print(f"[bold red]Error deleting {path_obj.name}: {e}[/bold red]")
        if undone_count > 0:
            console.print(f"[bold green]Successfully undone conversion. Trashed {undone_count} file(s).[/bold green]")
        else:
            console.print("[yellow]No files were undone.[/yellow]")
        get_char("\nPress any key to continue...")
    elif choice.lower() == 'q':
        console.print()
        import sys
        sys.exit(0)
    else:
        console.print()


def process_stream(conv, console, source_format, target_format, input_path=None, output_path=None, to_stdout=False, fps=None, bitrate=None, md_pdf_mode=None, strip_metadata=False, ocr=False, stt=False, model="base", language=None, hwaccel="auto"):
    """
    Processes stream-based conversion (stdin/stdout or Unix pipe).
    Reads binary input from sys.stdin.buffer (or input file) to a temporary file,
    executes single-file conversion via conv.process_single_file,
    and outputs the result to sys.stdout.buffer or output_path.
    """
    workspace_dir = Path(__file__).parent.parent.resolve()
    tmp_dir = workspace_dir / ".convergent_tmp"
    tmp_dir.mkdir(exist_ok=True)

    unique_id = uuid.uuid4().hex
    source_ext = source_format.lower()
    target_ext = target_format.lower()

    temp_source = tmp_dir / f"stream_in_{unique_id}.{source_ext}"
    temp_target = temp_source.with_suffix(f".{target_ext}")

    try:
        if not input_path or input_path == "-":
            # Read binary input from stdin
            with open(temp_source, "wb") as f_out:
                shutil.copyfileobj(sys.stdin.buffer, f_out)
        else:
            # Copy provided input file to temp_source
            shutil.copy2(os.path.expanduser(input_path), temp_source)

        if not temp_source.exists() or temp_source.stat().st_size == 0:
            console.print("[bold red]Error: Received empty input data from stream/file.[/bold red]")
            return False

        fname, success, err, duration = conv.process_single_file(
            temp_source,
            target_format.upper(),
            fps=fps,
            bitrate=bitrate,
            md_pdf_mode=md_pdf_mode,
            strip_metadata=strip_metadata,
            ocr=ocr,
            stt=stt,
            model=model,
            language=language,
            hwaccel=hwaccel
        )

        if not success:
            console.print(f"[bold red]Stream conversion failed: {err}[/bold red]")
            return False

        if temp_target.is_dir():
            if to_stdout:
                console.print("[bold red]Error: Conversion generated multiple output files (directory output), which cannot be streamed to stdout. Please specify an output path.[/bold red]")
                return False
            elif output_path and output_path != "-":
                out_dest = Path(os.path.expanduser(output_path)).resolve()
                if out_dest.exists():
                    send_to_trash(out_dest)
                shutil.copytree(temp_target, out_dest)
                console.print(f"[bold green]✓ Converted stream to directory {out_dest}[/bold green]")
                return True

        if not temp_target.exists():
            console.print("[bold red]Stream conversion succeeded but output temp file was not created.[/bold red]")
            return False

        if to_stdout:
            with open(temp_target, "rb") as f_in:
                shutil.copyfileobj(f_in, sys.stdout.buffer)
                sys.stdout.buffer.flush()
        elif output_path and output_path != "-":
            out_dest = Path(os.path.expanduser(output_path)).resolve()
            out_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(temp_target, out_dest)
            console.print(f"[bold green]✓ Converted stream to {out_dest}[/bold green]")
        else:
            # Default fallback if neither to_stdout nor output_path specified
            with open(temp_target, "rb") as f_in:
                shutil.copyfileobj(f_in, sys.stdout.buffer)
                sys.stdout.buffer.flush()

        return True
    except Exception as e:
        console.print(f"[bold red]Stream processing error: {e}[/bold red]")
        return False
    finally:
        try:
            if temp_source.exists():
                temp_source.unlink()
            if temp_target.exists():
                if temp_target.is_dir():
                    shutil.rmtree(temp_target)
                else:
                    temp_target.unlink()
        except Exception:
            pass

