#!/usr/bin/env python3
"""
Convergent: Private, Local File Converter Utility
-------------------------------------------
Owner: Kaiwen Du
License: Apache License 2.0

Copyright 2026 Kaiwen Du

Licensed under Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with License.
You may obtain a copy of License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See License for specific language governing permissions and
limitations under License.

Description:
    A high-performance CLI tool for batch file conversion including HEIC, 
    video formats (MOV, MP4), office documents (DOCX, PPTX), and images.
    Leverages FFmpeg and ImageMagick for robust processing.
"""

import os
import time
import subprocess
import sys
import argparse
import shlex
from pathlib import Path
from modules import pdf_manip, image, video, audio, doc, compress, decompress, ntb, combine, split, ocr, stt
from customs import shortcut, file_process
from customs.file_process import prompt_move_files, FORMAT_REGISTRY, load_failed_run, clear_failed_run, process_stream
from customs.run_command import run_command
from customs.console import console, set_stderr_mode, get_input, get_char, get_choice, prompt_fps, prompt_bitrate, prompt_strip_metadata

try:
    import termios
except ImportError:
    termios = None

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def clean_paths(path_str):
    if not path_str:
        return []
    if isinstance(path_str, list):
        resolved = []
        for item in path_str:
            resolved.extend(clean_paths(item))
        return resolved
    
    path_str = path_str.replace("\n", "").replace("\r", "").replace("\t", "").strip()
    
    if path_str == "-":
        return ["-"]
    
    # If entire path_str exists as a single file or directory, treat it as one path.
    # This prevents splitting a single path that has spaces but no quotes/escapes.
    try:
        if os.path.exists(os.path.expanduser(path_str)):
            return [path_str]
    except:
        pass
        
    try:
        # Handle shell-escaped paths, quoted paths, and multiple paths separated by spaces
        # shlex.split correctly handles cases like 'History\ \&\ Practice.pdf'
        # or multiple paths like '/path/1' '/path/2' or '/path/1 /path/2'
        if " " in path_str or "\\" in path_str or "'" in path_str or '"' in path_str:
            parts = shlex.split(path_str)
            if parts:
                return [p.strip() for p in parts if p.strip()]
    except:
        pass
    
    # Fallback to manual stripping of quotes if shlex fails or no special chars
    return [path_str.strip("'").strip('"').strip()]

def flush_stdin():
    if termios is not None:
        try:
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except:
            pass

def prompt_paths(action: str, allow_folders: bool = True):
    target_type = "file or folder" if allow_folders else "file"
    console.print(f"\n[bold yellow]Enter {target_type} path(s) to {action}:[/bold yellow]")
    console.print("[dim](Tip: You can either paste or drag and drop here)[/dim]")
    flush_stdin()
    paths = clean_paths(get_input("Path: "))
    flush_stdin()
    return paths


