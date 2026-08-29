import os
import re
import uuid
import subprocess
from pathlib import Path
from customs.console import console, get_input, get_char
from customs.run_command import run_command, send_to_trash

def natural_sort_key(path):
    name = path.name if hasattr(path, "name") else str(path)
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', name)]

def get_pdf_page_count(path):
    try:
        result = subprocess.run(["mdls", "-name", "kMDItemNumberOfPages", "-raw", str(path)], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != "(null)":
            return int(result.stdout.strip())
        cmd = ["gs", "-q", "-dNODISPLAY", "-dNOSAFER", "-c", f"({path}) (r) file runpdfbegin pdfpagecount = quit"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return int(result.stdout.strip())
    except:
        pass
    return 0

def get_media_duration(path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except:
        pass
    return 0.0

def format_seconds(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"

def resolve_output_path(output_path, base_dir, default_filename):
    if output_path:
        out_p = Path(os.path.expanduser(str(output_path)))
        if out_p.is_dir() or str(output_path).endswith(os.sep) or str(output_path).endswith("/"):
            out_p = out_p / default_filename
        out_p.parent.mkdir(parents=True, exist_ok=True)
        return out_p
    return base_dir / default_filename

def combine_pdfs(paths, output_path=None, interactive=True):
    if isinstance(paths, str):
        paths = [paths]
    
    pdf_files = []
    
    if len(paths) == 1:
        path_obj = Path(os.path.expanduser(paths[0]))
        if path_obj.is_dir():
            pdf_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"], key=natural_sort_key)
            if not pdf_files:
                if interactive:
                    console.print("[bold red]No PDF files found in the directory.[/bold red]")
                return None
            base_dir = path_obj
        else:
            pdf_files = [path_obj]
            base_dir = path_obj.parent
    else:
        for p in paths:
            path_obj = Path(os.path.expanduser(p))
            if path_obj.is_file() and path_obj.suffix.lower() == ".pdf":
                pdf_files.append(path_obj)
            elif path_obj.is_dir():
                pdf_files.extend(sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"], key=natural_sort_key))
        
        if not pdf_files:
            if interactive:
                console.print("[bold red]No PDF files found in the provided paths.[/bold red]")
            return None
        base_dir = pdf_files[0].parent

    if interactive:
        num_files = len(pdf_files)
        if num_files > 50:
            console.print(f"\n[bold yellow]Found {num_files} PDF files. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        # Fetch page counts first
        console.print("[dim]Reading PDF metadata...[/dim]")
        pdf_details = []
        for f in pdf_files:
            pages = get_pdf_page_count(str(f))
            pdf_details.append({"path": f, "pages": pages})

        while True:
            console.print("\n[bold yellow]Combine: PDF Order Preview[/bold yellow]")
            for idx, item in enumerate(pdf_details, 1):
                pages_str = f"({item['pages']} pages)" if item['pages'] > 0 else "(unknown pages)"
                console.print(f" [bold cyan]{idx}.[/bold cyan] {item['path'].name} [dim]{pages_str}[/dim]")
            
            console.print("\n[bold yellow]Commands:[/bold yellow]")
            console.print(" [bold white]C[/bold white].                Confirm & Merge")
            console.print(" [bold white]M[/bold white] [bold cyan]<num> <pos>[/bold cyan].    Move file")
            console.print(" [bold white]R[/bold white].                Reverse order")
            console.print(" [bold white]S[/bold white] [bold cyan]<num1> <num2>[/bold cyan].  Swap files")
            console.print(" [bold white]Q[/bold white].                Cancel")
            
            cmd_input = get_input("\nCommand: ").strip()
            if not cmd_input:
                break
            
            cmd_lower = cmd_input.lower()
            if cmd_lower == 'c':
                break
            elif cmd_lower == 'q':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None
            elif cmd_lower == 'r':
                pdf_details.reverse()
                console.print("[bold green]✓ Reversed file order.[/bold green]")
            elif cmd_lower.startswith('s'):
                match = re.match(r'^s\s+(\d+)\s+(\d+)$', cmd_lower)
                if match:
                    idx1, idx2 = int(match.group(1)) - 1, int(match.group(2)) - 1
                    if 0 <= idx1 < len(pdf_details) and 0 <= idx2 < len(pdf_details):
                        pdf_details[idx1], pdf_details[idx2] = pdf_details[idx2], pdf_details[idx1]
                        console.print(f"[bold green]✓ Swapped file {idx1+1} and file {idx2+1}.[/bold green]")
                    else:
                        console.print("[bold red]Error: Number out of range.[/bold red]")
                else:
                    console.print("[bold red]Error: Swap command requires exactly two numbers (e.g., s 1 3).[/bold red]")
            elif cmd_lower.startswith('m'):
                match = re.match(r'^m\s+(\d+)\s+(\d+)$', cmd_lower)
                if match:
                    idx, target = int(match.group(1)) - 1, int(match.group(2)) - 1
                    if 0 <= idx < len(pdf_details) and 0 <= target < len(pdf_details):
                        item = pdf_details.pop(idx)
                        pdf_details.insert(target, item)
                        console.print(f"[bold green]✓ Moved file {idx+1} to position {target+1}.[/bold green]")
                    else:
                        console.print("[bold red]Error: Number out of range.[/bold red]")
                else:
                    console.print("[bold red]Error: Move command requires two numbers (e.g., m 4 1).[/bold red]")
            else:
                console.print("[bold red]Error: Unknown command.[/bold red]")

        pdf_files = [item["path"] for item in pdf_details]

        output_name = get_input("\nEnter name for combined PDF (default: combined.pdf): ").strip()
        if output_name:
            if not output_name.lower().endswith(".pdf"):
                output_name += ".pdf"
            dest_path = base_dir / output_name
        else:
            dest_path = resolve_output_path(output_path, base_dir, "combined.pdf")
    else:
        dest_path = resolve_output_path(output_path, base_dir, "combined.pdf")

    send_to_trash(dest_path)
    cmd = ["gs", "-dNOPAUSE", "-sDEVICE=pdfwrite", f"-sOUTPUTFILE={dest_path}", "-dBATCH"] + [str(f) for f in pdf_files]
    success, error = run_command(cmd)
    if success:
        if interactive:
            console.print(f"[bold green]Successfully combined into {dest_path.name}[/bold green]")
        return dest_path
    else:
        if interactive:
            console.print(f"[bold red]FAILED to combine PDFs[/bold red]")
            if "command not found" in error:
                console.print("   [bold yellow]Error: 'ghostscript' is required for PDF operations.[/bold yellow]")
                console.print("   [dim]Install via: brew install ghostscript[/dim]")
            elif error:
                console.print(f"   [dim]{error.strip()}[/dim]")
        return None

def combine_videos(paths, output_path=None, interactive=True):
    if isinstance(paths, str):
        paths = [paths]
    
    video_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
    video_files = []
    
    if len(paths) == 1:
        path_obj = Path(os.path.expanduser(paths[0]))
        if path_obj.is_dir():
            video_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() in video_exts], key=natural_sort_key)
            if not video_files:
                if interactive:
                    console.print("[bold red]No video files found in the directory.[/bold red]")
                return None
            base_dir = path_obj
        else:
            video_files = [path_obj]
            base_dir = path_obj.parent
    else:
        for p in paths:
            path_obj = Path(os.path.expanduser(p))
            if path_obj.is_file() and path_obj.suffix.lower() in video_exts:
                video_files.append(path_obj)
            elif path_obj.is_dir():
                video_files.extend(sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() in video_exts], key=natural_sort_key))
        
        if not video_files:
            if interactive:
                console.print("[bold red]No video files found in the provided paths.[/bold red]")
            return None
        base_dir = video_files[0].parent

    out_ext = video_files[0].suffix.lower() if video_files else ".mp4"

    if interactive:
        num_files = len(video_files)
        if num_files > 50:
            console.print(f"\n[bold yellow]Found {num_files} video files. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        # Fetch durations first
        console.print("[dim]Reading video metadata...[/dim]")
        video_details = []
        for f in video_files:
            duration = get_media_duration(str(f))
            video_details.append({"path": f, "duration": duration})

        while True:
            console.print(f"\n[bold yellow]Combine: Video Order Preview[/bold yellow]")
            for idx, item in enumerate(video_details, 1):
                duration_str = f"({format_seconds(item['duration'])})" if item['duration'] > 0 else "(unknown duration)"
                console.print(f" [bold cyan]{idx}.[/bold cyan] {item['path'].name} [dim]{duration_str}[/dim]")
            
            console.print("\n[bold yellow]Commands:[/bold yellow]")
            console.print(" [bold white]C[/bold white].                Confirm & Merge")
            console.print(" [bold white]M[/bold white] [bold cyan]<num> <pos>[/bold cyan].    Move file")
            console.print(" [bold white]R[/bold white].                Reverse order")
            console.print(" [bold white]S[/bold white] [bold cyan]<num1> <num2>[/bold cyan].  Swap files")
            console.print(" [bold white]Q[/bold white].                Cancel")
            
            cmd_input = get_input("\nCommand: ").strip()
            if not cmd_input:
                break
            
            cmd_lower = cmd_input.lower()
            if cmd_lower == 'c':
                break
            elif cmd_lower == 'q':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None
            elif cmd_lower == 'r':
                video_details.reverse()
                console.print("[bold green]✓ Reversed file order.[/bold green]")
            elif cmd_lower.startswith('s'):
                match = re.match(r'^s\s+(\d+)\s+(\d+)$', cmd_lower)
                if match:
                    idx1, idx2 = int(match.group(1)) - 1, int(match.group(2)) - 1
                    if 0 <= idx1 < len(video_details) and 0 <= idx2 < len(video_details):
                        video_details[idx1], video_details[idx2] = video_details[idx2], video_details[idx1]
                        console.print(f"[bold green]✓ Swapped file {idx1+1} and file {idx2+1}.[/bold green]")
                    else:
                        console.print("[bold red]Error: Number out of range.[/bold red]")
                else:
                    console.print("[bold red]Error: Swap command requires exactly two numbers (e.g., s 1 3).[/bold red]")
            elif cmd_lower.startswith('m'):
                match = re.match(r'^m\s+(\d+)\s+(\d+)$', cmd_lower)
                if match:
                    idx, target = int(match.group(1)) - 1, int(match.group(2)) - 1
                    if 0 <= idx < len(video_details) and 0 <= target < len(video_details):
                        item = video_details.pop(idx)
                        video_details.insert(target, item)
                        console.print(f"[bold green]✓ Moved file {idx+1} to position {target+1}.[/bold green]")
                    else:
                        console.print("[bold red]Error: Number out of range.[/bold red]")
                else:
                    console.print("[bold red]Error: Move command requires two numbers (e.g., m 4 1).[/bold red]")
            else:
                console.print("[bold red]Error: Unknown command.[/bold red]")

        video_files = [item["path"] for item in video_details]

        output_name = get_input(f"\nEnter name for combined video (default: combined{out_ext}): ").strip()
        if output_name:
            if not output_name.lower().endswith(out_ext):
                output_name += out_ext
            dest_path = base_dir / output_name
        else:
            dest_path = resolve_output_path(output_path, base_dir, f"combined{out_ext}")
    else:
        dest_path = resolve_output_path(output_path, base_dir, f"combined{out_ext}")

    send_to_trash(dest_path)

    temp_txt_path = base_dir / f"temp_ffmpeg_concat_{uuid.uuid4().hex[:8]}.txt"
    try:
        with open(temp_txt_path, "w", encoding="utf-8") as f:
            for vf in video_files:
                abs_path = str(vf.resolve())
                escaped_path = abs_path.replace("\\", "\\\\").replace("'", "\\'")
                f.write(f"file '{escaped_path}'\n")
    except Exception as e:
        if interactive:
            console.print(f"[bold red]FAILED to create temporary file for combination: {e}[/bold red]")
        return None

    try:
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(temp_txt_path), "-c", "copy", "-y", "-loglevel", "error", str(dest_path)]
        success, error = run_command(cmd)
    finally:
        if temp_txt_path.exists():
            try:
                temp_txt_path.unlink()
            except:
                pass

    if success:
        if interactive:
            console.print(f"[bold green]Successfully combined into {dest_path.name}[/bold green]")
        return dest_path
    else:
        if interactive:
            console.print(f"[bold red]FAILED to combine videos[/bold red]")
            if error:
                console.print(f"   [dim]{error.strip()}[/dim]")
        return None

def combine_audios(paths, output_path=None, interactive=True):
    if isinstance(paths, str):
        paths = [paths]
    
    audio_exts = {".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"}
    audio_files = []
    
    if len(paths) == 1:
        path_obj = Path(os.path.expanduser(paths[0]))
        if path_obj.is_dir():
            audio_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() in audio_exts], key=natural_sort_key)
            if not audio_files:
                if interactive:
                    console.print("[bold red]No audio files found in the directory.[/bold red]")
                return None
            base_dir = path_obj
        else:
            audio_files = [path_obj]
            base_dir = path_obj.parent
    else:
        for p in paths:
            path_obj = Path(os.path.expanduser(p))
            if path_obj.is_file() and path_obj.suffix.lower() in audio_exts:
                audio_files.append(path_obj)
            elif path_obj.is_dir():
                audio_files.extend(sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() in audio_exts], key=natural_sort_key))
        
        if not audio_files:
            if interactive:
                console.print("[bold red]No audio files found in the provided paths.[/bold red]")
            return None
        base_dir = audio_files[0].parent

    out_ext = audio_files[0].suffix.lower() if audio_files else ".mp3"

    if interactive:
        num_files = len(audio_files)
        if num_files > 50:
            console.print(f"\n[bold yellow]Found {num_files} audio files. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        # Fetch durations first
        console.print("[dim]Reading audio metadata...[/dim]")
        audio_details = []
        for f in audio_files:
            duration = get_media_duration(str(f))
            audio_details.append({"path": f, "duration": duration})

        while True:
            console.print(f"\n[bold yellow]Combine: Audio Order Preview[/bold yellow]")
            for idx, item in enumerate(audio_details, 1):
                duration_str = f"({format_seconds(item['duration'])})" if item['duration'] > 0 else "(unknown duration)"
                console.print(f" [bold cyan]{idx}.[/bold cyan] {item['path'].name} [dim]{duration_str}[/dim]")
            
            console.print("\n[bold yellow]Commands:[/bold yellow] [white]C[/white] (Confirm) | [white]M <n> <p>[/white] (Move) | [white]R[/white] (Reverse) | [white]S <n1> <n2>[/white] (Swap) | [white]Q[/white] (Cancel)")
            
            cmd_input = get_input("\nCommand: ").strip()
            if not cmd_input:
                break
            
            cmd_lower = cmd_input.lower()
            if cmd_lower == 'c':
                break
            elif cmd_lower == 'q':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None
            elif cmd_lower == 'r':
                audio_details.reverse()
                console.print("[bold green]✓ Reversed file order.[/bold green]")
            elif cmd_lower.startswith('s'):
                match = re.match(r'^s\s+(\d+)\s+(\d+)$', cmd_lower)
                if match:
                    idx1, idx2 = int(match.group(1)) - 1, int(match.group(2)) - 1
                    if 0 <= idx1 < len(audio_details) and 0 <= idx2 < len(audio_details):
                        audio_details[idx1], audio_details[idx2] = audio_details[idx2], audio_details[idx1]
                        console.print(f"[bold green]✓ Swapped file {idx1+1} and file {idx2+1}.[/bold green]")
                    else:
                        console.print("[bold red]Error: Number out of range.[/bold red]")
                else:
                    console.print("[bold red]Error: Swap command requires exactly two numbers (e.g., s 1 3).[/bold red]")
            elif cmd_lower.startswith('m'):
                match = re.match(r'^m\s+(\d+)\s+(\d+)$', cmd_lower)
                if match:
                    idx, target = int(match.group(1)) - 1, int(match.group(2)) - 1
                    if 0 <= idx < len(audio_details) and 0 <= target < len(audio_details):
                        item = audio_details.pop(idx)
                        audio_details.insert(target, item)
                        console.print(f"[bold green]✓ Moved file {idx+1} to position {target+1}.[/bold green]")
                    else:
                        console.print("[bold red]Error: Number out of range.[/bold red]")
                else:
                    console.print("[bold red]Error: Move command requires two numbers (e.g., m 4 1).[/bold red]")
            else:
                console.print("[bold red]Error: Unknown command.[/bold red]")

        audio_files = [item["path"] for item in audio_details]

        output_name = get_input(f"\nEnter name for combined audio (default: combined{out_ext}): ").strip()
        if output_name:
            if not output_name.lower().endswith(out_ext):
                output_name += out_ext
            dest_path = base_dir / output_name
        else:
            dest_path = resolve_output_path(output_path, base_dir, f"combined{out_ext}")
    else:
        dest_path = resolve_output_path(output_path, base_dir, f"combined{out_ext}")

    send_to_trash(dest_path)

    temp_txt_path = base_dir / f"temp_ffmpeg_concat_{uuid.uuid4().hex[:8]}.txt"
    try:
        with open(temp_txt_path, "w", encoding="utf-8") as f:
            for af in audio_files:
                abs_path = str(af.resolve())
                escaped_path = abs_path.replace("\\", "\\\\").replace("'", "\\'")
                f.write(f"file '{escaped_path}'\n")
    except Exception as e:
        if interactive:
            console.print(f"[bold red]FAILED to create temporary file for combination: {e}[/bold red]")
        return None

    try:
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(temp_txt_path), "-c", "copy", "-y", "-loglevel", "error", str(dest_path)]
        success, error = run_command(cmd)
    finally:
        if temp_txt_path.exists():
            try:
                temp_txt_path.unlink()
            except:
                pass

    if success:
        if interactive:
            console.print(f"[bold green]Successfully combined into {dest_path.name}[/bold green]")
        return dest_path
    else:
        if interactive:
            console.print(f"[bold red]FAILED to combine audios[/bold red]")
            if error:
                console.print(f"   [dim]{error.strip()}[/dim]")
        return None

