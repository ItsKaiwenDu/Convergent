#!/usr/bin/env python3
"""
Convergent: Private, Local File Converter Utility
-------------------------------------------
Owner: Kaiwen Du
License: Apache License 2.0

Copyright 2026 Kaiwen Du

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

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
from modules import pdf_manip, image, video, audio, doc, compress, decompress, ntb, combine, split, ocr
from customs import shortcut, file_process
from customs.file_process import prompt_move_files, FORMAT_REGISTRY, load_failed_run, clear_failed_run
from customs.run_command import run_command
from customs.console import console, get_input, get_char, get_choice, prompt_fps, prompt_bitrate, prompt_strip_metadata

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
    
    # If the entire path_str exists as a single file or directory, treat it as one path.
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
        return video.convert_video(source, target_ext, fps, bitrate)

    def convert_audio(self, source, target_ext, bitrate=None, **kwargs):
        return audio.convert_audio(source, target_ext, bitrate)

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
        return pdf_manip.convert_pdf_to_image(source, target_ext)

    def convert_ntb(self, source, target_ext, **kwargs):
        return ntb.convert_ntb(source, target_ext)

    def convert_markdown(self, source, target_ext, md_pdf_mode=None, **kwargs):
        return doc.convert_markdown(source, target_ext, md_pdf_mode)

    def combine_pdfs(self, paths):
        return combine.combine_pdfs(paths)

    def combine_videos(self, paths):
        return combine.combine_videos(paths)

    def combine_audios(self, paths):
        return combine.combine_audios(paths)

    def combine_gifs(self, paths):
        return combine.combine_gifs(paths)

    def combine_docx(self, paths):
        return combine.combine_docx(paths)

    def combine_pptx(self, paths):
        return combine.combine_pptx(paths)

    def combine_txt(self, paths):
        return combine.combine_txt(paths)

    def get_pdf_page_count(self, path):
        return combine.get_pdf_page_count(path)

    def split_pdf(self, path):
        return split.split_pdf(path)

    def split_video(self, path):
        return split.split_video(path)

    def split_audio(self, path):
        return split.split_audio(path)

    def split_gif(self, path):
        return split.split_gif(path)

    def split_docx(self, path):
        return split.split_docx(path)

    def split_pptx(self, path):
        return split.split_pptx(path)

    def compress(self, paths, output_name, format_choice, password=None):
        return compress.compress(paths, output_name, format_choice, password)

    def decompress(self, path, output_dir=None):
        return decompress.decompress(path, output_dir)

    def process_single_file(self, f, target_format, fps=None, md_pdf_mode=None, ocr=False):
        return file_process.process_single_file(self, f, target_format, fps, md_pdf_mode=md_pdf_mode, ocr=ocr)

    def process(self, source_formats, target_format, paths, fps=None, bitrate=None, jobs=None, overwrite=False, skip=False, md_pdf_mode=None, strip_metadata=False, interactive=True, ocr=False, success_map=None):
        return file_process.process(self, console, get_char, source_formats, target_format, paths, fps, bitrate, jobs, overwrite, skip, md_pdf_mode, strip_metadata, interactive, ocr=ocr, success_map=success_map)

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

def main():
    conv = Converter()
    
    parser = argparse.ArgumentParser(description="Convergent: Local File Converter")
    parser.add_argument("--from", dest="from_fmt", help="Source format (e.g., JPG, MOV)")
    parser.add_argument("--to", dest="to_fmt", help="Target format (e.g., PNG, MP3)")
    parser.add_argument("--fps", help="Frames per second for GIF conversion (e.g., 30, 60)")
    parser.add_argument("--bitrate", help="Audio bitrate for MP3 conversion (e.g., 128k, 192k, 320k)")
    parser.add_argument("--md-pdf-mode", choices=["formatted", "raw"], default="formatted", help="Rendering mode for Markdown to PDF (default: formatted)")
    parser.add_argument("--path", nargs="+", help="Path to file or directory")
    parser.add_argument("--jobs", "-j", type=int, help="Number of parallel jobs (default: CPU count)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files without prompting")
    parser.add_argument("--skip", action="store_true", help="Skip existing output files without prompting")
    parser.add_argument("--strip-metadata", action="store_true", help="Remove EXIF/IPTC/metadata from images for privacy")
    parser.add_argument("--resume", action="store_true", help="Resume / retry the last failed batch conversion")
    parser.add_argument("--shortcut", dest="shortcut_key", help="Run a saved shortcut by key symbol (requires --path unless shortcut has a fixed path)")
    parser.add_argument("--mcp", action="store_true", help="Launch local MCP (Model Context Protocol) server over stdio")
    args = parser.parse_args()

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
            console.print("[bold yellow]None of the failed files from the last run exist anymore.[/bold yellow]")
            clear_failed_run()
            sys.exit(0)
            
        source_fmts = failed_run["source_formats"]
        target_fmt = failed_run["target_format"]
        fps = failed_run.get("fps")
        bitrate = failed_run.get("bitrate")
        md_pdf_mode = failed_run.get("md_pdf_mode")
        strip_metadata = failed_run.get("strip_metadata", False)
        
        console.print(f"[bold cyan]Resuming last failed batch run: {len(existing_failed)} file(s)...[/bold cyan]")
        conv.process(source_fmts, target_fmt, existing_failed, fps=fps, bitrate=bitrate, jobs=args.jobs, overwrite=args.overwrite, skip=args.skip, md_pdf_mode=md_pdf_mode, strip_metadata=strip_metadata, interactive=False)
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
            cli_bitrate=args.bitrate,
            cli_strip_metadata=args.strip_metadata,
            prompt_fps=prompt_fps,
            prompt_bitrate=prompt_bitrate,
            prompt_strip_metadata=prompt_strip_metadata,
        )
        sys.exit(0 if ok else 1)

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
        conv.process([source_fmt], target_fmt, paths, fps=args.fps, bitrate=args.bitrate, jobs=args.jobs, overwrite=args.overwrite, skip=args.skip, md_pdf_mode=args.md_pdf_mode, strip_metadata=args.strip_metadata, interactive=False)
        return

    while True:
        shortcuts = shortcut.load_shortcuts()
        
        clear_screen()
        console.rule("File Converter Machine")
        
        if shortcuts:
            console.print("\n[bold yellow]Your Shortcuts:[/bold yellow]")
            for sym, sc in shortcuts.items():
                console.print(f" [bold cyan]{sym}.[/bold cyan] {sc['title']}")

        shortcut.print_source_menu(console, conv, "\n[bold yellow]Select source format ('From'):[/bold yellow]")
            
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
        
        choice = get_char("\nSelect Option: ")
        if choice.lower() == 'q':
            console.print()
            break
            
        elif choice.lower() == 'r' and failed_run and existing_failed:
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
            
        elif choice == '+':
            shortcut.add_shortcut(shortcuts, conv, console, get_char, get_input, flush_stdin, clean_paths)
            continue

        elif choice == '-' and shortcuts:
            shortcut.remove_shortcut(shortcuts, console, get_input, get_char)
            continue

        elif choice == '=' and shortcuts:
            shortcut.edit_shortcut(shortcuts, conv, console, get_char, get_input, clean_paths)
            continue
            
        elif choice.upper() in shortcuts:
            console.print()
            shortcut.run_shortcut(
                conv, console, get_char, get_input, flush_stdin, clean_paths,
                check_and_prompt_md_pdf, prompt_move_files,
                choice.upper(),
                interactive=True,
                prompt_fps=prompt_fps,
                prompt_bitrate=prompt_bitrate,
                prompt_strip_metadata=prompt_strip_metadata,
            )
            continue
        
        elif choice == '0':
            console.print()
            console.print(f"\n[bold yellow]Enter folder path or multiple PDF/MP4/MP3/GIF/DOCX/PPTX/TXT files:[/bold yellow]")
            console.print("[dim](Tip: You can either paste or drag and drop here)[/dim]")
            flush_stdin()
            paths = clean_paths(get_input("Path: "))
            flush_stdin()
            if paths:
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
                    try:
                        c_idx = int(c_choice) - 1
                        if 0 <= c_idx < len(available_types):
                            combine_type = available_types[c_idx][0]
                    except ValueError:
                        pass
                    if not combine_type:
                        continue
                elif len(available_types) == 1:
                    combine_type = available_types[0][0]
                else:
                    console.print("[bold red]No PDF, MP4, MP3, GIF, DOCX, PPTX, or TXT files found to combine.[/bold red]")
                    get_char("\nPress any key to continue...")
                    continue
                
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
                else:
                    get_char("\nPress any key to continue...")
            continue
            
        elif choice == '1':
            console.print()
            console.print(f"\n[bold yellow]Enter file path(s) to split (PDF, MP4, MP3, GIF, DOCX, or PPTX):[/bold yellow]")
            console.print("[dim](Tip: You can drag and drop multiple files into this window)[/dim]")
            flush_stdin()
            paths = clean_paths(get_input("Path: "))
            flush_stdin()
            if paths:
                split_dirs = []
                for path in paths:
                    p = Path(path)
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
                else:
                    get_char("\nPress any key to continue...")
            continue
            
        elif choice == '2':
            console.print()
            console.print(f"\n[bold yellow]Enter file or folder path(s) to resize:[/bold yellow]")
            console.print("[dim](Tip: You can either paste or drag and drop here)[/dim]")
            flush_stdin()
            paths = clean_paths(get_input("Path: "))
            flush_stdin()
            if paths:
                from modules import resize
                resize.resize_media(paths, conv, console, get_char, get_input)
            continue
            
        elif choice == '7':
            console.print()
            console.print(f"\n[bold yellow]Enter file or folder path(s) to compress:[/bold yellow]")
            flush_stdin()
            paths = clean_paths(get_input("Path: "))
            flush_stdin()
            
            if not paths:
                continue

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
                    continue
                
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
                continue
                
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
                continue
            
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
            else:
                console.print(f"\n[bold red]FAILED to compress:[/bold red]")
                console.print(f"   [dim]{error.strip()}[/dim]")
                get_char("\nPress any key to continue...")
            continue
            
        elif choice == '8':
            console.print()
            console.print(f"\n[bold yellow]Enter archive file path(s) to decompress:[/bold yellow]")
            flush_stdin()
            paths = clean_paths(get_input("Path: "))
            flush_stdin()
            
            if not paths:
                continue
                
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
                    continue

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
            else:
                get_char("\nPress any key to continue...")
            continue
            
        elif choice == '9':
            console.print()
            console.print(f"\n[bold yellow]Select target format for OCR text:[/bold yellow]")
            console.print(" 1. txt")
            console.print(" 2. md")
            console.print(" 3. docx")
            console.print(" 4. pdf")
            console.print(" [bold white]B[/bold white]. Back")
            fmt_choice = get_char("\nSelect Option: ")
            
            if fmt_choice.lower() == 'b':
                continue
            
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
                continue
                
            console.print()
            console.print(f"\n[bold yellow]Enter image or PDF file or folder path(s) for OCR (JPG/JPEG/PNG/HEIC/PDF):[/bold yellow]")
            console.print("[dim](Tip: You can either paste or drag and drop here)[/dim]")
            flush_stdin()
            paths = clean_paths(get_input("Path: "))
            flush_stdin()
            if paths:
                success_map = {}
                converted = conv.process(["JPG", "JPEG", "PNG", "HEIC", "PDF"], target_fmt, paths, ocr=True, success_map=success_map)
                prompt_move_files(console, get_char, get_input, converted, original_files=list(success_map.values()))
            continue
            
        elif choice in ["3", "4", "5", "6"]:
            console.print()
            
            cat_id = {"3": "2", "4": "3", "5": "4", "6": "5"}[choice]
            category = conv.categories[cat_id]
            source_fmts = category["extensions"]
            
            available_targets = set()
            for fmt in source_fmts:
                available_targets.update(conv.formats.get(fmt, []))
            
            sorted_targets = sorted(list(available_targets))
            
            console.print(f"\n[bold yellow]Select target format ('To') for {category['name']}:[/bold yellow]")
            for i, fmt in enumerate(sorted_targets, 1):
                console.print(f" {i}. {fmt.lower()}")
            console.print(" [bold white]B[/bold white]. Back")
            
            target_choice = get_choice("\nSelect Option: ", choices=sorted_targets)
            if target_choice.lower() == 'b':
                console.print()
                continue
                
            try:
                to_idx = int(target_choice) - 1
                if to_idx < 0 or to_idx >= len(sorted_targets):
                    raise ValueError
                target_fmt = sorted_targets[to_idx]
            except ValueError:
                console.print(" [dim]Invalid choice[/dim]")
                time.sleep(0.5)
                continue
            
            console.print()
                
            fps = None
            if target_fmt == "GIF":
                status, val = prompt_fps()
                if status in ("back", "invalid"):
                    continue
                fps = val
                
            bitrate = None
            if target_fmt == "MP3":
                status, val = prompt_bitrate()
                if status in ("back", "invalid"):
                    continue
                bitrate = val

            strip_metadata = False
            if cat_id == '2':
                status, val = prompt_strip_metadata()
                if status in ("back", "invalid"):
                    continue
                strip_metadata = val
                
            console.print(f"\n[bold yellow]Enter file or folder path(s):[/bold yellow]")
            console.print("[dim](Tip: You can either paste or drag and drop here)[/dim]")
            flush_stdin()
            paths = clean_paths(get_input("Path: "))
            flush_stdin()
            
            if not paths:
                continue
                
            md_pdf_mode = check_and_prompt_md_pdf(target_fmt, paths, console, get_char, time)
            if md_pdf_mode == "back":
                continue
            success_map = {}
            converted = conv.process(source_fmts, target_fmt, paths, fps=fps, bitrate=bitrate, md_pdf_mode=md_pdf_mode, strip_metadata=strip_metadata, success_map=success_map)
            prompt_move_files(console, get_char, get_input, converted, original_files=list(success_map.values()))

        else:
            console.print(" [dim]Invalid choice[/dim]")
            time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Exiting...[/bold yellow]")
        sys.exit(0)