class Converter:
    def __init__(self):
        self.formats = {f.name: f.targets for f in FORMAT_REGISTRY}
        self.source_formats = sorted(list(self.formats.keys()))
        category_names = {
            "2": "Image",
            "3": "Video",
            "4": "Audio",
            "5": "Document"
        }
        self.categories = {
            cat_id: {
                "name": cat_name,
                "extensions": sorted([f.name for f in FORMAT_REGISTRY if f.category_id == cat_id])
            }
            for cat_id, cat_name in category_names.items()
        }

    def convert_heic(self, source, target_ext, strip_metadata=False, **kwargs):
        return image.convert_heic(source, target_ext, strip_metadata=strip_metadata)

    def convert_video(self, source, target_ext, fps=None, bitrate=None, **kwargs):
        is_stt = kwargs.get("stt", False) or target_ext.upper() in ("TXT", "SRT", "VTT", "MD")
        if is_stt:
            return self.convert_stt(source, target_ext, **kwargs)
        return video.convert_video(source, target_ext, fps, bitrate, hwaccel=kwargs.get("hwaccel", "auto"))

    def convert_audio(self, source, target_ext, bitrate=None, **kwargs):
        is_stt = kwargs.get("stt", False) or target_ext.upper() in ("TXT", "SRT", "VTT", "MD")
        if is_stt:
            return self.convert_stt(source, target_ext, **kwargs)
        return audio.convert_audio(source, target_ext, bitrate)

    def convert_stt(self, source, target_ext, **kwargs):
        return stt.convert_audio_to_text(source, target_ext, **kwargs)

    def convert_office(self, source, target_ext, **kwargs):
        return doc.convert_office(source, target_ext)

    def convert_image(self, source, target_ext, strip_metadata=False, **kwargs):
        is_ocr = kwargs.get("ocr", False) or target_ext.upper() in ("TXT", "MD", "DOCX")
        if is_ocr:
            return self.convert_ocr(source, target_ext, **kwargs)
        return image.convert_image(source, target_ext, strip_metadata=strip_metadata)

    def convert_ocr(self, source, target_ext, **kwargs):
        return ocr.convert_image_to_text(source, target_ext, **kwargs)

    def convert_pdf(self, source, target_ext, **kwargs):
        is_ocr = kwargs.get("ocr", False) or target_ext.upper() in ("TXT", "MD", "DOCX")
        if is_ocr:
            return self.convert_ocr(source, target_ext, **kwargs)
        dpi = kwargs.get("dpi", 300)
        return pdf_manip.convert_pdf_to_image(source, target_ext, dpi=dpi)

    def convert_ntb(self, source, target_ext, **kwargs):
        return ntb.convert_ntb(source, target_ext)

    def convert_markdown(self, source, target_ext, md_pdf_mode=None, **kwargs):
        return doc.convert_markdown(source, target_ext, md_pdf_mode)

    def combine_pdfs(self, paths, output_path=None, interactive=True):
        return combine.combine_pdfs(paths, output_path=output_path, interactive=interactive)

    def combine_videos(self, paths, output_path=None, interactive=True):
        return combine.combine_videos(paths, output_path=output_path, interactive=interactive)

    def combine_audios(self, paths, output_path=None, interactive=True):
        return combine.combine_audios(paths, output_path=output_path, interactive=interactive)

    def combine_gifs(self, paths, output_path=None, interactive=True):
        return combine.combine_gifs(paths, output_path=output_path, interactive=interactive)

    def combine_docx(self, paths, output_path=None, interactive=True):
        return combine.combine_docx(paths, output_path=output_path, interactive=interactive)

    def combine_pptx(self, paths, output_path=None, interactive=True):
        return combine.combine_pptx(paths, output_path=output_path, interactive=interactive)

    def combine_txt(self, paths, output_path=None, interactive=True):
        return combine.combine_txt(paths, output_path=output_path, interactive=interactive)

    def get_pdf_page_count(self, path):
        return combine.get_pdf_page_count(path)

    def split_pdf(self, path, mode="pages", ranges=None, num_parts=None, output_dir=None, interactive=True, display_name=None):
        return split.split_pdf(path, mode=mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=interactive, display_name=display_name)

    def split_video(self, path, mode="interval", interval=None, ranges=None, num_parts=None, output_dir=None, interactive=True):
        return split.split_video(path, mode=mode, interval=interval, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=interactive)

    def split_audio(self, path, mode="interval", interval=None, ranges=None, num_parts=None, output_dir=None, interactive=True):
        return split.split_audio(path, mode=mode, interval=interval, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=interactive)

    def split_gif(self, path, mode="frames", frame_format="png", interval=None, ranges=None, num_parts=None, output_dir=None, interactive=True):
        return split.split_gif(path, mode=mode, frame_format=frame_format, interval=interval, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=interactive)

    def split_docx(self, path, mode="pages", ranges=None, num_parts=None, output_dir=None, interactive=True):
        return split.split_docx(path, mode=mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=interactive)

    def split_pptx(self, path, mode="pages", ranges=None, num_parts=None, output_dir=None, interactive=True):
        return split.split_pptx(path, mode=mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=interactive)

    def compress(self, paths, output_name, format_choice, password=None):
        return compress.compress(paths, output_name, format_choice, password)

    def decompress(self, path, output_dir=None):
        return decompress.decompress(path, output_dir)

    def process_single_file(self, f, target_format, fps=None, bitrate=None, md_pdf_mode=None, strip_metadata=False, ocr=False, stt=False, model="base", language=None, hwaccel="auto", dpi=None):
        return file_process.process_single_file(self, f, target_format, fps=fps, bitrate=bitrate, md_pdf_mode=md_pdf_mode, strip_metadata=strip_metadata, ocr=ocr, stt=stt, model=model, language=language, hwaccel=hwaccel, dpi=dpi)

    def process(self, source_formats, target_format, paths, fps=None, bitrate=None, jobs=None, overwrite=False, skip=False, md_pdf_mode=None, strip_metadata=False, interactive=True, ocr=False, stt=False, model="base", language=None, success_map=None, use_cache=True, hwaccel="auto", dpi=None):
        return file_process.process(self, console, get_char, source_formats, target_format, paths, fps, bitrate, jobs, overwrite, skip, md_pdf_mode, strip_metadata, interactive, ocr=ocr, stt=stt, model=model, language=language, success_map=success_map, use_cache=use_cache, hwaccel=hwaccel, dpi=dpi)

def check_and_prompt_md_pdf(target_fmt, paths, console, get_char, time):
    if target_fmt != "PDF" or not paths:
        return None
        
    has_md = False
    for p in paths:
        path_obj = Path(os.path.expanduser(p))
        if path_obj.is_file() and path_obj.suffix.lower() == ".md":
            has_md = True
            break
        elif path_obj.is_dir():
            try:
                for item in path_obj.iterdir():
                    if item.is_file() and item.suffix.lower() == ".md":
                        has_md = True
                        break
            except:
                pass
            if has_md:
                break
                
    if not has_md:
        return None
        
    while True:
        console.print("\n[bold yellow]Markdown (.md) files detected! Select rendering mode for PDF:[/bold yellow]")
        console.print(" 1. Human-friendly PDF (renders bold, tables, lists, etc. correctly)")
        console.print(" 2. Raw PDF (displays raw Markdown text and symbols)")
        console.print(" [bold white]B[/bold white]. Back")
        md_choice = get_char("\nSelect Option: ")
        if md_choice.lower() == 'b':
            console.print()
            return "back"
        elif md_choice == '1':
            console.print()
            return "formatted"
        elif md_choice == '2':
            console.print()
            return "raw"
        else:
            console.print(" [dim]Invalid choice[/dim]")
            time.sleep(0.5)

