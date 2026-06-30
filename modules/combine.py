import os
import re
import subprocess
from pathlib import Path
from customs.console import console, get_input, get_char
from customs.run_command import run_command, send_to_trash

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

def combine_pdfs(paths):
    if isinstance(paths, str):
        paths = [paths]
    
    pdf_files = []
    
    if len(paths) == 1:
        path_obj = Path(os.path.expanduser(paths[0]))
        if path_obj.is_dir():
            pdf_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"])
            if not pdf_files:
                console.print("[bold red]No PDF files found in the directory.[/bold red]")
                return
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
                pdf_files.extend(sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]))
        
        if not pdf_files:
            console.print("[bold red]No PDF files found in the provided paths.[/bold red]")
            return
        base_dir = pdf_files[0].parent

    num_files = len(pdf_files)
    if num_files > 50:
        console.print(f"\n[bold yellow]Found {num_files} PDF files. Proceed? (y/n)[/bold yellow]")
        choice = get_char("   Choice: ")
        console.print()
        if choice.lower() != 'y':
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

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
        console.print(" [bold white]Q[/bold white].                Cancel")
        console.print(" [bold white]R[/bold white].                Reverse order")
        console.print(" [bold white]S[/bold white] [bold cyan]<num1> <num2>[/bold cyan].  Swap files")
        
        cmd_input = get_input("\nCommand: ").strip()
        if not cmd_input:
            # Empty enter: default to confirm
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

    # Proceed to merge using the updated list of files
    pdf_files = [item["path"] for item in pdf_details]

    output_name = get_input("\nEnter name for combined PDF (default: combined.pdf): ")
    if not output_name:
        output_name = "combined.pdf"
    if not output_name.endswith(".pdf"):
        output_name += ".pdf"
    output_path = base_dir / output_name
    send_to_trash(output_path)
    cmd = ["gs", "-dNOPAUSE", "-sDEVICE=pdfwrite", f"-sOUTPUTFILE={output_path}", "-dBATCH"] + [str(f) for f in pdf_files]
    success, error = run_command(cmd)
    if success:
        console.print(f"[bold green]Successfully combined into {output_name}[/bold green]")
        return output_path
    else:
        console.print(f"[bold red]FAILED to combine PDFs[/bold red]")
        if "command not found" in error:
            console.print("   [bold yellow]Error: 'ghostscript' is required for PDF operations.[/bold yellow]")
            console.print("   [dim]Install via: brew install ghostscript[/dim]")
        elif error:
            console.print(f"   [dim]{error.strip()}[/dim]")
        return None

def combine_videos(paths):
    if isinstance(paths, str):
        paths = [paths]
    
    video_files = []
    
    if len(paths) == 1:
        path_obj = Path(os.path.expanduser(paths[0]))
        if path_obj.is_dir():
            video_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".mp4"])
            if not video_files:
                console.print("[bold red]No MP4 files found in the directory.[/bold red]")
                return None
            base_dir = path_obj
        else:
            video_files = [path_obj]
            base_dir = path_obj.parent
    else:
        for p in paths:
            path_obj = Path(os.path.expanduser(p))
            if path_obj.is_file() and path_obj.suffix.lower() == ".mp4":
                video_files.append(path_obj)
            elif path_obj.is_dir():
                video_files.extend(sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".mp4"]))
        
        if not video_files:
            console.print("[bold red]No MP4 files found in the provided paths.[/bold red]")
            return None
        base_dir = video_files[0].parent

    num_files = len(video_files)
    if num_files > 50:
        console.print(f"\n[bold yellow]Found {num_files} MP4 files. Proceed? (y/n)[/bold yellow]")
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
        console.print("\n[bold yellow]Combine: MP4 Order Preview[/bold yellow]")
        for idx, item in enumerate(video_details, 1):
            duration_str = f"({format_seconds(item['duration'])})" if item['duration'] > 0 else "(unknown duration)"
            console.print(f" [bold cyan]{idx}.[/bold cyan] {item['path'].name} [dim]{duration_str}[/dim]")
        
        console.print("\n[bold yellow]Commands:[/bold yellow]")
        console.print(" [bold white]C[/bold white].                Confirm & Merge")
        console.print(" [bold white]M[/bold white] [bold cyan]<num> <pos>[/bold cyan].    Move file")
        console.print(" [bold white]Q[/bold white].                Cancel")
        console.print(" [bold white]R[/bold white].                Reverse order")
        console.print(" [bold white]S[/bold white] [bold cyan]<num1> <num2>[/bold cyan].  Swap files")
        
        cmd_input = get_input("\nCommand: ").strip()
        if not cmd_input:
            # Empty enter: default to confirm
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

    # Proceed to merge using the updated list of files
    video_files = [item["path"] for item in video_details]

    output_name = get_input("\nEnter name for combined MP4 (default: combined.mp4): ")
    if not output_name:
        output_name = "combined.mp4"
    if not output_name.endswith(".mp4"):
        output_name += ".mp4"
    output_path = base_dir / output_name
    send_to_trash(output_path)

    temp_txt_path = base_dir / "temp_ffmpeg_concat.txt"
    try:
        with open(temp_txt_path, "w", encoding="utf-8") as f:
            for vf in video_files:
                abs_path = str(vf.resolve())
                escaped_path = abs_path.replace("\\", "\\\\").replace("'", "\\'")
                f.write(f"file '{escaped_path}'\n")
    except Exception as e:
        console.print(f"[bold red]FAILED to create temporary file for combination: {e}[/bold red]")
        return None

    try:
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(temp_txt_path), "-c", "copy", "-y", "-loglevel", "error", str(output_path)]
        success, error = run_command(cmd)
    finally:
        if temp_txt_path.exists():
            try:
                temp_txt_path.unlink()
            except:
                pass

    if success:
        console.print(f"[bold green]Successfully combined into {output_name}[/bold green]")
        return output_path
    else:
        console.print(f"[bold red]FAILED to combine videos[/bold red]")
        if error:
            console.print(f"   [dim]{error.strip()}[/dim]")
        return None

