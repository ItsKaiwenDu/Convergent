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
import subprocess
import sys
import tty
import termios
import argparse
import concurrent.futures
import multiprocessing
import json
from pathlib import Path
from modules import pdf_manip, image, video, audio, doc, compress
from customs import shortcut

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()
except ImportError:
    class MockConsole:
        def print(self, *args, **kwargs):
            import re
            msg = " ".join(map(str, args))
            msg = re.sub(r"\[.*?\]", "", msg)
            if 'end' in kwargs:
                print(msg, end=kwargs['end'])
            else:
                print(msg)
        def rule(self, title):
            print(f"\n{'='*20} {title} {'='*20}")
    console = MockConsole()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_input(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""

def get_char(prompt):
    console.print(prompt, end="")
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    if ch == '\x03':
        raise KeyboardInterrupt
        
    console.print(ch)
    return ch

def clean_path(path_str):
    if not path_str:
        return ""
    import shlex
    # Remove internal newlines/tabs that might come from messy copy-pastes
    path_str = path_str.replace("\n", "").replace("\r", "").replace("\t", "").strip()
    
    try:
        # Handle shell-escaped paths and quoted paths
        # shlex.split correctly handles cases like 'History\ \&\ Practice.pdf'
        if "\\" in path_str or "'" in path_str or '"' in path_str:
            parts = shlex.split(path_str)
            if parts:
                return " ".join(parts).strip()
    except:
        pass
    
    # Fallback to manual stripping of quotes
    return path_str.strip("'").strip('"').strip()

def flush_stdin():
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except:
        pass

def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)

class Converter:
    def __init__(self):
        self.formats = {
            "HEIC": ["JPG", "PNG"],
            "MOV": ["MP4", "GIF", "AVI", "MP3"],
            "DOCX": ["PDF"],
            "PPTX": ["PDF"],
            "RTF": ["PDF"],
            "JPG": ["PNG", "WEBP", "PDF"],
            "PNG": ["JPG", "WEBP", "PDF"],
            "MP4": ["MOV", "GIF", "MP3"],
            "WAV": ["MP3", "M4A"],
            "M4A": ["MP3", "WAV"],
        }
        self.source_formats = sorted(list(self.formats.keys()))
        self.categories = {
            "2": {"name": "Image", "extensions": ["HEIC", "JPG", "PNG"]},
            "3": {"name": "Video", "extensions": ["MOV", "MP4"]},
            "4": {"name": "Audio", "extensions": ["WAV", "M4A"]},
            "5": {"name": "Document", "extensions": ["DOCX", "PPTX", "RTF"]},
        }

    def convert_heic(self, source, target_ext):
        return image.convert_heic(source, target_ext)

    def convert_video(self, source, target_ext, fps=None):
        return video.convert_video(source, target_ext, fps)

    def convert_audio(self, source, target_ext):
        return audio.convert_audio(source, target_ext)

    def convert_office(self, source, target_ext):
        return doc.convert_office(source, target_ext)

    def convert_image(self, source, target_ext):
        return image.convert_image(source, target_ext)

    def combine_pdfs(self, path):
        return pdf_manip.combine_pdfs(path)

    def get_pdf_page_count(self, path):
        return pdf_manip.get_pdf_page_count(path)

    def split_pdf(self, path):
        return pdf_manip.split_pdf(path)

    def compress(self, path, output_name, format_choice, password=None):
        return compress.compress(path, output_name, format_choice, password)

    def process_single_file(self, f, target_format, fps=None):
        source_fmt = f.suffix.lower()[1:].upper()
        
        # Check if this specific source format supports the target format
        if target_format not in self.formats.get(source_fmt, []):
            if source_fmt == target_format:
                return f.name, True, "Skipped (Same format)"
            return f.name, False, f"Target {target_format} not supported for {source_fmt}"

        success = False
        error = ""
        
        if source_fmt == "HEIC":
            success, error = self.convert_heic(f, target_format)
        elif source_fmt in ["MOV", "MP4"]:
            success, error = self.convert_video(f, target_format, fps=fps)
        elif source_fmt in ["WAV", "M4A", "MP3"]:
            success, error = self.convert_audio(f, target_format)
        elif source_fmt in ["DOCX", "PPTX", "RTF"]:
            success, error = self.convert_office(f, target_format)
        elif source_fmt in ["JPG", "PNG"]:
            success, error = self.convert_image(f, target_format)
            
        return f.name, success, error

    def process(self, source_formats, target_format, path, fps=None, jobs=None):
        path_obj = Path(os.path.expanduser(path))
        files = []
        
        source_fmts_upper = [fmt.upper() for fmt in source_formats]
        
        if path_obj.is_file():
            ext = path_obj.suffix.lower()[1:].upper()
            if ext in source_fmts_upper:
                files = [path_obj]
        elif path_obj.is_dir():
            for item in path_obj.iterdir():
                if item.is_file():
                    ext = item.suffix.lower()[1:].upper()
                    if ext in source_fmts_upper:
                        files.append(item)
        
        if not files:
            console.print(f"[bold red]No matching files found at {path}[/bold red]")
            return

        console.print(f"[bold cyan]Found {len(files)} files to convert...[/bold cyan]")
        
        if not jobs:
            jobs = multiprocessing.cpu_count()
            
        success_count = 0
        
        try:
            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"Converting to {target_format}...", total=len(files))
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
                    futures = {executor.submit(self.process_single_file, f, target_format, fps): f for f in files}
                    
                    for future in concurrent.futures.as_completed(futures):
                        name, success, error = future.result()
                        if success:
                            success_count += 1
                            if error != "Skipped (Same format)":
                                progress.console.print(f" [bold green]✓[/bold green] {name}")
                        else:
                            progress.console.print(f" [bold red]✗[/bold red] {name}: [dim]{error.strip()}[/dim]")
                        progress.update(task, advance=1)
        except ImportError:
            # Fallback for systems without rich
            for f in files:
                name, success, error = self.process_single_file(f, target_format, fps)
                if success:
                    success_count += 1
                    if error != "Skipped (Same format)":
                        console.print(f" > {name}... [bold green]DONE[/bold green]")
                else:
                    console.print(f" > {name}... [bold red]FAILED[/bold red]")
                    if error:
                        console.print(f"   [dim]{error.strip()}[/dim]")
        
        console.print(f"\n[bold green]Finished! Successfully converted {success_count} files.[/bold green]")