def build_parser() -> argparse.ArgumentParser:
    """Builds and returns top-level argument parser for Convergent CLI."""
    parser = argparse.ArgumentParser(description="Convergent: Local File Converter")
    parser.add_argument("--from", dest="from_fmt", help="Source format (e.g., JPG, MOV)")
    parser.add_argument("--to", dest="to_fmt", help="Target format (e.g., PNG, MP3)")
    parser.add_argument("--fps", help="Frames per second for GIF conversion (e.g., 30, 60)")
    parser.add_argument("--bitrate", help="Audio bitrate for MP3 conversion (e.g., 128k, 192k, 320k)")
    parser.add_argument("--md-pdf-mode", choices=["formatted", "raw"], default="formatted", help="Rendering mode for Markdown to PDF (default: formatted)")
    parser.add_argument("--path", nargs="+", help="Path to file or directory")
    parser.add_argument("--stdin", action="store_true", help="Read binary input from standard input (stdin)")
    parser.add_argument("--stdout", action="store_true", help="Write binary converted output to standard output (stdout)")
    parser.add_argument("--jobs", "-j", type=int, help="Number of parallel jobs (default: CPU count)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files without prompting")
    parser.add_argument("--skip", action="store_true", help="Skip existing output files without prompting")
    parser.add_argument("--strip-metadata", action="store_true", help="Remove EXIF/IPTC/metadata from images for privacy")
    parser.add_argument("--dpi", type=int, default=None, help="Resolution DPI for PDF to image conversion (default: 300)")
    parser.add_argument("--stt", action="store_true", help="Perform Speech-to-Text transcription on audio/video input")
    parser.add_argument("--model", default="base", choices=["standard", "mini", "medium", "large", "tiny", "base", "small", "turbo", "large-v3-turbo"], help="Whisper model size for STT: standard (~142MB), mini (~75MB), medium (~466MB), large (~1.5GB); default: standard")
    parser.add_argument("--language", default=None, help="Language code for STT transcription (e.g. en, es, zh, auto)")
    parser.add_argument("--hwaccel", choices=["auto", "videotoolbox", "nvenc", "qsv", "none"], default="auto", help="Hardware acceleration mode for video encoding (default: auto)")
    parser.add_argument("--cache", action="store_true", help="Enable content-addressable cache to skip unchanged files (default: enabled)")
    parser.add_argument("--no-cache", "--force", action="store_true", dest="no_cache", help="Disable cache and force re-conversion of all files")
    parser.add_argument("--cache-ttl", type=float, default=None, help="Cache Time-To-Live in days (default: 30 days, 0 to disable expiration)")
    parser.add_argument("--resume", action="store_true", help="Resume / retry last failed batch conversion")
    parser.add_argument("--shortcut", dest="shortcut_key", help="Run a saved shortcut by key symbol (requires --path unless shortcut has a fixed path)")
    parser.add_argument("--mcp", action="store_true", help="Launch local MCP (Model Context Protocol) server over stdio")
    return parser


def handle_combine(conv, paths, console, get_char, get_choice, get_input):
    pdf_files = []
    mp4_files = []
    mp3_files = []
    gif_files = []
    docx_files = []
    pptx_files = []
    txt_files = []
    for p in paths:
        path_obj = Path(os.path.expanduser(p))
        if path_obj.is_file():
            suffix = path_obj.suffix.lower()
            if suffix == ".pdf":
                pdf_files.append(path_obj)
            elif suffix == ".mp4":
                mp4_files.append(path_obj)
            elif suffix == ".mp3":
                mp3_files.append(path_obj)
            elif suffix == ".gif":
                gif_files.append(path_obj)
            elif suffix == ".docx":
                docx_files.append(path_obj)
            elif suffix == ".pptx":
                pptx_files.append(path_obj)
            elif suffix == ".txt":
                txt_files.append(path_obj)
        elif path_obj.is_dir():
            pdf_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"])
            mp4_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".mp4"])
            mp3_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"])
            gif_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".gif"])
            docx_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".docx"])
            pptx_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".pptx"])
            txt_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".txt"])
    
    combine_type = None
    available_types = []
    if pdf_files: available_types.append(('pdf', 'PDF files'))
    if mp4_files: available_types.append(('mp4', 'MP4 files'))
    if mp3_files: available_types.append(('mp3', 'MP3 files'))
    if gif_files: available_types.append(('gif', 'GIF files'))
    if docx_files: available_types.append(('docx', 'DOCX files'))
    if pptx_files: available_types.append(('pptx', 'PPTX files'))
    if txt_files: available_types.append(('txt', 'TXT files'))
    
    if len(available_types) > 1:
        console.print("\n[bold yellow]Found multiple file types. What do you want to combine?[/bold yellow]")
        for i, (t_code, t_name) in enumerate(available_types, 1):
            console.print(f" {i}. {t_name}")
        console.print(" [bold white]B[/bold white]. Back")
        c_choice = get_choice("\nSelect Option: ", choices=available_types)
        if c_choice.lower() == 'b':
            return False
        try:
            c_idx = int(c_choice) - 1
            if 0 <= c_idx < len(available_types):
                combine_type = available_types[c_idx][0]
        except ValueError:
            pass
        if not combine_type:
            return False
    elif len(available_types) == 1:
        combine_type = available_types[0][0]
    else:
        console.print("[bold red]No PDF, MP4, MP3, GIF, DOCX, PPTX, or TXT files found to combine.[/bold red]")
        get_char("\nPress any key to continue...")
        return False
    
    out_path = None
    if combine_type == 'pdf':
        out_path = conv.combine_pdfs(paths)
    elif combine_type == 'mp4':
        out_path = conv.combine_videos(paths)
    elif combine_type == 'mp3':
        out_path = conv.combine_audios(paths)
    elif combine_type == 'gif':
        out_path = conv.combine_gifs(paths)
    elif combine_type == 'docx':
        out_path = conv.combine_docx(paths)
    elif combine_type == 'pptx':
        out_path = conv.combine_pptx(paths)
    elif combine_type == 'txt':
        out_path = conv.combine_txt(paths)
    
    if out_path:
        prompt_move_files(console, get_char, get_input, [out_path], original_files=paths)
        return True
    else:
        get_char("\nPress any key to continue...")
        return False