def combine_gifs(paths, output_path=None, interactive=True):
    if isinstance(paths, str):
        paths = [paths]
    
    gif_files = []
    
    if len(paths) == 1:
        path_obj = Path(os.path.expanduser(paths[0]))
        if path_obj.is_dir():
            gif_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".gif"], key=natural_sort_key)
            if not gif_files:
                if interactive:
                    console.print("[bold red]No GIF files found in the directory.[/bold red]")
                return None
            base_dir = path_obj
        else:
            gif_files = [path_obj]
            base_dir = path_obj.parent
    else:
        for p in paths:
            path_obj = Path(os.path.expanduser(p))
            if path_obj.is_file() and path_obj.suffix.lower() == ".gif":
                gif_files.append(path_obj)
            elif path_obj.is_dir():
                gif_files.extend(sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".gif"], key=natural_sort_key))
        
        if not gif_files:
            if interactive:
                console.print("[bold red]No GIF files found in the provided paths.[/bold red]")
            return None
        base_dir = gif_files[0].parent

    if interactive:
        num_files = len(gif_files)
        if num_files > 50:
            console.print(f"\n[bold yellow]Found {num_files} GIF files. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        # Fetch durations first
        console.print("[dim]Reading GIF metadata...[/dim]")
        gif_details = []
        for f in gif_files:
            duration = get_media_duration(str(f))
            gif_details.append({"path": f, "duration": duration})

        while True:
            console.print("\n[bold yellow]Combine: GIF Order Preview[/bold yellow]")
            for idx, item in enumerate(gif_details, 1):
                duration_str = f"({format_seconds(item['duration'])})" if item['duration'] > 0 else "(unknown duration)"
                console.print(f" [bold cyan]{idx}.[/bold cyan] {item['path'].name} [dim]{duration_str}[/dim]")
            
            console.print("\n[bold yellow]Commands:[/bold yellow] [white]C[/white] (Confirm) | [white]M <n> <p>[/white] (Move) | [white]R[/white] (Reverse) | [white]S <n1> <n2>[/white] (Swap) | [white]Q[/white] (Cancel)")
            
            cmd_input = get_input("\nCommand: ").strip()
            if not cmd_input:
                break
            
            cmd_lower = cmd_input.lower()
            if cmd_lower == 'c':
                break
            elif cmd_lower == 'q':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None
            elif cmd_lower == 'r':
                gif_details.reverse()
                console.print("[bold green]✓ Reversed file order.[/bold green]")
            elif cmd_lower.startswith('s'):
                match = re.match(r'^s\s+(\d+)\s+(\d+)$', cmd_lower)
                if match:
                    idx1, idx2 = int(match.group(1)) - 1, int(match.group(2)) - 1
                    if 0 <= idx1 < len(gif_details) and 0 <= idx2 < len(gif_details):
                        gif_details[idx1], gif_details[idx2] = gif_details[idx2], gif_details[idx1]
                        console.print(f"[bold green]✓ Swapped file {idx1+1} and file {idx2+1}.[/bold green]")
                    else:
                        console.print("[bold red]Error: Number out of range.[/bold red]")
                else:
                    console.print("[bold red]Error: Swap command requires exactly two numbers (e.g., s 1 3).[/bold red]")
            elif cmd_lower.startswith('m'):
                match = re.match(r'^m\s+(\d+)\s+(\d+)$', cmd_lower)
                if match:
                    idx, target = int(match.group(1)) - 1, int(match.group(2)) - 1
                    if 0 <= idx < len(gif_details) and 0 <= target < len(gif_details):
                        item = gif_details.pop(idx)
                        gif_details.insert(target, item)
                        console.print(f"[bold green]✓ Moved file {idx+1} to position {target+1}.[/bold green]")
                    else:
                        console.print("[bold red]Error: Number out of range.[/bold red]")
                else:
                    console.print("[bold red]Error: Move command requires two numbers (e.g., m 4 1).[/bold red]")
            else:
                console.print("[bold red]Error: Unknown command.[/bold red]")

        gif_files = [item["path"] for item in gif_details]

        output_name = get_input("\nEnter name for combined GIF (default: combined.gif): ").strip()
        if output_name:
            if not output_name.lower().endswith(".gif"):
                output_name += ".gif"
            dest_path = base_dir / output_name
        else:
            dest_path = resolve_output_path(output_path, base_dir, "combined.gif")
    else:
        dest_path = resolve_output_path(output_path, base_dir, "combined.gif")

    send_to_trash(dest_path)

    temp_txt_path = base_dir / f"temp_ffmpeg_concat_{uuid.uuid4().hex[:8]}.txt"
    try:
        with open(temp_txt_path, "w", encoding="utf-8") as f:
            for gf in gif_files:
                abs_path = str(gf.resolve())
                escaped_path = abs_path.replace("\\", "\\\\").replace("'", "\\'")
                f.write(f"file '{escaped_path}'\n")
    except Exception as e:
        if interactive:
            console.print(f"[bold red]FAILED to create temporary file for combination: {e}[/bold red]")
        return None

    try:
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(temp_txt_path), "-y", "-loglevel", "error", str(dest_path)]
        success, error = run_command(cmd)
    finally:
        if temp_txt_path.exists():
            try:
                temp_txt_path.unlink()
            except:
                pass

    if success:
        if interactive:
            console.print(f"[bold green]Successfully combined into {dest_path.name}[/bold green]")
        return dest_path
    else:
        if interactive:
            console.print(f"[bold red]FAILED to combine GIFs[/bold red]")
            if error:
                console.print(f"   [dim]{error.strip()}[/dim]")
        return None

