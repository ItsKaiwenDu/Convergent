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
from pathlib import Path
from modules import pdf_manip, image, video, audio, doc

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
            "5": {"name": "Document", "extensions": ["DOCX", "PPTX"]},
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


    def process(self, source_formats, target_format, path, fps=None):
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
        
        success_count = 0
        for f in files:
            source_fmt = f.suffix.lower()[1:].upper()
            
            # Check if this specific source format supports the target format
            if target_format not in self.formats.get(source_fmt, []):
                # Special case: if target is the same as source, skip
                if source_fmt == target_format:
                    continue
                console.print(f" > {f.name}... [bold yellow]SKIPPED[/bold yellow] (Target {target_format} not supported for {source_fmt})")
                continue

            console.print(f" > {f.name}...", end=" ")
            
            success = False
            error = ""
            
            if source_fmt == "HEIC":
                success, error = self.convert_heic(f, target_format)
            elif source_fmt in ["MOV", "MP4"]:
                success, error = self.convert_video(f, target_format, fps=fps)
            elif source_fmt in ["WAV", "M4A", "MP3"]:
                success, error = self.convert_audio(f, target_format)
            elif source_fmt in ["DOCX", "PPTX"]:
                success, error = self.convert_office(f, target_format)
            elif source_fmt in ["JPG", "PNG"]:
                success, error = self.convert_image(f, target_format)
                
            if success:
                console.print("[bold green]DONE[/bold green]")
                success_count += 1
            else:
                console.print(f"[bold red]FAILED[/bold red]")
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
            
        conv.process([source_fmt], target_fmt, args.path, fps=args.fps)
        return

    while True:
        clear_screen()
        console.rule("File Converter Machine")
        
        console.print("\n[bold yellow]Select source format ('From'):[/bold yellow]")
        console.print(" 0. Combine: PDF")
        console.print(" 1. Split: PDF")
        for key in sorted(conv.categories.keys()):
            cat = conv.categories[key]
            exts_str = ", ".join(cat["extensions"])
            console.print(f" {key}. {cat['name']}: {exts_str}")
        console.print(" Q. Quit")
        
        choice = get_char("\nPick a #: ")
        if choice.lower() == 'q':
            break
        
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
        console.print(" B. Back")
        
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