def handle_split(conv, paths, console, get_char, get_input):
    split_dirs = []
    for path in paths:
        p = Path(path)
        if p.is_dir():
            continue
        if p.suffix.lower() == ".pdf":
            out_dir = conv.split_pdf(path)
            if out_dir:
                split_dirs.append(out_dir)
        elif p.suffix.lower() == ".mp4":
            out_dir = conv.split_video(path)
            if out_dir:
                split_dirs.append(out_dir)
        elif p.suffix.lower() == ".mp3":
            out_dir = conv.split_audio(path)
            if out_dir:
                split_dirs.append(out_dir)
        elif p.suffix.lower() == ".gif":
            out_dir = conv.split_gif(path)
            if out_dir:
                split_dirs.append(out_dir)
        elif p.suffix.lower() == ".docx":
            out_dir = conv.split_docx(path)
            if out_dir:
                split_dirs.append(out_dir)
        elif p.suffix.lower() == ".pptx":
            out_dir = conv.split_pptx(path)
            if out_dir:
                split_dirs.append(out_dir)
        else:
            console.print(f"[bold red]Error: Unsupported file type '{p.suffix}' for {p.name}. Only PDF, MP4, MP3, GIF, DOCX, and PPTX are supported for splitting.[/bold red]")
    
    if split_dirs:
        prompt_move_files(console, get_char, get_input, split_dirs, original_files=paths)
        return True
    else:
        get_char("\nPress any key to continue...")
        return False

def handle_resize(conv, paths, console, get_char, get_input):
    from modules import resize
    return resize.resize_media(paths, conv, console, get_char, get_input)

def handle_compress(conv, paths, console, get_char, get_input, time):
    total_files = 0
    for p in paths:
        path_obj = Path(os.path.expanduser(p))
        if path_obj.is_file():
            total_files += 1
        elif path_obj.is_dir():
            for _ in path_obj.rglob('*'):
                if _.is_file():
                    total_files += 1
    
    if total_files > 50:
        console.print(f"\n[bold yellow]Found {total_files} files to compress. Proceed? (y/n)[/bold yellow]")
        if get_char("   Choice: ").lower() != 'y':
            console.print("[yellow]Operation cancelled.[/yellow]")
            get_char("\nPress any key to continue...")
            return False
        
    console.print(f"\n[bold yellow]Select target format:[/bold yellow]")
    console.print(" 1. 7z")
    console.print(" 2. rar")
    console.print(" 3. tar.bz2")
    console.print(" 4. tar.gz")
    console.print(" 5. tar.xz")
    console.print(" 6. zip")
    console.print(" [bold white]B[/bold white]. Back")
    fmt_choice = get_char("\nSelect Option: ")
    
    if fmt_choice.lower() == 'b':
        return False
        
    target_fmt = (
        "7Z" if fmt_choice == '1' else
        "RAR" if fmt_choice == '2' else
        "TAR.BZ2" if fmt_choice == '3' else
        "TAR.GZ" if fmt_choice == '4' else
        "TAR.XZ" if fmt_choice == '5' else
        "ZIP" if fmt_choice == '6' else
        None
    )
    if not target_fmt:
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return False
    
    console.print()
        
    password = None
    if target_fmt in ["ZIP", "7Z", "RAR"]:
        console.print(f"\n[bold yellow]Add password protection? (y/n):[/bold yellow]", end=" ")
        pwd_yn = get_char("")
        if pwd_yn.lower() == 'y':
            password = get_input("\nEnter password: ")
    
    output_name = get_input(f"\nEnter name for archive (default: compressed.{target_fmt.lower()}): ")
    if not output_name:
        output_name = f"compressed.{target_fmt.lower()}"
        
    success, error, out_path = conv.compress(paths, output_name, target_fmt, password)
    if success:
        console.print(f"\n[bold green]Successfully compressed into {output_name}[/bold green]")
        prompt_move_files(console, get_char, get_input, [out_path], original_files=paths)
        return True
    else:
        console.print(f"\n[bold red]FAILED to compress:[/bold red]")
        console.print(f"   [dim]{error.strip()}[/dim]")
        get_char("\nPress any key to continue...")
        return False