def combine_office(paths, file_type, output_path=None, interactive=True):
    import shutil
    
    if isinstance(paths, str):
        paths = [paths]
    
    office_files = []
    
    if len(paths) == 1:
        path_obj = Path(os.path.expanduser(paths[0]))
        if path_obj.is_dir():
            office_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == f".{file_type}"], key=natural_sort_key)
            if not office_files:
                if interactive:
                    console.print(f"[bold red]No {file_type.upper()} files found in the directory.[/bold red]")
                return None
            base_dir = path_obj
        else:
            office_files = [path_obj]
            base_dir = path_obj.parent
    else:
        for p in paths:
            path_obj = Path(os.path.expanduser(p))
            if path_obj.is_file() and path_obj.suffix.lower() == f".{file_type}":
                office_files.append(path_obj)
            elif path_obj.is_dir():
                office_files.extend(sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == f".{file_type}"], key=natural_sort_key))
        
        if not office_files:
            if interactive:
                console.print(f"[bold red]No {file_type.upper()} files found in the provided paths.[/bold red]")
            return None
        base_dir = office_files[0].parent

    if interactive:
        num_files = len(office_files)
        if num_files > 50:
            console.print(f"\n[bold yellow]Found {num_files} {file_type.upper()} files. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

    # Import convert_office
    from modules.doc import convert_office

    # Create workspace temp dir
    workspace_dir = Path(__file__).parent.parent.resolve()
    tmp_dir = workspace_dir / ".convergent_tmp"
    tmp_dir.mkdir(exist_ok=True)

    temp_files_to_clean = []
    pdf_details = []

    try:
        if interactive:
            console.print(f"[dim]Converting {file_type.upper()} files to temporary PDFs...[/dim]")
        
        for idx, f in enumerate(office_files, 1):
            unique_id = uuid.uuid4().hex
            temp_office = tmp_dir / f"combine_{unique_id}_{idx}.{file_type}"
            shutil.copy2(f, temp_office)
            temp_files_to_clean.append(temp_office)
            
            temp_pdf = tmp_dir / f"combine_{unique_id}_{idx}.pdf"
            success, err = convert_office(temp_office, "PDF")
            if not success:
                if interactive:
                    console.print(f"[bold red]Failed to convert {f.name} to PDF: {err}[/bold red]")
                return None
            
            expected_pdf = temp_office.with_suffix(".pdf")
            if expected_pdf.exists():
                if expected_pdf != temp_pdf:
                    shutil.move(str(expected_pdf), str(temp_pdf))
            
            if not temp_pdf.exists():
                if interactive:
                    console.print(f"[bold red]Failed to produce PDF for {f.name}[/bold red]")
                return None
                
            temp_files_to_clean.append(temp_pdf)
            
            pages = get_pdf_page_count(str(temp_pdf))
            pdf_details.append({
                "temp_pdf": temp_pdf,
                "original_name": f.name,
                "pages": pages
            })
            
        if interactive:
            # Preview & edit order loop
            while True:
                console.print(f"\n[bold yellow]Combine: {file_type.upper()} Order Preview (Output will be PDF)[/bold yellow]")
                for idx, item in enumerate(pdf_details, 1):
                    pages_str = f"({item['pages']} pages)" if item['pages'] > 0 else "(unknown pages)"
                    console.print(f" [bold cyan]{idx}.[/bold cyan] {item['original_name']} [dim]{pages_str}[/dim]")
                
                console.print("\n[bold yellow]Commands:[/bold yellow]")
                console.print(" [bold white]C[/bold white].                Confirm & Merge")
                console.print(" [bold white]M[/bold white] [bold cyan]<num> <pos>[/bold cyan].    Move file")
                console.print(" [bold white]R[/bold white].                Reverse order")
                console.print(" [bold white]S[/bold white] [bold cyan]<num1> <num2>[/bold cyan].  Swap files")
                console.print(" [bold white]Q[/bold white].                Cancel")
                
                cmd_input = get_input("\nCommand: ").strip()
                if not cmd_input:
                    break
                
                cmd_lower = cmd_input.lower()
                if cmd_lower == 'c':
                    break
                elif cmd_lower == 'q':
                    console.print("[yellow]Operation cancelled.[/yellow]")
                    return None
                elif cmd_lower == 'r':
                    pdf_details.reverse()
                    console.print("[bold green]✓ Reversed file order.[/bold green]")
                elif cmd_lower.startswith('s'):
                    match = re.match(r'^s\s+(\d+)\s+(\d+)$', cmd_lower)
                    if match:
                        idx1, idx2 = int(match.group(1)) - 1, int(match.group(2)) - 1
                        if 0 <= idx1 < len(pdf_details) and 0 <= idx2 < len(pdf_details):
                            pdf_details[idx1], pdf_details[idx2] = pdf_details[idx2], pdf_details[idx1]
                            console.print(f"[bold green]✓ Swapped file {idx1+1} and file {idx2+1}.[/bold green]")
                        else:
                            console.print("[bold red]Error: Number out of range.[/bold red]")
                    else:
                        console.print("[bold red]Error: Swap command requires exactly two numbers (e.g., s 1 3).[/bold red]")
                elif cmd_lower.startswith('m'):
                    match = re.match(r'^m\s+(\d+)\s+(\d+)$', cmd_lower)
                    if match:
                        idx, target = int(match.group(1)) - 1, int(match.group(2)) - 1
                        if 0 <= idx < len(pdf_details) and 0 <= target < len(pdf_details):
                            item = pdf_details.pop(idx)
                            pdf_details.insert(target, item)
                            console.print(f"[bold green]✓ Moved file {idx+1} to position {target+1}.[/bold green]")
                        else:
                            console.print("[bold red]Error: Number out of range.[/bold red]")
                    else:
                        console.print("[bold red]Error: Move command requires two numbers (e.g., m 4 1).[/bold red]")
                else:
                    console.print("[bold red]Error: Unknown command.[/bold red]")

            output_name = get_input("\nEnter name for combined PDF (default: combined.pdf): ").strip()
            if output_name:
                if not output_name.lower().endswith(".pdf"):
                    output_name += ".pdf"
                dest_path = base_dir / output_name
            else:
                dest_path = resolve_output_path(output_path, base_dir, "combined.pdf")
        else:
            dest_path = resolve_output_path(output_path, base_dir, "combined.pdf")

        send_to_trash(dest_path)
        
        pdf_files = [item["temp_pdf"] for item in pdf_details]
        cmd = ["gs", "-dNOPAUSE", "-sDEVICE=pdfwrite", f"-sOUTPUTFILE={dest_path}", "-dBATCH"] + [str(f) for f in pdf_files]
        success, error = run_command(cmd)
        if success:
            if interactive:
                console.print(f"[bold green]Successfully combined into {dest_path.name}[/bold green]")
            return dest_path
        else:
            if interactive:
                console.print(f"[bold red]FAILED to combine PDFs[/bold red]")
                if "command not found" in error:
                    console.print("   [bold yellow]Error: 'ghostscript' is required for PDF operations.[/bold yellow]")
                    console.print("   [dim]Install via: brew install ghostscript[/dim]")
                elif error:
                    console.print(f"   [dim]{error.strip()}[/dim]")
            return None

    finally:
        for temp_f in temp_files_to_clean:
            try:
                if temp_f.exists():
                    temp_f.unlink()
            except Exception:
                pass

def combine_docx(paths, output_path=None, interactive=True):
    return combine_office(paths, "docx", output_path=output_path, interactive=interactive)

def combine_pptx(paths, output_path=None, interactive=True):
    return combine_office(paths, "pptx", output_path=output_path, interactive=interactive)

def get_txt_line_count(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except:
        return 0

def combine_txt(paths, output_path=None, interactive=True):
    if isinstance(paths, str):
        paths = [paths]
    
    txt_files = []
    
    if len(paths) == 1:
        path_obj = Path(os.path.expanduser(paths[0]))
        if path_obj.is_dir():
            txt_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".txt"], key=natural_sort_key)
            if not txt_files:
                if interactive:
                    console.print("[bold red]No TXT files found in the directory.[/bold red]")
                return None
            base_dir = path_obj
        else:
            txt_files = [path_obj]
            base_dir = path_obj.parent
    else:
        for p in paths:
            path_obj = Path(os.path.expanduser(p))
            if path_obj.is_file() and path_obj.suffix.lower() == ".txt":
                txt_files.append(path_obj)
            elif path_obj.is_dir():
                txt_files.extend(sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".txt"], key=natural_sort_key))
        
        if not txt_files:
            if interactive:
                console.print("[bold red]No TXT files found in the provided paths.[/bold red]")
            return None
        base_dir = txt_files[0].parent

    if interactive:
        num_files = len(txt_files)
        if num_files > 50:
            console.print(f"\n[bold yellow]Found {num_files} TXT files. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        # Fetch line counts first
        console.print("[dim]Reading TXT metadata...[/dim]")
        txt_details = []
        for f in txt_files:
            lines = get_txt_line_count(str(f))
            txt_details.append({"path": f, "lines": lines})

        while True:
            console.print("\n[bold yellow]Combine: TXT Order Preview[/bold yellow]")
            for idx, item in enumerate(txt_details, 1):
                lines_str = f"({item['lines']} lines)" if item['lines'] > 0 else "(0 lines)"
                console.print(f" [bold cyan]{idx}.[/bold cyan] {item['path'].name} [dim]{lines_str}[/dim]")
            
            console.print("\n[bold yellow]Commands:[/bold yellow]")
            console.print(" [bold white]C[/bold white].                Confirm & Merge")
            console.print(" [bold white]M[/bold white] [bold cyan]<num> <pos>[/bold cyan].    Move file")
            console.print(" [bold white]R[/bold white].                Reverse order")
            console.print(" [bold white]S[/bold white] [bold cyan]<num1> <num2>[/bold cyan].  Swap files")
            console.print(" [bold white]Q[/bold white].                Cancel")
            
            cmd_input = get_input("\nCommand: ").strip()
            if not cmd_input:
                break
            
            cmd_lower = cmd_input.lower()
            if cmd_lower == 'c':
                break
            elif cmd_lower == 'q':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None
            elif cmd_lower == 'r':
                txt_details.reverse()
                console.print("[bold green]✓ Reversed file order.[/bold green]")
            elif cmd_lower.startswith('s'):
                match = re.match(r'^s\s+(\d+)\s+(\d+)$', cmd_lower)
                if match:
                    idx1, idx2 = int(match.group(1)) - 1, int(match.group(2)) - 1
                    if 0 <= idx1 < len(txt_details) and 0 <= idx2 < len(txt_details):
                        txt_details[idx1], txt_details[idx2] = txt_details[idx2], txt_details[idx1]
                        console.print(f"[bold green]✓ Swapped file {idx1+1} and file {idx2+1}.[/bold green]")
                    else:
                        console.print("[bold red]Error: Number out of range.[/bold red]")
                else:
                    console.print("[bold red]Error: Swap command requires exactly two numbers (e.g., s 1 3).[/bold red]")
            elif cmd_lower.startswith('m'):
                match = re.match(r'^m\s+(\d+)\s+(\d+)$', cmd_lower)
                if match:
                    idx, target = int(match.group(1)) - 1, int(match.group(2)) - 1
                    if 0 <= idx < len(txt_details) and 0 <= target < len(txt_details):
                        item = txt_details.pop(idx)
                        txt_details.insert(target, item)
                        console.print(f"[bold green]✓ Moved file {idx+1} to position {target+1}.[/bold green]")
                    else:
                        console.print("[bold red]Error: Number out of range.[/bold red]")
                else:
                    console.print("[bold red]Error: Move command requires two numbers (e.g., m 4 1).[/bold red]")
            else:
                console.print("[bold red]Error: Unknown command.[/bold red]")

        txt_files = [item["path"] for item in txt_details]

        output_name = get_input("\nEnter name for combined TXT (default: combined.txt): ").strip()
        if output_name:
            if not output_name.lower().endswith(".txt"):
                output_name += ".txt"
            dest_path = base_dir / output_name
        else:
            dest_path = resolve_output_path(output_path, base_dir, "combined.txt")
    else:
        dest_path = resolve_output_path(output_path, base_dir, "combined.txt")

    send_to_trash(dest_path)

    try:
        with open(dest_path, "w", encoding="utf-8") as outfile:
            for tf in txt_files:
                with open(tf, "r", encoding="utf-8", errors="ignore") as infile:
                    content = infile.read()
                    outfile.write(content)
                    if content and not content.endswith("\n"):
                        outfile.write("\n")
        if interactive:
            console.print(f"[bold green]Successfully combined into {dest_path.name}[/bold green]")
        return dest_path
    except Exception as e:
        if interactive:
            console.print(f"[bold red]FAILED to combine TXT files: {e}[/bold red]")
        return None