def main():
    conv = Converter()
    
    parser = argparse.ArgumentParser(description="Convergent: Local File Converter")
    parser.add_argument("--from", dest="from_fmt", help="Source format (e.g., JPG, MOV)")
    parser.add_argument("--to", dest="to_fmt", help="Target format (e.g., PNG, MP3)")
    parser.add_argument("--fps", help="Frames per second for GIF conversion (e.g., 30, 60)")
    parser.add_argument("--path", help="Path to file or directory")
    parser.add_argument("--jobs", "-j", type=int, help="Number of parallel jobs (default: CPU count)")
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
            
        conv.process([source_fmt], target_fmt, args.path, fps=args.fps, jobs=args.jobs)
        return

    while True:
        shortcuts = shortcut.load_shortcuts()
        
        clear_screen()
        console.rule("File Converter Machine")
        
        if shortcuts:
            console.print("\n[bold yellow]Your Shortcuts:[/bold yellow]")
            for sym, sc in shortcuts.items():
                console.print(f" [bold]{sym}[/bold]. {sc['title']}")

        console.print("\n[bold yellow]Select source format ('From'):[/bold yellow]")
        console.print(" 0. Combine: PDF")
        console.print(" 1. Split: PDF")
        for key in sorted(conv.categories.keys()):
            cat = conv.categories[key]
            exts_str = ", ".join(cat["extensions"])
            console.print(f" {key}. {cat['name']}: {exts_str}")
        console.print(" 6. Compress: File/Folder")
            
        console.print(" [bold white]A[/bold white]: Add Shortcut")
        if shortcuts:
            console.print(" [bold white]R[/bold white]: Remove Shortcut")
        console.print(" [bold white]Q[/bold white]: Quit")
        
        choice = get_char("\nPick a #: ")
        if choice.lower() == 'q':
            break
            
        if choice.lower() == 'a':
            console.print("\n\n[bold yellow]--- Add New Shortcut ---[/bold yellow]")
            console.print("Select source category:")
            category_keys = sorted(conv.categories.keys())
            for i, key in enumerate(category_keys, 1):
                cat = conv.categories[key]
                exts_str = ", ".join(cat["extensions"])
                console.print(f" [bold]{i}[/bold]. {cat['name']}: {exts_str}")
            console.print(" [bold white]C[/bold white]. Cancel")
            cat_choice = get_char("\nPick category #: ")
            
            if cat_choice.lower() == 'c':
                continue
            
            selected_cat_key = None
            try:
                idx = int(cat_choice) - 1
                if 0 <= idx < len(category_keys):
                    selected_cat_key = category_keys[idx]
            except ValueError:
                pass
                
            if not selected_cat_key:
                continue
                
            category = conv.categories[selected_cat_key]
            source_fmts = category["extensions"]
            available_targets = set()
            for fmt in source_fmts:
                available_targets.update(conv.formats.get(fmt, []))
            sorted_targets = sorted(list(available_targets))
            
            console.print(f"\n[bold yellow]Select target format ('To') for {category['name']}:[/bold yellow]")
            for i, fmt in enumerate(sorted_targets, 1):
                console.print(f" {i}. {fmt}")
                
            target_choice = get_char("\nPick target #: ")
            try:
                to_idx = int(target_choice) - 1
                if to_idx < 0 or to_idx >= len(sorted_targets):
                    raise ValueError
                target_fmt = sorted_targets[to_idx]
            except ValueError:
                continue
                
            console.print(f"\n[bold yellow]Do you want to fix a file/folder path for this shortcut? (y/n)[/bold yellow]")
            fix_path = get_char("Choice: ")
            fixed_path = ""
            if fix_path.lower() == 'y':
                flush_stdin()
                fixed_path = clean_path(get_input("\nEnter path: "))
                flush_stdin()
                
            flush_stdin()
            sym = get_input("\nInput a single symbol/key for this shortcut (e.g., 'S'): ").strip().upper()
            title = get_input("Input a label title (e.g., 'Quick JPG Convert'): ").strip()
            
            if sym and title:
                shortcuts[sym] = {
                    "title": title,
                    "category": selected_cat_key,
                    "target_fmt": target_fmt,
                    "fixed_path": fixed_path
                }
                shortcut.save_shortcuts(shortcuts)
                console.print(f"\n[bold green]Shortcut '{sym}' added successfully![/bold green]")
                get_char("\nPress any key to continue...")
            continue

        if choice.lower() == 'r' and shortcuts:
            console.print("\n\n[bold yellow]--- Remove Shortcut ---[/bold yellow]")
            console.print("Existing shortcuts:")
            for sym, sc in shortcuts.items():
                console.print(f" [bold]{sym}[/bold]. {sc['title']}")
            console.print(" [bold white]C[/bold white]. Cancel")
            
            sym_to_remove = get_input("\nEnter symbol to remove (or 'C' to cancel): ").strip().upper()
            
            if sym_to_remove == 'C' or not sym_to_remove:
                continue
                
            if sym_to_remove in shortcuts:
                title = shortcuts[sym_to_remove]['title']
                del shortcuts[sym_to_remove]
                shortcut.save_shortcuts(shortcuts)
                console.print(f"\n[bold green]Shortcut '{sym_to_remove}' ({title}) removed successfully![/bold green]")
                get_char("\nPress any key to continue...")
            else:
                console.print(f"\n[bold red]Shortcut '{sym_to_remove}' not found.[/bold red]")
                get_char("\nPress any key to continue...")
            continue
            
        if choice.upper() in shortcuts:
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
                fps_choice = get_char("\nPick a #: ")
                if fps_choice == '2':
                    fps = 30
                elif fps_choice == '3':
                    fps = 60
            
            if not path:
                console.print(f"\n[bold yellow]Executing Shortcut: {sc['title']}[/bold yellow]")
                console.print(f"[bold yellow]Enter file or folder path:[/bold yellow]")
                console.print("[dim](Tip: You can drag and drop a file or folder into this window)[/dim]")
                flush_stdin()
                path = clean_path(get_input("Path: "))
                flush_stdin()
                
            if path:
                conv.process(source_fmts, target_fmt, path, fps=fps)
                get_char("\nPress any key to continue...")
            continue
        
        if choice == '0':
            console.print(f"\n[bold yellow]Enter folder path containing PDFs:[/bold yellow]")
            flush_stdin()
            path = clean_path(get_input("Path: "))
            flush_stdin()
            if path:
                conv.combine_pdfs(path)
                get_char("\nPress any key to continue...")
            continue
            
        if choice == '1':
            console.print(f"\n[bold yellow]Enter PDF file path to split:[/bold yellow]")
            flush_stdin()
            path = clean_path(get_input("Path: "))
            flush_stdin()
            if path:
                conv.split_pdf(path)
                get_char("\nPress any key to continue...")
            continue
            
        if choice == '6':
            console.print(f"\n[bold yellow]Enter file or folder path to compress:[/bold yellow]")
            flush_stdin()
            path = clean_path(get_input("Path: "))
            flush_stdin()
            
            if not path:
                continue
                
            console.print(f"\n[bold yellow]Select target format:[/bold yellow]")
            console.print(" 1. ZIP")
            console.print(" 2. TAR.GZ")
            fmt_choice = get_char("\nPick a #: ")
            
            target_fmt = "ZIP" if fmt_choice == '1' else "TAR.GZ" if fmt_choice == '2' else None
            if not target_fmt:
                continue
                
            password = None
            if target_fmt == "ZIP":
                console.print(f"\n[bold yellow]Add password protection? (y/n):[/bold yellow]", end=" ")
                pwd_yn = get_char("")
                if pwd_yn.lower() == 'y':
                    password = get_input("\nEnter password: ")
            
            output_name = get_input(f"\nEnter name for archive (default: compressed.{target_fmt.lower()}): ")
            if not output_name:
                output_name = f"compressed.{target_fmt.lower()}"
                
            success, error = conv.compress(path, output_name, target_fmt, password)
            if success:
                console.print(f"\n[bold green]Successfully compressed into {output_name}[/bold green]")
            else:
                console.print(f"\n[bold red]FAILED to compress:[/bold red]")
                console.print(f"   [dim]{error.strip()}[/dim]")
            
            get_char("\nPress any key to continue...")
            continue
            
        if choice not in conv.categories:
            continue
            
        category = conv.categories[choice]
        source_fmts = category["extensions"]
        
        # Determine available targets for this category (union of targets)
        available_targets = set()
        for fmt in source_fmts:
            available_targets.update(conv.formats.get(fmt, []))
        
        sorted_targets = sorted(list(available_targets))
        
        console.print(f"\n[bold yellow]Select target format ('To') for {category['name']}:[/bold yellow]")
        for i, fmt in enumerate(sorted_targets, 1):
            console.print(f" {i}. {fmt}")
        console.print(" [bold white]B[/bold white]. Back")
        
        target_choice = get_char("\nPick a #: ")
        if target_choice.lower() == 'b':
            continue
            
        try:
            to_idx = int(target_choice) - 1
            if to_idx < 0 or to_idx >= len(sorted_targets):
                raise ValueError
            target_fmt = sorted_targets[to_idx]
        except ValueError:
            continue
            
        fps = None
        if target_fmt == "GIF":
            console.print("\n[bold yellow]Select FPS for GIF:[/bold yellow]")
            console.print(" 1. Original FPS")
            console.print(" 2. 30 FPS")
            console.print(" 3. 60 FPS")
            fps_choice = get_char("\nPick a #: ")
            if fps_choice == '2':
                fps = 30
            elif fps_choice == '3':
                fps = 60
            
        console.print(f"\n[bold yellow]Enter file or folder path:[/bold yellow]")
        console.print("[dim](Tip: You can drag and drop a file or folder into this window)[/dim]")
        flush_stdin()
        path = clean_path(get_input("Path: "))
        flush_stdin()
        
        if not path:
            continue
            
        conv.process(source_fmts, target_fmt, path, fps=fps)
        get_char("\nPress any key to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Exiting...[/bold yellow]")
        sys.exit(0)