def handle_decompress(conv, paths, console, get_char, get_input, flush_stdin, clean_paths):
    console.print(f"\n[bold yellow]Enter output directory (leave blank for default):[/bold yellow]")
    flush_stdin()
    out_dirs = clean_paths(get_input("Dir: "))
    out_dir = out_dirs[0] if out_dirs else None
    flush_stdin()
        
    num_archives = len(paths)
    if num_archives > 50:
        console.print(f"\n[bold yellow]Found {num_archives} archives to decompress. Proceed? (y/n)[/bold yellow]")
        if get_char("   Choice: ").lower() != 'y':
            console.print("[yellow]Operation cancelled.[/yellow]")
            get_char("\nPress any key to continue...")
            return False

    decompressed_dirs = []
    for path in paths:
        success, error, actual_out_dir = conv.decompress(path, out_dir)
        if success:
            console.print(f"\n[bold green]Successfully decompressed {Path(path).name}.[/bold green]")
            decompressed_dirs.append(actual_out_dir)
        else:
            console.print(f"\n[bold red]FAILED to decompress {Path(path).name}:[/bold red]")
            console.print(f"   [dim]{error.strip()}[/dim]")
    
    if decompressed_dirs:
        prompt_move_files(console, get_char, get_input, decompressed_dirs, original_files=paths)
        return True
    else:
        get_char("\nPress any key to continue...")
        return False

def handle_ocr(conv, paths, console, get_char, get_input, time):
    console.print(f"\n[bold yellow]Select target format for OCR text:[/bold yellow]")
    console.print(" 1. txt")
    console.print(" 2. md")
    console.print(" 3. docx")
    console.print(" 4. pdf")
    console.print(" [bold white]B[/bold white]. Back")
    fmt_choice = get_char("\nSelect Option: ")
    
    if fmt_choice.lower() == 'b':
        return False
    
    target_fmt = (
        "TXT" if fmt_choice == '1' else
        "MD" if fmt_choice == '2' else
        "DOCX" if fmt_choice == '3' else
        "PDF" if fmt_choice == '4' else
        None
    )
    
    if not target_fmt:
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return False
        
    success_map = {}
    converted = conv.process(["JPG", "PNG", "HEIC", "PDF"], target_fmt, paths, ocr=True, success_map=success_map, use_cache=True)
    if converted:
        prompt_move_files(console, get_char, get_input, converted, original_files=list(success_map.values()))
        return True
    else:
        get_char("\nPress any key to continue...")
        return False

def handle_stt(conv, paths, console, get_char, get_input, time):
    console.print(f"\n[bold yellow]Select target format for Speech-to-Text:[/bold yellow]")
    console.print(" 1. txt")
    console.print(" 2. srt")
    console.print(" 3. vtt")
    console.print(" 4. md")
    console.print(" [bold white]B[/bold white]. Back")
    fmt_choice = get_char("\nSelect Option: ")

    if fmt_choice.lower() == 'b':
        return False

    target_fmt = (
        "TXT" if fmt_choice == '1' else
        "SRT" if fmt_choice == '2' else
        "VTT" if fmt_choice == '3' else
        "MD" if fmt_choice == '4' else
        None
    )

    if not target_fmt:
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return False

    console.print(f"\n[bold yellow]Select STT model size:[/bold yellow]")
    console.print(" 1. Standard (~142MB)")
    console.print(" 2. Mini (~75MB)")
    console.print(" 3. Medium (~466MB)")
    console.print(" 4. Large (~1.5GB)")
    console.print(" [bold white]B[/bold white]. Back")
    model_choice = get_char("\nSelect Option: ")

    if model_choice.lower() == 'b':
        return False

    model = (
        "tiny" if model_choice == '2' else
        "small" if model_choice == '3' else
        "turbo" if model_choice == '4' else
        "base"
    )

    success_map = {}
    converted = conv.process(
        ["MP3", "WAV", "M4A", "FLAC", "AAC", "OGG", "MP4", "MOV", "MKV", "WEBM", "AVI"],
        target_fmt,
        paths,
        stt=True,
        model=model,
        success_map=success_map,
        use_cache=True
    )
    if converted:
        prompt_move_files(console, get_char, get_input, converted, original_files=list(success_map.values()))
        return True
    else:
        get_char("\nPress any key to continue...")
        return False