def combine_audios(paths):
    if isinstance(paths, str):
        paths = [paths]
    
    audio_files = []
    
    if len(paths) == 1:
        path_obj = Path(os.path.expanduser(paths[0]))
        if path_obj.is_dir():
            audio_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"])
            if not audio_files:
                console.print("[bold red]No MP3 files found in the directory.[/bold red]")
                return None
            base_dir = path_obj
        else:
            audio_files = [path_obj]
            base_dir = path_obj.parent
    else:
        for p in paths:
            path_obj = Path(os.path.expanduser(p))
            if path_obj.is_file() and path_obj.suffix.lower() == ".mp3":
                audio_files.append(path_obj)
            elif path_obj.is_dir():
                audio_files.extend(sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"]))
        
        if not audio_files:
            console.print("[bold red]No MP3 files found in the provided paths.[/bold red]")
            return None
        base_dir = audio_files[0].parent

    num_files = len(audio_files)
    if num_files > 50:
        console.print(f"\n[bold yellow]Found {num_files} MP3 files. Proceed? (y/n)[/bold yellow]")
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
        console.print("\n[bold yellow]Combine: MP3 Order Preview[/bold yellow]")
        for idx, item in enumerate(audio_details, 1):
            duration_str = f"({format_seconds(item['duration'])})" if item['duration'] > 0 else "(unknown duration)"
            console.print(f" [bold cyan]{idx}.[/bold cyan] {item['path'].name} [dim]{duration_str}[/dim]")
        
        console.print("\n[bold yellow]Commands:[/bold yellow] [white]C[/white] (Confirm) | [white]M <n> <p>[/white] (Move) | [white]S <n1> <n2>[/white] (Swap) | [white]R[/white] (Reverse) | [white]Q[/white] (Cancel)")
        
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

    # Proceed to merge using the updated list of files
    audio_files = [item["path"] for item in audio_details]

    output_name = get_input("\nEnter name for combined MP3 (default: combined.mp3): ")
    if not output_name:
        output_name = "combined.mp3"
    if not output_name.endswith(".mp3"):
        output_name += ".mp3"
    output_path = base_dir / output_name
    send_to_trash(output_path)

    temp_txt_path = base_dir / "temp_ffmpeg_concat.txt"
    try:
        with open(temp_txt_path, "w", encoding="utf-8") as f:
            for af in audio_files:
                abs_path = str(af.resolve())
                escaped_path = abs_path.replace("\\", "\\\\").replace("'", "\\'")
                f.write(f"file '{escaped_path}'\n")
    except Exception as e:
        console.print(f"[bold red]FAILED to create temporary file for combination: {e}[/bold red]")
        return None

    try:
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(temp_txt_path), "-c", "copy", "-y", "-loglevel", "error", str(output_path)]
        success, error = run_command(cmd)
    finally:
        if temp_txt_path.exists():
            try:
                temp_txt_path.unlink()
            except:
                pass

    if success:
        console.print(f"[bold green]Successfully combined into {output_name}[/bold green]")
        return output_path
    else:
        console.print(f"[bold red]FAILED to combine audios[/bold red]")
        if error:
            console.print(f"   [dim]{error.strip()}[/dim]")
        return None

def combine_gifs(paths):
    import re
    if isinstance(paths, str):
        paths = [paths]
    
    gif_files = []
    
    if len(paths) == 1:
        path_obj = Path(os.path.expanduser(paths[0]))
        if path_obj.is_dir():
            gif_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".gif"])
            if not gif_files:
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
                gif_files.extend(sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".gif"]))
        
        if not gif_files:
            console.print("[bold red]No GIF files found in the provided paths.[/bold red]")
            return None
        base_dir = gif_files[0].parent

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
        
        console.print("\n[bold yellow]Commands:[/bold yellow] [white]C[/white] (Confirm) | [white]M <n> <p>[/white] (Move) | [white]S <n1> <n2>[/white] (Swap) | [white]R[/white] (Reverse) | [white]Q[/white] (Cancel)")
        
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

    # Proceed to merge using the updated list of files
    gif_files = [item["path"] for item in gif_details]

    output_name = get_input("\nEnter name for combined GIF (default: combined.gif): ")
    if not output_name:
        output_name = "combined.gif"
    if not output_name.endswith(".gif"):
        output_name += ".gif"
    output_path = base_dir / output_name
    send_to_trash(output_path)

    temp_txt_path = base_dir / "temp_ffmpeg_concat.txt"
    try:
        with open(temp_txt_path, "w", encoding="utf-8") as f:
            for gf in gif_files:
                abs_path = str(gf.resolve())
                escaped_path = abs_path.replace("\\", "\\\\").replace("'", "\\'")
                f.write(f"file '{escaped_path}'\n")
    except Exception as e:
        console.print(f"[bold red]FAILED to create temporary file for combination: {e}[/bold red]")
        return None

    try:
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(temp_txt_path), "-y", "-loglevel", "error", str(output_path)]
        success, error = run_command(cmd)
    finally:
        if temp_txt_path.exists():
            try:
                temp_txt_path.unlink()
            except:
                pass

    if success:
        console.print(f"[bold green]Successfully combined into {output_name}[/bold green]")
        return output_path
    else:
        console.print(f"[bold red]FAILED to combine GIFs[/bold red]")
        if error:
            console.print(f"   [dim]{error.strip()}[/dim]")
        return None
