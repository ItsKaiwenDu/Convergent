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
from pathlib import Path
from modules import pdf_manip, image, video, audio, doc, compress, decompress, ntb
from customs import shortcut, file_process
from customs.file_process import prompt_move_files
from customs.run_command import run_command
from customs.console import console, get_input, get_char

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def clean_paths(path_str):
    if not path_str:
        return []
    import shlex
    path_str = path_str.replace("\n", "").replace("\r", "").replace("\t", "").strip()
    
    try:
        # Handle shell-escaped paths and quoted paths
        # shlex.split correctly handles cases like 'History\ \&\ Practice.pdf'
        # or multiple paths like '/path/1' '/path/2'
        if "\\" in path_str or "'" in path_str or '"' in path_str:
            parts = shlex.split(path_str)
            if parts:
                return [p.strip() for p in parts if p.strip()]
    except:
        pass
    
    # Fallback to manual stripping of quotes if shlex fails or no special chars
    return [path_str.strip("'").strip('"').strip()]

def flush_stdin():
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except:
        pass


class Converter:
    def __init__(self):
        self.formats = {
            "HEIC": ["JPG", "PNG", "TIFF", "BMP"],
            "MOV": ["MP4", "WEBM", "GIF", "AVI", "MP3", "WAV", "M4A", "FLAC"],
            "DOCX": ["PDF"],
            "PPTX": ["PDF"],
            "RTF": ["PDF"],
            "JPG": ["PNG", "WEBP", "PDF", "TIFF", "BMP"],
            "PNG": ["JPG", "WEBP", "PDF", "TIFF", "BMP"],
            "WEBP": ["JPG", "PNG", "PDF", "TIFF", "BMP"],
            "TIFF": ["JPG", "PNG", "WEBP", "PDF", "BMP"],
            "TIF": ["JPG", "PNG", "WEBP", "PDF", "BMP"],
            "BMP": ["JPG", "PNG", "WEBP", "PDF", "TIFF"],
            "MP4": ["MOV", "WEBM", "GIF", "MP3", "WAV", "M4A", "FLAC"],
            "WEBM": ["MOV", "MP4", "GIF", "AVI", "MP3", "WAV", "M4A", "FLAC"],
            "GIF": ["MOV", "MP4", "WEBM", "AVI"],
            "AVI": ["MOV", "MP4", "WEBM", "GIF", "MP3", "WAV", "M4A", "FLAC"],
            "WAV": ["MP3", "M4A", "FLAC"],
            "M4A": ["MP3", "WAV", "FLAC"],
            "MP3": ["WAV", "M4A", "FLAC"],
            "FLAC": ["MP3", "WAV", "M4A"],
            "PDF": ["JPG", "PNG", "TIFF", "BMP"],
            "ARW": ["JPG", "PNG", "WEBP", "PDF", "TIFF", "BMP"],
            "DNG": ["JPG", "PNG", "WEBP", "PDF", "TIFF", "BMP"],
            "SVG": ["JPG", "PNG", "WEBP", "PDF", "TIFF", "BMP"],
            "NTB": ["PDF"],
            "MD": ["PDF", "HTML", "TXT"],
        }
        self.source_formats = sorted(list(self.formats.keys()))
        self.categories = {
            "2": {"name": "Image", "extensions": ["HEIC", "JPG", "PNG", "WEBP", "TIFF", "TIF", "BMP", "ARW", "DNG", "SVG"]},
            "3": {"name": "Video", "extensions": ["MOV", "MP4", "WEBM", "GIF", "AVI"]},
            "4": {"name": "Audio", "extensions": ["WAV", "M4A", "MP3", "FLAC"]},
            "5": {"name": "Document", "extensions": ["DOCX", "PPTX", "RTF", "PDF", "NTB", "MD"]},
        }

    def convert_heic(self, source, target_ext):
        return image.convert_heic(source, target_ext)

    def convert_video(self, source, target_ext, fps=None, bitrate=None):
        return video.convert_video(source, target_ext, fps, bitrate)

    def convert_audio(self, source, target_ext, bitrate=None):
        return audio.convert_audio(source, target_ext, bitrate)

    def convert_office(self, source, target_ext):
        return doc.convert_office(source, target_ext)

    def convert_image(self, source, target_ext):
        return image.convert_image(source, target_ext)

    def convert_pdf(self, source, target_ext):
        return pdf_manip.convert_pdf_to_image(source, target_ext)

    def convert_ntb(self, source, target_ext):
        return ntb.convert_ntb(source, target_ext)

    def convert_markdown(self, source, target_ext, md_pdf_mode=None):
        return doc.convert_markdown(source, target_ext, md_pdf_mode)

    def combine_pdfs(self, paths):
        return pdf_manip.combine_pdfs(paths)

    def get_pdf_page_count(self, path):
        return pdf_manip.get_pdf_page_count(path)

    def split_pdf(self, path):
        return pdf_manip.split_pdf(path)

    def split_video(self, path):
        return video.split_video(path)

    def compress(self, paths, output_name, format_choice, password=None):
        return compress.compress(paths, output_name, format_choice, password)

    def decompress(self, path, output_dir=None):
        return decompress.decompress(path, output_dir)

    def process_single_file(self, f, target_format, fps=None, md_pdf_mode=None):
        return file_process.process_single_file(self, f, target_format, fps, md_pdf_mode=md_pdf_mode)

    def process(self, source_formats, target_format, paths, fps=None, bitrate=None, jobs=None, overwrite=False, skip=False, md_pdf_mode=None):
        return file_process.process(self, console, get_char, source_formats, target_format, paths, fps, bitrate, jobs, overwrite, skip, md_pdf_mode)

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
        md_choice = get_char("\nPick a #: ")
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
    parser.add_argument("--path", help="Path to file or directory")
    parser.add_argument("--jobs", "-j", type=int, help="Number of parallel jobs (default: CPU count)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files without prompting")
    parser.add_argument("--skip", action="store_true", help="Skip existing output files without prompting")
    args = parser.parse_args()

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
            
        # For CLI, we treat the path as a single path or split it if it looks like multiple
        paths = clean_paths(args.path)
        conv.process([source_fmt], target_fmt, paths, fps=args.fps, bitrate=args.bitrate, jobs=args.jobs, overwrite=args.overwrite, skip=args.skip, md_pdf_mode=args.md_pdf_mode)
        return

    while True:
        shortcuts = shortcut.load_shortcuts()
        
        clear_screen()
        console.rule("File Converter Machine")
        
        if shortcuts:
            console.print("\n[bold yellow]Your Shortcuts:[/bold yellow]")
            for sym, sc in shortcuts.items():
                console.print(f" [bold cyan]{sym}.[/bold cyan] {sc['title']}")

        console.print("\n[bold yellow]Select source format ('From'):[/bold yellow]")
        label_w = 14
        console.print(f" [bold cyan]0.[/bold cyan] {'Combine:'.ljust(label_w)} pdf")
        console.print(f" [bold cyan]1.[/bold cyan] {'Split:'.ljust(label_w)} pdf, mp4")
        for key in sorted(conv.categories.keys()):
            cat = conv.categories[key]
            exts_str = ", ".join(cat["extensions"]).lower()
            console.print(f" [bold cyan]{key}.[/bold cyan] {(cat['name'] + ':').ljust(label_w)} {exts_str}")
        console.print(f" [bold cyan]6.[/bold cyan] {'Compress:'.ljust(label_w)} zip, rar, 7z, tar.(gz/bz2/xz)")
        console.print(f" [bold cyan]7.[/bold cyan] {'Decompress:'.ljust(label_w)} zip, rar, 7z, tar.(gz/bz2/xz)")
            
        console.print(" [bold white]+.[/bold white] Add Shortcut")
        if shortcuts:
            console.print(" [bold white]-.[/bold white] Remove Shortcut")
            console.print(" [bold white]=.[/bold white] Edit Shortcut")
        console.print(" [bold white]Q.[/bold white] Quit")
        
        choice = get_char("\nPick a #: ")
        if choice.lower() == 'q':
            console.print()
            break
            
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
            sc = shortcuts[choice.upper()]
            category = conv.categories[sc["category"]]
            source_fmts = category["extensions"]
            target_fmt = sc["target_fmt"]
            path = sc.get("fixed_path", "")
            
            fps = None
            if target_fmt == "GIF":
                console.print("\n[bold yellow]Select FPS for GIF:[/bold yellow]")
                console.print(" 1. Original FPS")
                console.print(" 2. 30 FPS")
                console.print(" 3. 60 FPS")
                console.print(" [bold white]B[/bold white]. Back")
                fps_choice = get_char("\nPick a #: ")
                if fps_choice.lower() == 'b':
                    console.print()
                    continue
                elif fps_choice == '1':
                    console.print()
                    fps = None
                elif fps_choice == '2':
                    console.print()
                    fps = 30
                elif fps_choice == '3':
                    console.print()
                    fps = 60
                else:
                    console.print(" [dim]Invalid choice[/dim]")
                    time.sleep(0.5)
                    continue
            
            bitrate = None
            if target_fmt == "MP3":
                preselected_bitrate = sc.get("bitrate", "ask")
                if preselected_bitrate == "ask":
                    console.print("\n[bold yellow]Select Audio Bitrate for MP3:[/bold yellow]")
                    console.print(" 1. Default")
                    console.print(" 2. 128k")
                    console.print(" 3. 192k")
                    console.print(" 4. 320k")
                    console.print(" [bold white]B[/bold white]. Back")
                    bitrate_choice = get_char("\nPick a #: ")
                    if bitrate_choice.lower() == 'b':
                        console.print()
                        continue
                    elif bitrate_choice == '1':
                        console.print()
                        bitrate = None
                    elif bitrate_choice == '2':
                        console.print()
                        bitrate = "128k"
                    elif bitrate_choice == '3':
                        console.print()
                        bitrate = "192k"
                    elif bitrate_choice == '4':
                        console.print()
                        bitrate = "320k"
                    else:
                        console.print(" [dim]Invalid choice[/dim]")
                        time.sleep(0.5)
                        continue
                elif preselected_bitrate == "default":
                    bitrate = None
                else:
                    bitrate = preselected_bitrate
            
            if not path:
                console.print(f"\n[bold yellow]Executing Shortcut: {sc['title']}[/bold yellow]")
                console.print(f"[bold yellow]Enter file or folder path(s):[/bold yellow]")
                console.print("[dim](Tip: You can drag and drop multiple files or folders into this window)[/dim]")
                flush_stdin()
                paths = clean_paths(get_input("Path: "))
                flush_stdin()
            else:
                paths = clean_paths(path)
                
            if paths:
                md_pdf_mode = check_and_prompt_md_pdf(target_fmt, paths, console, get_char, time)
                if md_pdf_mode == "back":
                    continue
                converted = conv.process(source_fmts, target_fmt, paths, fps=fps, bitrate=bitrate, md_pdf_mode=md_pdf_mode)
                prompt_move_files(console, get_char, get_input, converted)
            continue
        
        elif choice == '0':
            console.print()
            console.print(f"\n[bold yellow]Enter folder path or multiple PDF files:[/bold yellow]")
            flush_stdin()
            paths = clean_paths(get_input("Path: "))
            flush_stdin()
            if paths:
                out_path = conv.combine_pdfs(paths)
                if out_path:
                    prompt_move_files(console, get_char, get_input, [out_path])
                else:
                    get_char("\nPress any key to continue...")
            continue
            
        elif choice == '1':
            console.print()
            console.print(f"\n[bold yellow]Enter file path(s) to split (PDF or MP4):[/bold yellow]")
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
                    else:
                        console.print(f"[bold red]Error: Unsupported file type '{p.suffix}' for {p.name}. Only PDF and MP4 are supported for splitting.[/bold red]")
                
                if split_dirs:
                    prompt_move_files(console, get_char, get_input, split_dirs)
                else:
                    get_char("\nPress any key to continue...")
            continue
            
        elif choice == '6':
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
            console.print(" 1. zip")
            console.print(" 2. tar.gz")
            console.print(" 3. tar.bz2")
            console.print(" 4. tar.xz")
            console.print(" 5. 7z")
            console.print(" 6. rar")
            console.print(" [bold white]B[/bold white]. Back")
            fmt_choice = get_char("\nPick a #: ")
            
            if fmt_choice.lower() == 'b':
                continue
                
            target_fmt = (
                "ZIP" if fmt_choice == '1' else
                "TAR.GZ" if fmt_choice == '2' else
                "TAR.BZ2" if fmt_choice == '3' else
                "TAR.XZ" if fmt_choice == '4' else
                "7Z" if fmt_choice == '5' else
                "RAR" if fmt_choice == '6' else
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
                prompt_move_files(console, get_char, get_input, [out_path])
            else:
                console.print(f"\n[bold red]FAILED to compress:[/bold red]")
                console.print(f"   [dim]{error.strip()}[/dim]")
                get_char("\nPress any key to continue...")
            continue
            
        elif choice == '7':
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
                prompt_move_files(console, get_char, get_input, decompressed_dirs)
            else:
                get_char("\nPress any key to continue...")
            continue
            
        elif choice in conv.categories:
            console.print()
            
            category = conv.categories[choice]
            source_fmts = category["extensions"]
            
            available_targets = set()
            for fmt in source_fmts:
                available_targets.update(conv.formats.get(fmt, []))
            
            sorted_targets = sorted(list(available_targets))
            
            console.print(f"\n[bold yellow]Select target format ('To') for {category['name']}:[/bold yellow]")
            for i, fmt in enumerate(sorted_targets, 1):
                console.print(f" {i}. {fmt.lower()}")
            console.print(" [bold white]B[/bold white]. Back")
            
            target_choice = get_char("\nPick a #: ")
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
                console.print("\n[bold yellow]Select FPS for GIF:[/bold yellow]")
                console.print(" 1. Original FPS")
                console.print(" 2. 30 FPS")
                console.print(" 3. 60 FPS")
                console.print(" [bold white]B[/bold white]. Back")
                fps_choice = get_char("\nPick a #: ")
                if fps_choice.lower() == 'b':
                    console.print()
                    continue
                elif fps_choice == '1':
                    console.print()
                    fps = None
                elif fps_choice == '2':
                    console.print()
                    fps = 30
                elif fps_choice == '3':
                    console.print()
                    fps = 60
                else:
                    console.print(" [dim]Invalid choice[/dim]")
                    time.sleep(0.5)
                    continue
                
            bitrate = None
            if target_fmt == "MP3":
                console.print("\n[bold yellow]Select Audio Bitrate for MP3:[/bold yellow]")
                console.print(" 1. Default")
                console.print(" 2. 128k")
                console.print(" 3. 192k")
                console.print(" 4. 320k")
                console.print(" [bold white]B[/bold white]. Back")
                bitrate_choice = get_char("\nPick a #: ")
                if bitrate_choice.lower() == 'b':
                    console.print()
                    continue
                elif bitrate_choice == '1':
                    console.print()
                    bitrate = None
                elif bitrate_choice == '2':
                    console.print()
                    bitrate = "128k"
                elif bitrate_choice == '3':
                    console.print()
                    bitrate = "192k"
                elif bitrate_choice == '4':
                    console.print()
                    bitrate = "320k"
                else:
                    console.print(" [dim]Invalid choice[/dim]")
                    time.sleep(0.5)
                    continue
                
            console.print(f"\n[bold yellow]Enter file or folder path(s):[/bold yellow]")
            console.print("[dim](Tip: You can drag and drop multiple files or folders into this window)[/dim]")
            flush_stdin()
            paths = clean_paths(get_input("Path: "))
            flush_stdin()
            
            if not paths:
                continue
                
            md_pdf_mode = check_and_prompt_md_pdf(target_fmt, paths, console, get_char, time)
            if md_pdf_mode == "back":
                continue
            converted = conv.process(source_fmts, target_fmt, paths, fps=fps, bitrate=bitrate, md_pdf_mode=md_pdf_mode)
            prompt_move_files(console, get_char, get_input, converted)

        else:
            console.print(" [dim]Invalid choice[/dim]")
            time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Exiting...[/bold yellow]")
        sys.exit(0)
