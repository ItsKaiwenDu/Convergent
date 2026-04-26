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
            "WAV": ["MP3"],
            "M4A": ["MP3"],
        }
        self.source_formats = sorted(list(self.formats.keys()))
        self.categories = {
            "2": {"name": "Image", "extensions": ["HEIC", "JPG", "PNG"]},
            "3": {"name": "Video", "extensions": ["MOV", "MP4", "WAV"]},
            "4": {"name": "Audio", "extensions": ["M4A"]},
            "5": {"name": "Document", "extensions": ["DOCX", "PPTX"]},
        }

    def convert_heic(self, source, target_ext):
        output = source.with_suffix(f".{target_ext.lower()}")
        return run_command(["magick", str(source), str(output)])

    def convert_video(self, source, target_ext, fps=None):
        output = source.with_suffix(f".{target_ext.lower()}")
        cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
        if target_ext.upper() == "MP4":
            cmd += ["-c:v", "libx264", "-c:a", "aac", "-strict", "experimental"]
        elif target_ext.upper() == "GIF":
            vf = "scale=480:-1:flags=lanczos"
            if fps:
                vf = f"fps={fps}," + vf
            cmd += ["-vf", vf]
        elif target_ext.upper() == "MP3":
            cmd += ["-vn", "-acodec", "libmp3lame", "-q:a", "2"]
        
        cmd.append(str(output))
        return run_command(cmd)

    def convert_audio(self, source, target_ext):
        output = source.with_suffix(f".{target_ext.lower()}")
        cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
        if target_ext.upper() == "MP3":
            cmd += ["-acodec", "libmp3lame", "-q:a", "2"]
        
        cmd.append(str(output))
        return run_command(cmd)

    def convert_office(self, source, target_ext):
        if target_ext.upper() == "PDF":
            output = source.with_suffix(".pdf")
            success, err = run_command(["pandoc", str(source), "-o", str(output)])
            if success: return True, ""
            
            return False, f"{source.suffix[1:].upper()} to PDF requires 'pandoc'.\nInstall via: brew install pandoc"
        return False, f"Unsupported target format: {target_ext}"

    def convert_image(self, source, target_ext):
        output = source.with_suffix(f".{target_ext.lower()}")
        return run_command(["magick", str(source), str(output)])

    def combine_pdfs(self, path):
        path_obj = Path(os.path.expanduser(path))
        if not path_obj.is_dir():
            console.print("[bold red]Error: PDF Combiner requires a directory path.[/bold red]")
            return
            
        pdf_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"])
        
        if not pdf_files:
            console.print("[bold red]No PDF files found in the directory.[/bold red]")
            return
            
        console.print(f"[bold cyan]Found {len(pdf_files)} PDF files to combine...[/bold cyan]")
        output_name = get_input("\nEnter name for combined PDF (default: combined.pdf): ")
        if not output_name:
            output_name = "combined.pdf"
        if not output_name.endswith(".pdf"):
            output_name += ".pdf"
            
        output_path = path_obj / output_name
        
        # Use ghostscript directly for high-quality PDF merging (no rasterization)
        cmd = [
            "gs", 
            "-dNOPAUSE", 
            "-sDEVICE=pdfwrite", 
            f"-sOUTPUTFILE={output_path}", 
            "-dBATCH"
        ] + [str(f) for f in pdf_files]
        
        success, error = run_command(cmd)
        
        if success:
            console.print(f"[bold green]Successfully combined into {output_name}[/bold green]")
        else:
            console.print(f"[bold red]FAILED to combine PDFs[/bold red]")
            if "command not found" in error:
                console.print("   [bold yellow]Error: 'ghostscript' is required for PDF operations.[/bold yellow]")
                console.print("   [dim]Install via: brew install ghostscript[/dim]")
            elif error:
                console.print(f"   [dim]{error.strip()}[/dim]")

    def get_pdf_page_count(self, path):
        try:
            # Try mdls first (macOS)
            result = subprocess.run(["mdls", "-name", "kMDItemNumberOfPages", "-raw", str(path)], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != "(null)":
                return int(result.stdout.strip())
            
            # Fallback to gs
            cmd = ["gs", "-q", "-dNODISPLAY", "-dNOSAFER", "-c", f"({path}) (r) file runpdfbegin pdfpagecount = quit"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return int(result.stdout.strip())
        except:
            pass
        return 0

    def split_pdf(self, path):
        path_obj = Path(os.path.expanduser(path)).resolve()
        if not path_obj.is_file() or path_obj.suffix.lower() != ".pdf":
            console.print("[bold red]Error: Split PDF requires a single PDF file.[/bold red]")
            return

        total_pages = self.get_pdf_page_count(str(path_obj))
        if total_pages == 0:
            console.print("[bold red]Error: Could not determine PDF page count or file is empty.[/bold red]")
            return

        console.print(f"\n[bold yellow]Split Options for '{path_obj.name}' ({total_pages} pages):[/bold yellow]")
        console.print(" 1. Individual Pages (every page becomes its own PDF)")
        console.print(" 2. Custom Split (e.g., 1, 4, 2, 3...)")
        
        mode = get_char("\nPick a #: ")
        
        # Create a directory for the split pages
        output_dir = path_obj.parent / f"{path_obj.stem}_split"
        try:
            output_dir.mkdir(exist_ok=True)
        except Exception as e:
            console.print(f"[bold red]Error creating directory: {e}[/bold red]")
            return

        if mode == '1':
            console.print(f"[bold cyan]Splitting into {total_pages} individual pages...[/bold cyan]")
            output_pattern = output_dir / "page_%03d.pdf"
            cmd = [
                "gs", 
                "-sDEVICE=pdfwrite", 
                "-o", str(output_pattern),
                str(path_obj)
            ]
            success, error = run_command(cmd)
            if success:
                console.print(f"[bold green]Successfully split into {output_dir.name}/[/bold green]")
            else:
                console.print(f"[bold red]FAILED to split PDF[/bold red]")
                if error: console.print(f"   [dim]{error.strip()}[/dim]")

        elif mode == '2':
            console.print(f"\n[bold yellow]Enter page counts for each PDF separated by commas:[/bold yellow]")
            console.print(f"[dim](Example: 1, 4, 2 will create 3 PDFs with 1, 4, and 2 pages, plus 1 PDF for the remaining pages)[/dim]")
            input_str = get_input("Page counts: ")
            try:
                page_counts = [int(x.strip()) for x in input_str.split(',') if x.strip()]
            except ValueError:
                console.print("[bold red]Invalid input. Please use numbers separated by commas.[/bold red]")
                return
            
            console.print(f"[bold cyan]Processing custom split...[/bold cyan]")
            current_page = 1
            idx = 1
            for count in page_counts:
                if current_page > total_pages:
                    break
                if count <= 0: continue
                
                end_page = min(current_page + count - 1, total_pages)
                out_file = output_dir / f"part_{idx}_{current_page}-{end_page}.pdf"
                
                cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(out_file), 
                       f"-dFirstPage={current_page}", f"-dLastPage={end_page}", str(path_obj)]
                success, error = run_command(cmd)
                if not success:
                    console.print(f" > Part {idx}: [bold red]FAILED[/bold red] [dim]{error.strip()}[/dim]")
                else:
                    console.print(f" > Part {idx} (Pages {current_page}-{end_page}): [bold green]DONE[/bold green]")
                
                current_page = end_page + 1
                idx += 1
            
            if current_page <= total_pages:
                out_file = output_dir / f"part_{idx}_{current_page}-{total_pages}_remainder.pdf"
                cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(out_file), 
                       f"-dFirstPage={current_page}", f"-dLastPage={total_pages}", str(path_obj)]
                success, error = run_command(cmd)
                if success:
                    console.print(f" > Part {idx} (Remainder, Pages {current_page}-{total_pages}): [bold green]DONE[/bold green]")
            
            console.print(f"\n[bold green]Custom split finished! Files are in {output_dir.name}/[/bold green]")
        else:
            console.print("[bold yellow]Operation cancelled.[/bold yellow]")

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
            elif source_fmt in ["WAV", "M4A"]:
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
            path = get_input("Path: ").strip().strip("'").strip('"').strip()
            if path:
                conv.combine_pdfs(path)
                get_char("\nPress any key to continue...")
            continue
            
        if choice == '1':
            console.print(f"\n[bold yellow]Enter PDF file path to split:[/bold yellow]")
            path = get_input("Path: ").strip().strip("'").strip('"').strip()
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
        path = get_input("Path: ").strip().strip("'").strip('"').strip()
        
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
