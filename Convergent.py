#!/usr/bin/env python3
"""
Convergent: Private, Local File Converter Utility
-------------------------------------------
Owner: Kaiwen Du
License: Free to use

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

# Try to import rich for better UI, fallback to print if not available
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()
except ImportError:
    class MockConsole:
        def print(self, *args, **kwargs):
            # Strip rich-style tags if using fallback
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
    
    # Handle Ctrl+C (\x03) manually in raw mode
    if ch == '\x03':
        raise KeyboardInterrupt
        
    console.print(ch)
    return ch

def run_command(cmd):
    try:
        # We don't capture output for ffmpeg so the user can see progress if they want, 
        # but here we'll keep it quiet for a cleaner CLI.
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
            "WAV": ["MP3"],
            "M4A": ["MP3"],
        }
        self.source_formats = sorted(list(self.formats.keys()))

    def convert_heic(self, source, target_ext):
        # Using ImageMagick 'magick' command
        output = source.with_suffix(f".{target_ext.lower()}")
        return run_command(["magick", str(source), str(output)])

    def convert_video(self, source, target_ext):
        # Using ffmpeg
        output = source.with_suffix(f".{target_ext.lower()}")
        cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
        if target_ext.upper() == "MP4":
            cmd += ["-c:v", "libx264", "-c:a", "aac", "-strict", "experimental"]
        elif target_ext.upper() == "GIF":
            cmd += ["-vf", "fps=10,scale=480:-1:flags=lanczos"]
        elif target_ext.upper() == "MP3":
            cmd += ["-vn", "-acodec", "libmp3lame", "-q:a", "2"]
        
        cmd.append(str(output))
        return run_command(cmd)

    def convert_audio(self, source, target_ext):
        # Using ffmpeg
        output = source.with_suffix(f".{target_ext.lower()}")
        cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
        if target_ext.upper() == "MP3":
            cmd += ["-acodec", "libmp3lame", "-q:a", "2"]
        
        cmd.append(str(output))
        return run_command(cmd)

    def convert_office(self, source, target_ext):
        if target_ext.upper() == "PDF":
            # Try pandoc first
            output = source.with_suffix(".pdf")
            success, err = run_command(["pandoc", str(source), "-o", str(output)])
            if success: return True, ""
            
            return False, f"{source.suffix[1:].upper()} to PDF requires 'pandoc'.\nInstall via: brew install pandoc"
        return False, f"Unsupported target format: {target_ext}"

    def convert_image(self, source, target_ext):
        # Using ImageMagick
        output = source.with_suffix(f".{target_ext.lower()}")
        return run_command(["magick", str(source), str(output)])

    def process(self, source_format, target_format, path):
        path_obj = Path(os.path.expanduser(path))
        files = []
        
        if path_obj.is_file():
            if path_obj.suffix.lower() == f".{source_format.lower()}":
                files = [path_obj]
        elif path_obj.is_dir():
            # Truly case-insensitive search for all files in the directory
            for item in path_obj.iterdir():
                if item.is_file() and item.suffix.lower() == f".{source_format.lower()}":
                    files.append(item)
        
        if not files:
            console.print(f"[bold red]No {source_format} files found at {path}[/bold red]")
            return

        console.print(f"[bold cyan]Found {len(files)} files to convert...[/bold cyan]")
        
        success_count = 0
        for f in files:
            console.print(f" > {f.name}...", end=" ")
            
            success = False
            error = ""
            
            if source_format == "HEIC":
                success, error = self.convert_heic(f, target_format)
            elif source_format in ["MOV", "MP4"]:
                success, error = self.convert_video(f, target_format)
            elif source_format in ["WAV", "M4A"]:
                success, error = self.convert_audio(f, target_format)
            elif source_format in ["DOCX", "PPTX"]:
                success, error = self.convert_office(f, target_format)
            elif source_format in ["JPG", "PNG"]:
                success, error = self.convert_image(f, target_format)
                
            if success:
                console.print("[bold green]DONE[/bold green]")
                success_count += 1
            else:
                console.print(f"[bold red]FAILED[/bold red]")
                if error:
                    console.print(f"   [dim]{error.strip()}[/dim]")
        
        console.print(f"\n[bold green]Finished! Successfully converted {success_count}/{len(files)} files.[/bold green]")

def main():
    conv = Converter()
    
    parser = argparse.ArgumentParser(description="Convergent: Local File Converter")
    parser.add_argument("--from", dest="from_fmt", help="Source format (e.g., JPG, MOV)")
    parser.add_argument("--to", dest="to_fmt", help="Target format (e.g., PNG, MP3)")
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
            
        conv.process(source_fmt, target_fmt, args.path)
        return

    while True:
        clear_screen()
        console.rule("File Converter Machine")
        
        # Select FROM
        console.print("\n[bold yellow]Select source format ('From'):[/bold yellow]")
        for i, fmt in enumerate(conv.source_formats, 1):
            console.print(f" {i}. {fmt}")
        console.print(" Q. Quit")
        
        choice = get_char("\nPick a #: ")
        if choice.lower() == 'q':
            break
            
        try:
            from_idx = int(choice) - 1
            if from_idx < 0 or from_idx >= len(conv.source_formats):
                raise ValueError
            source_fmt = conv.source_formats[from_idx]
        except ValueError:
            continue
            
        # Select TO
        targets = conv.formats[source_fmt]
        console.print(f"\n[bold yellow]Select target format ('To') for {source_fmt}:[/bold yellow]")
        for i, fmt in enumerate(targets, 1):
            console.print(f" {i}. {fmt}")
        console.print(" B. Back")
        
        choice = get_char("\nPick a #: ")
        if choice.lower() == 'b':
            continue
            
        try:
            to_idx = int(choice) - 1
            if to_idx < 0 or to_idx >= len(targets):
                raise ValueError
            target_fmt = targets[to_idx]
        except ValueError:
            continue
            
        # Path input
        console.print(f"\n[bold yellow]Enter file or folder path:[/bold yellow]")
        console.print("[dim](Tip: You can drag and drop a file or folder into this window)[/dim]")
        path = get_input("Path: ").strip().strip("'").strip('"').strip() # Clean quotes and spaces
        
        if not path:
            continue
            
        conv.process(source_fmt, target_fmt, path)
        get_char("\nPress any key to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Exiting...[/bold yellow]")
        sys.exit(0)