def handle_convert(conv, cat_id, paths, console, get_char, get_choice, get_input, prompt_fps, prompt_bitrate, prompt_strip_metadata, check_and_prompt_md_pdf, time):
    category = conv.categories[cat_id]
    source_fmts = category["extensions"]
    
    available_targets = set()
    for fmt in source_fmts:
        available_targets.update(conv.formats.get(fmt, []))
    
    sorted_targets = sorted(list(available_targets))
    
    console.print(f"\n[bold yellow]Convert to:[/bold yellow]")
    for i, fmt in enumerate(sorted_targets, 1):
        console.print(f" {i}. {fmt.lower()}")
    console.print(" [bold white]B[/bold white]. Back")
    
    target_choice = get_choice("\nSelect Option: ", choices=sorted_targets)
    if target_choice.lower() == 'b':
        console.print()
        return False
        
    try:
        to_idx = int(target_choice) - 1
        if to_idx < 0 or to_idx >= len(sorted_targets):
            raise ValueError
        target_fmt = sorted_targets[to_idx]
    except ValueError:
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return False
    
    console.print()
        
    fps = None
    if target_fmt == "GIF":
        status, val = prompt_fps()
        if status in ("back", "invalid"):
            return False
        fps = val
        
    bitrate = None
    if target_fmt == "MP3":
        status, val = prompt_bitrate()
        if status in ("back", "invalid"):
            return False
        bitrate = val

    strip_metadata = False
    if cat_id == '2':
        status, val = prompt_strip_metadata()
        if status in ("back", "invalid"):
            return False
        strip_metadata = val

    md_pdf_mode = check_and_prompt_md_pdf(target_fmt, paths, console, get_char, time)
    if md_pdf_mode == "back":
        return False

    success_map = {}
    converted = conv.process(source_fmts, target_fmt, paths, fps=fps, bitrate=bitrate, md_pdf_mode=md_pdf_mode, strip_metadata=strip_metadata, success_map=success_map, use_cache=True)
    if converted:
        prompt_move_files(console, get_char, get_input, converted, original_files=list(success_map.values()))
        return True
    else:
        get_char("\nPress any key to continue...")
        return False


def main():
    conv = Converter()
    parser = build_parser()
    args = parser.parse_args()

    if args.cache_ttl is not None:
        os.environ["CONVERGENT_CACHE_TTL_DAYS"] = str(args.cache_ttl)

    use_cache = not args.no_cache

    if args.mcp:
        import importlib
        mcp_server_mod = importlib.import_module("mcp_server.server")
        mcp_server_mod.run_server()
        sys.exit(0)

    if args.resume:
        failed_run = load_failed_run()
        if not failed_run:
            console.print("[bold yellow]No failed run to resume.[/bold yellow]")
            sys.exit(0)
            
        paths = failed_run["paths"]
        existing_failed = [p for p in paths if os.path.exists(p)]
        if not existing_failed:
            console.print("[bold yellow]None of failed files from last run exist anymore.[/bold yellow]")
            clear_failed_run()
            sys.exit(0)
            
        source_fmts = failed_run["source_formats"]
        target_fmt = failed_run["target_format"]
        fps = failed_run.get("fps")
        bitrate = failed_run.get("bitrate")
        md_pdf_mode = failed_run.get("md_pdf_mode")
        strip_metadata = failed_run.get("strip_metadata", False)
        use_cache_failed = failed_run.get("use_cache", True) and not args.no_cache
        
        console.print(f"[bold cyan]Resuming last failed batch run: {len(existing_failed)} file(s)...[/bold cyan]")
        conv.process(source_fmts, target_fmt, existing_failed, fps=fps, bitrate=bitrate, jobs=args.jobs, overwrite=args.overwrite, skip=args.skip, md_pdf_mode=md_pdf_mode, strip_metadata=strip_metadata, interactive=False, use_cache=use_cache_failed, hwaccel=args.hwaccel)
        return

    if args.shortcut_key:
        paths = clean_paths(args.path) if args.path else None
        ok = shortcut.run_shortcut(
            conv, console, get_char, get_input, flush_stdin, clean_paths,
            check_and_prompt_md_pdf if sys.stdin.isatty() else None,
            prompt_move_files if sys.stdin.isatty() else None,
            args.shortcut_key,
            paths=paths,
            interactive=sys.stdin.isatty(),
            md_pdf_mode=args.md_pdf_mode,
            jobs=args.jobs,
            overwrite=args.overwrite,
            skip=args.skip,
            use_cache=use_cache,
            cli_bitrate=args.bitrate,
            cli_strip_metadata=args.strip_metadata,
            prompt_fps=prompt_fps,
            prompt_bitrate=prompt_bitrate,
            prompt_strip_metadata=prompt_strip_metadata,
        )
        sys.exit(0 if ok else 1)

    # Check if stream mode (stdin/stdout or Unix pipe) is requested or auto-detected
    is_stdin_req = args.stdin or (args.path and args.path[0] == "-") or (not sys.stdin.isatty() and args.from_fmt is not None and not args.path)

    input_p = "-" if is_stdin_req else None
    output_p = None
    if args.path:
        clean_p = clean_paths(args.path)
        if clean_p:
            if clean_p[0] != "-":
                input_p = clean_p[0]
            if len(clean_p) > 1 and clean_p[1] != "-":
                output_p = clean_p[1]

    is_stdout_req = args.stdout or (args.path and len(args.path) > 1 and args.path[1] == "-") or (output_p is None and not sys.stdout.isatty() and (is_stdin_req or args.stdin or args.stdout))

    if is_stdin_req or args.stdin or args.stdout or (args.path and "-" in args.path):
        if not args.from_fmt or not args.to_fmt:
            if is_stdout_req:
                set_stderr_mode(True)
            console.print("[bold red]Error: Stream processing (--stdin / --stdout / Unix pipe) requires both --from and --to flags.[/bold red]")
            sys.exit(1)

        source_fmt = args.from_fmt.upper()
        target_fmt = args.to_fmt.upper()

        if source_fmt not in conv.formats:
            if is_stdout_req:
                set_stderr_mode(True)
            console.print(f"[bold red]Error: Unsupported source format '{source_fmt}'.[/bold red]")
            sys.exit(1)
        if target_fmt not in conv.formats[source_fmt]:
            if is_stdout_req:
                set_stderr_mode(True)
            console.print(f"[bold red]Error: Unsupported target format '{target_fmt}' for {source_fmt}.[/bold red]")
            sys.exit(1)

        if args.bitrate and args.bitrate not in ["128k", "192k", "320k"]:
            if is_stdout_req:
                set_stderr_mode(True)
            console.print("[bold red]Error: Invalid bitrate. Choose from 128k, 192k, 320k.[/bold red]")
            sys.exit(1)

        if is_stdout_req:
            set_stderr_mode(True)

        is_ocr = source_fmt in ("JPG", "PNG", "HEIC", "PDF") and target_fmt in ("TXT", "MD", "DOCX")
        is_stt = args.stt or (target_fmt in ("TXT", "SRT", "VTT", "MD") and source_fmt in ("MP3", "WAV", "M4A", "FLAC", "AAC", "OGG", "MP4", "MOV", "MKV", "WEBM", "AVI"))

        success = file_process.process_stream(
            conv,
            console,
            source_fmt,
            target_fmt,
            input_path=input_p,
            output_path=output_p,
            to_stdout=is_stdout_req,
            fps=args.fps,
            bitrate=args.bitrate,
            md_pdf_mode=args.md_pdf_mode,
            strip_metadata=args.strip_metadata,
            ocr=is_ocr,
            stt=is_stt,
            model=args.model,
            language=args.language,
            hwaccel=args.hwaccel
        )
        sys.exit(0 if success else 1)

    if args.from_fmt or args.to_fmt or args.path:
        if not all([args.from_fmt, args.to_fmt, args.path]):
            console.print("[bold red]Error: When using CLI flags, you must provide --from, --to, and --path.[/bold red]")
            sys.exit(1)
            
        source_fmt = args.from_fmt.upper()
        target_fmt = args.to_fmt.upper()
        
        if source_fmt not in conv.formats:
            console.print(f"[bold red]Error: Unsupported source format '{source_fmt}'.[/bold red]")
            sys.exit(1)
        if target_fmt not in conv.formats[source_fmt]:
            console.print(f"[bold red]Error: Unsupported target format '{target_fmt}' for {source_fmt}.[/bold red]")
            sys.exit(1)
            
        if args.bitrate and args.bitrate not in ["128k", "192k", "320k"]:
            console.print("[bold red]Error: Invalid bitrate. Choose from 128k, 192k, 320k.[/bold red]")
            sys.exit(1)
            
        paths = clean_paths(args.path)
        is_ocr = source_fmt in ("JPG", "PNG", "HEIC", "PDF") and target_fmt in ("TXT", "MD", "DOCX")
        is_stt = args.stt or (target_fmt in ("TXT", "SRT", "VTT", "MD") and source_fmt in ("MP3", "WAV", "M4A", "FLAC", "AAC", "OGG", "MP4", "MOV", "MKV", "WEBM", "AVI"))
        converted = conv.process([source_fmt], target_fmt, paths, fps=args.fps, bitrate=args.bitrate, jobs=args.jobs, overwrite=args.overwrite, skip=args.skip, md_pdf_mode=args.md_pdf_mode, strip_metadata=args.strip_metadata, interactive=False, ocr=is_ocr, stt=is_stt, model=args.model, language=args.language, use_cache=use_cache, hwaccel=args.hwaccel, dpi=args.dpi)
        sys.exit(0 if converted else 1)

    while True:
        shortcuts = shortcut.load_shortcuts()
        
        clear_screen()
        console.rule("Convergent")
        
        if shortcuts:
            console.print("\n[bold yellow]Your Shortcuts:[/bold yellow]")
            for sym, sc in shortcuts.items():
                console.print(f" [bold cyan]{sym}.[/bold cyan] {sc['title']}")
            console.print()

        console.print(" [bold white]+.[/bold white] Add Shortcut")
        if shortcuts:
            console.print(" [bold white]-.[/bold white] Remove Shortcut")
            console.print(" [bold white]=.[/bold white] Edit Shortcut")
            
        failed_run = load_failed_run()
        existing_failed = []
        if failed_run:
            existing_failed = [p for p in failed_run["paths"] if os.path.exists(p)]
            if existing_failed:
                console.print(f"\n[bold red]Last Run Failed: {len(existing_failed)} file(s) pending[/bold red]")
                console.print(f" [bold cyan]R.[/bold cyan] Retry last failed run ({failed_run['target_format'].lower()})")
            else:
                clear_failed_run()
                failed_run = None
                
        console.print(" [bold white]Q.[/bold white] Quit")
        
        console.print("\n[bold yellow]Enter file or folder path(s) to continue:[/bold yellow]")
        console.print("[dim](Tip: You can either paste or drag and drop here)[/dim]")
        flush_stdin()
        raw_input = get_input("Path: ")
        flush_stdin()

        if not raw_input or not raw_input.strip():
            continue

        trimmed = raw_input.strip()

        if trimmed.lower() == 'q':
            console.print()
            break

        if trimmed == '+':
            shortcut.add_shortcut(shortcuts, conv, console, get_char, get_input, flush_stdin, clean_paths)
            continue

        if trimmed == '-' and shortcuts:
            shortcut.remove_shortcut(shortcuts, console, get_input, get_char)
            continue

        if trimmed == '=' and shortcuts:
            shortcut.edit_shortcut(shortcuts, conv, console, get_char, get_input, clean_paths)
            continue

        if trimmed.lower() == 'r' and failed_run and existing_failed:
            console.print()
            paths = failed_run["paths"]
            source_fmts = failed_run["source_formats"]
            target_fmt = failed_run["target_format"]
            fps = failed_run.get("fps")
            bitrate = failed_run.get("bitrate")
            md_pdf_mode = failed_run.get("md_pdf_mode")
            strip_metadata = failed_run.get("strip_metadata", False)
            
            success_map = {}
            converted = conv.process(source_fmts, target_fmt, existing_failed, fps=fps, bitrate=bitrate, md_pdf_mode=md_pdf_mode, strip_metadata=strip_metadata, success_map=success_map)
            prompt_move_files(console, get_char, get_input, converted, original_files=list(success_map.values()))
            continue

        if trimmed.upper() in shortcuts:
            console.print()
            shortcut.run_shortcut(
                conv, console, get_char, get_input, flush_stdin, clean_paths,
                check_and_prompt_md_pdf, prompt_move_files,
                trimmed.upper(),
                interactive=True,
                prompt_fps=prompt_fps,
                prompt_bitrate=prompt_bitrate,
                prompt_strip_metadata=prompt_strip_metadata,
            )
            continue

        paths = clean_paths(raw_input)
        if not paths:
            continue

        valid_paths = [p for p in paths if os.path.exists(os.path.expanduser(p))]
        if not valid_paths:
            console.print(f"[bold red]Error: Specified file or folder path does not exist.[/bold red]")
            get_char("\nPress any key to continue...")
            continue

        # Screen 2: Context-Aware "Convert from:" Menu
        while True:
            clear_screen()
            console.rule("Convergent")

            if len(valid_paths) == 1:
                p_obj = Path(os.path.expanduser(valid_paths[0]))
                desc = f"{p_obj.name}/" if p_obj.is_dir() else p_obj.name
                console.print(f"\n[bold]Detected:[/bold] [cyan]{desc}[/cyan]")
            else:
                console.print(f"\n[bold]Detected:[/bold] [cyan]{len(valid_paths)} items[/cyan]")

            matched_entries = shortcut.get_applicable_menu_entries(conv, valid_paths)
            if not matched_entries:
                console.print("[bold red]No supported operations found for the provided path(s).[/bold red]")
                get_char("\nPress any key to continue...")
                break

            console.print("\n[bold yellow]Convert from:[/bold yellow]")
            for entry in matched_entries:
                console.print(
                    f" [bold cyan]{entry['key']}.[/bold cyan] "
                    f"{entry['label'].ljust(shortcut.MENU_LABEL_WIDTH)} {entry['exts']}"
                )
            console.print(" [bold white]B.[/bold white] Back")
            console.print(" [bold white]Q.[/bold white] Quit")
            console.print("\n[dim](Other choices are hidden based on detected file format)[/dim]")

            choice = get_char("\nSelect Option: ")
            if choice.lower() == 'b':
                break
            if choice.lower() == 'q':
                console.print()
                sys.exit(0)

            selected_entry = next((e for e in matched_entries if e["key"] == choice), None)
            if not selected_entry:
                console.print(" [dim]Invalid choice[/dim]")
                time.sleep(0.5)
                continue

            op = selected_entry["operation"]
            op_completed = False

            if op == "combine":
                op_completed = handle_combine(conv, valid_paths, console, get_char, get_choice, get_input)
            elif op == "split":
                op_completed = handle_split(conv, valid_paths, console, get_char, get_input)
            elif op == "resize":
                op_completed = handle_resize(conv, valid_paths, console, get_char, get_input)
            elif op == "convert":
                cat_id = selected_entry["category_id"]
                op_completed = handle_convert(
                    conv, cat_id, valid_paths, console, get_char, get_choice, get_input,
                    prompt_fps, prompt_bitrate, prompt_strip_metadata, check_and_prompt_md_pdf, time
                )
            elif op == "compress":
                op_completed = handle_compress(conv, valid_paths, console, get_char, get_input, time)
            elif op == "decompress":
                op_completed = handle_decompress(conv, valid_paths, console, get_char, get_input, flush_stdin, clean_paths)
            elif op == "ocr":
                op_completed = handle_ocr(conv, valid_paths, console, get_char, get_input, time)
            elif op == "stt":
                op_completed = handle_stt(conv, valid_paths, console, get_char, get_input, time)

            if op_completed:
                break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Exiting...[/bold yellow]")
        sys.exit(0)
