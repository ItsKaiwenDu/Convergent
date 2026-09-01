import os
import re
import uuid
import shutil
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

def parse_timestamp(ts):
    try:
        if isinstance(ts, (int, float)):
            return float(ts)
        ts_str = str(ts).strip()
        if ":" in ts_str:
            parts = ts_str.split(":")
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        return float(ts_str)
    except:
        return None

def parse_page_ranges(input_ranges, total_pages):
    """
    Parse page ranges from a string (e.g. '1-5, 6-10') or list of tuples/lists.
    Returns list of (start_page, end_page) tuples (1-indexed).
    """
    ranges = []
    if isinstance(input_ranges, str):
        parts = [p.strip() for p in input_ranges.split(',') if p.strip()]
    elif isinstance(input_ranges, (list, tuple)):
        parts = input_ranges
    else:
        return []

    for part in parts:
        if isinstance(part, (list, tuple)) and len(part) == 2:
            start, end = int(part[0]), int(part[1])
        elif isinstance(part, str) and '-' in part:
            s_str, e_str = part.split('-', 1)
            start, end = int(s_str.strip()), int(e_str.strip())
        elif isinstance(part, (int, str)) and str(part).isdigit():
            start = end = int(part)
        else:
            continue
        if 1 <= start <= total_pages and 1 <= end <= total_pages and start <= end:
            ranges.append((start, end))
    return ranges

def parse_time_ranges(input_ranges, duration):
    """
    Parse time ranges from a string (e.g. '0-10, 00:01:00-00:02:00') or list of tuples.
    Returns list of (start_sec, end_sec) floats.
    """
    ranges = []
    if isinstance(input_ranges, str):
        parts = [p.strip() for p in input_ranges.split(',') if p.strip()]
    elif isinstance(input_ranges, (list, tuple)):
        parts = input_ranges
    else:
        return []

    for part in parts:
        if isinstance(part, (list, tuple)) and len(part) == 2:
            start = parse_timestamp(part[0])
            end = parse_timestamp(part[1])
        elif isinstance(part, str) and '-' in part:
            s_str, e_str = part.split('-', 1)
            start = parse_timestamp(s_str.strip())
            end = parse_timestamp(e_str.strip())
        else:
            continue
        if start is not None and end is not None and start >= 0 and end <= duration and start < end:
            ranges.append((start, end))
    return ranges

def split_pdf(
    path,
    mode="pages",
    ranges=None,
    num_parts=None,
    output_dir=None,
    interactive=True,
    display_name=None,
):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".pdf":
        if interactive:
            console.print(f"[bold red]Error: Could not find PDF at: [white]{path}[/white][/bold red]")
        return None
    
    total_pages = get_pdf_page_count(str(path_obj))
    if total_pages == 0:
        if interactive:
            console.print("[bold red]Error: Could not determine PDF page count or file is empty.[/bold red]")
        return None

    chosen_mode = str(mode).lower() if mode else "pages"

    if interactive:
        name_to_show = display_name or path_obj.name
        console.print(f"\n[bold yellow]Split Options for '{name_to_show}' ({total_pages} pages):[/bold yellow]")
        console.print(" 1. Individual Pages (every page becomes its own PDF)")
        console.print(" 2. Custom Split (e.g., 1-5, 6-10...)")
        console.print(" 3. Split into N parts")
        console.print(" [bold white]B[/bold white]. Back")
        user_choice = get_char("\nSelect Option: ")
        console.print()
        if user_choice.lower() == 'b':
            return None
        chosen_mode = user_choice

    out_directory = Path(os.path.expanduser(str(output_dir))) if output_dir else (path_obj.parent / f"{path_obj.stem}_split")
    send_to_trash(out_directory)
    out_directory.mkdir(parents=True, exist_ok=True)

    if chosen_mode in ('1', 'pages', 'all', 'individual', 'auto'):
        if interactive and total_pages > 50:
            console.print(f"\n[bold yellow]Found {total_pages} pages to split. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None
        if interactive:
            console.print(f"[bold cyan]Splitting into {total_pages} individual pages...[/bold cyan]")
        output_pattern = out_directory / "page_%03d.pdf"
        cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(output_pattern), str(path_obj)]
        success, error = run_command(cmd)
        if success:
            if interactive:
                console.print(f"[bold green]Successfully split into {out_directory.name}/[/bold green]")
            return out_directory
        else:
            if interactive:
                console.print(f"[bold red]FAILED to split PDF[/bold red]")
            return None

    elif chosen_mode in ('2', 'ranges', 'range', 'custom'):
        if interactive:
            console.print(f"\n[bold yellow]Enter page ranges for each PDF separated by commas:[/bold yellow]")
            input_str = get_input("Page ranges: ")
            page_ranges = parse_page_ranges(input_str, total_pages)
            if not page_ranges:
                console.print("[bold red]Invalid page ranges provided.[/bold red]")
                return None
        else:
            page_ranges = parse_page_ranges(ranges, total_pages) if ranges else []
            if not page_ranges:
                return None

        any_success = False
        for idx, (start, end) in enumerate(page_ranges, 1):
            out_file = out_directory / f"part_{idx}_{start}-{end}.pdf"
            cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(out_file), f"-dFirstPage={start}", f"-dLastPage={end}", str(path_obj)]
            success, _ = run_command(cmd)
            if success:
                if interactive:
                    console.print(f" [bold green]✓[/bold green] Part {idx} (Pages {start}-{end}): [bold green]DONE[/bold green]")
                any_success = True
            else:
                if interactive:
                    console.print(f" [bold red]✗[/bold red] Part {idx} (Pages {start}-{end}): [bold red]FAILED[/bold red]")

        if any_success:
            if interactive:
                console.print(f"\n[bold green]Custom split finished! Files are in {out_directory.name}/[/bold green]")
            return out_directory
        return None

    elif chosen_mode in ('3', 'parts', 'n_parts', 'split_parts'):
        if interactive:
            num_str = get_input("Number of PDFs: ")
            try:
                parts_count = int(num_str)
                if parts_count < 1 or parts_count > total_pages:
                    raise ValueError
            except ValueError:
                console.print("[bold red]Invalid input.[/bold red]")
                return None
        else:
            try:
                parts_count = int(num_parts) if num_parts is not None else 2
                if parts_count < 1 or parts_count > total_pages:
                    parts_count = min(max(parts_count, 1), total_pages)
            except (ValueError, TypeError):
                parts_count = 2

        base_size = total_pages // parts_count
        remainder = total_pages % parts_count
        current_page = 1
        any_success = False
        for i in range(parts_count):
            count = base_size + (1 if i < remainder else 0)
            end_page = current_page + count - 1
            out_file = out_directory / f"part_{i+1}_{current_page}-{end_page}.pdf"
            cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(out_file), f"-dFirstPage={current_page}", f"-dLastPage={end_page}", str(path_obj)]
            success, _ = run_command(cmd)
            if success:
                if interactive:
                    console.print(f" [bold green]✓[/bold green] Part {i+1} (Pages {current_page}-{end_page}): [bold green]DONE[/bold green]")
                any_success = True
            else:
                if interactive:
                    console.print(f" [bold red]✗[/bold red] Part {i+1} (Pages {current_page}-{end_page}): [bold red]FAILED[/bold red]")
            current_page = end_page + 1

        if any_success:
            if interactive:
                console.print(f"\n[bold green]Split finished! Files are in {out_directory.name}/[/bold green]")
            return out_directory
        return None

    return None

def split_video(
    path,
    mode="interval",
    interval=None,
    ranges=None,
    num_parts=None,
    output_dir=None,
    interactive=True,
):
    path_obj = Path(os.path.expanduser(path)).resolve()
    video_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
    if not path_obj.is_file() or path_obj.suffix.lower() not in video_exts:
        if interactive:
            console.print(f"[bold red]Error: Could not find video file at: [white]{path}[/white][/bold red]")
        return None
    
    duration = get_media_duration(path_obj)
    if duration == 0:
        if interactive:
            console.print("[bold red]Error: Could not determine video duration or file is empty.[/bold red]")
        return None
    
    out_ext = path_obj.suffix.lower()
    chosen_mode = str(mode).lower() if mode else "interval"

    if interactive:
        console.print(f"\n[bold yellow]Split Options for '{path_obj.name}' ({format_seconds(duration)}):[/bold yellow]")
        console.print(" 1. Fixed Segments (e.g., every 60 seconds)")
        console.print(" 2. Custom Range (e.g., 00:00:00-00:01:00)")
        console.print(" 3. Split into N parts")
        console.print(" [bold white]B[/bold white]. Back")
        
        user_choice = get_char("\nSelect Option: ")
        console.print()
        if user_choice.lower() == 'b':
            return None
        chosen_mode = user_choice

    out_directory = Path(os.path.expanduser(str(output_dir))) if output_dir else (path_obj.parent / f"{path_obj.stem}_split")
    send_to_trash(out_directory)
    out_directory.mkdir(parents=True, exist_ok=True)
    
    if chosen_mode in ('1', 'interval', 'fixed', 'segments', 'auto'):
        if interactive:
            interval_str = get_input("Interval in seconds (e.g., 60): ")
            try:
                split_interval = float(interval_str)
                if split_interval <= 0:
                    raise ValueError
            except ValueError:
                console.print("[bold red]Invalid interval.[/bold red]")
                return None
        else:
            try:
                split_interval = float(interval) if interval is not None else 60.0
                if split_interval <= 0:
                    split_interval = 60.0
            except (ValueError, TypeError):
                split_interval = 60.0
        
        num_segments = int(duration // split_interval) + (1 if duration % split_interval > 0 else 0)
        
        if interactive and num_segments > 50:
            console.print(f"\n[bold yellow]Found {num_segments} segments to create. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        if interactive:
            console.print(f"[bold cyan]Splitting into segments of {split_interval}s...[/bold cyan]")
        
        any_success = False
        for i in range(num_segments):
            start = i * split_interval
            out_file = out_directory / f"part_{i+1:03d}{out_ext}"
            cmd = ["ffmpeg", "-ss", str(start), "-t", str(split_interval), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                if interactive:
                    console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                any_success = True
            else:
                if interactive:
                    console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
            
        if any_success:
            if interactive:
                console.print(f"\n[bold green]Split finished! Files are in {out_directory.name}/[/bold green]")
            return out_directory
        return None

    elif chosen_mode in ('2', 'ranges', 'range', 'custom'):
        if interactive:
            console.print(f"\n[bold yellow]Enter time ranges separated by commas (e.g., 0-10, 00:01:00-00:02:00):[/bold yellow]")
            input_str = get_input("Ranges: ")
            time_ranges = parse_time_ranges(input_str, duration)
            if not time_ranges:
                console.print("[bold red]Invalid time ranges provided.[/bold red]")
                return None
        else:
            time_ranges = parse_time_ranges(ranges, duration) if ranges else []
            if not time_ranges:
                return None
            
        any_success = False
        for idx, (start, end) in enumerate(time_ranges, 1):
            out_file = out_directory / f"part_{idx}_{int(start)}-{int(end)}{out_ext}"
            cmd = ["ffmpeg", "-ss", str(start), "-to", str(end), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                if interactive:
                    console.print(f" [bold green]✓[/bold green] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold green]DONE[/bold green]")
                any_success = True
            else:
                if interactive:
                    console.print(f" [bold red]✗[/bold red] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold red]FAILED[/bold red]")
            
        if any_success:
            if interactive:
                console.print(f"\n[bold green]Custom split finished! Files are in {out_directory.name}/[/bold green]")
            return out_directory
        return None

    elif chosen_mode in ('3', 'parts', 'n_parts', 'split_parts'):
        if interactive:
            num_str = get_input("Number of parts: ")
            try:
                parts_count = int(num_str)
                if parts_count < 1:
                    raise ValueError
            except ValueError:
                console.print("[bold red]Invalid input.[/bold red]")
                return None
        else:
            try:
                parts_count = int(num_parts) if num_parts is not None else 2
                if parts_count < 1:
                    parts_count = 2
            except (ValueError, TypeError):
                parts_count = 2
            
        split_interval = duration / parts_count
        if interactive and parts_count > 50:
            console.print(f"\n[bold yellow]Found {parts_count} parts to create. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        if interactive:
            console.print(f"[bold cyan]Splitting into {parts_count} equal parts (~{split_interval:.2f}s each)...[/bold cyan]")
        
        any_success = False
        for i in range(parts_count):
            start = i * split_interval
            out_file = out_directory / f"part_{i+1:03d}{out_ext}"
            cmd = ["ffmpeg", "-ss", str(start), "-t", str(split_interval), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                if interactive:
                    console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                any_success = True
            else:
                if interactive:
                    console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
            
        if any_success:
            if interactive:
                console.print(f"\n[bold green]Split finished! Files are in {out_directory.name}/[/bold green]")
            return out_directory
        return None

    return None

def split_audio(
    path,
    mode="interval",
    interval=None,
    ranges=None,
    num_parts=None,
    output_dir=None,
    interactive=True,
):
    path_obj = Path(os.path.expanduser(path)).resolve()
    audio_exts = {".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"}
    if not path_obj.is_file() or path_obj.suffix.lower() not in audio_exts:
        if interactive:
            console.print(f"[bold red]Error: Could not find audio file at: [white]{path}[/white][/bold red]")
        return None
    
    duration = get_media_duration(path_obj)
    if duration == 0:
        if interactive:
            console.print("[bold red]Error: Could not determine audio duration or file is empty.[/bold red]")
        return None
    
    out_ext = path_obj.suffix.lower()
    chosen_mode = str(mode).lower() if mode else "interval"

    if interactive:
        console.print(f"\n[bold yellow]Split Options for '{path_obj.name}' ({format_seconds(duration)}):[/bold yellow]")
        console.print(" 1. Fixed Segments (e.g., every 60 seconds)")
        console.print(" 2. Custom Range (e.g., 00:00:00-00:01:00)")
        console.print(" 3. Split into N parts")
        console.print(" [bold white]B[/bold white]. Back")
        
        user_choice = get_char("\nSelect Option: ")
        console.print()
        if user_choice.lower() == 'b':
            return None
        chosen_mode = user_choice
        
    out_directory = Path(os.path.expanduser(str(output_dir))) if output_dir else (path_obj.parent / f"{path_obj.stem}_split")
    send_to_trash(out_directory)
    out_directory.mkdir(parents=True, exist_ok=True)
    
    if chosen_mode in ('1', 'interval', 'fixed', 'segments', 'auto'):
        if interactive:
            interval_str = get_input("Interval in seconds (e.g., 60): ")
            try:
                split_interval = float(interval_str)
                if split_interval <= 0:
                    raise ValueError
            except ValueError:
                console.print("[bold red]Invalid interval.[/bold red]")
                return None
        else:
            try:
                split_interval = float(interval) if interval is not None else 60.0
                if split_interval <= 0:
                    split_interval = 60.0
            except (ValueError, TypeError):
                split_interval = 60.0
        
        num_segments = int(duration // split_interval) + (1 if duration % split_interval > 0 else 0)
        
        if interactive and num_segments > 50:
            console.print(f"\n[bold yellow]Found {num_segments} segments to create. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        if interactive:
            console.print(f"[bold cyan]Splitting into segments of {split_interval}s...[/bold cyan]")
        
        any_success = False
        for i in range(num_segments):
            start = i * split_interval
            out_file = out_directory / f"part_{i+1:03d}{out_ext}"
            cmd = ["ffmpeg", "-ss", str(start), "-t", str(split_interval), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                if interactive:
                    console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                any_success = True
            else:
                if interactive:
                    console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
            
        if any_success:
            if interactive:
                console.print(f"\n[bold green]Split finished! Files are in {out_directory.name}/[/bold green]")
            return out_directory
        return None

    elif chosen_mode in ('2', 'ranges', 'range', 'custom'):
        if interactive:
            console.print(f"\n[bold yellow]Enter time ranges separated by commas (e.g., 0-10, 00:01:00-00:02:00):[/bold yellow]")
            input_str = get_input("Ranges: ")
            time_ranges = parse_time_ranges(input_str, duration)
            if not time_ranges:
                console.print("[bold red]Invalid time ranges provided.[/bold red]")
                return None
        else:
            time_ranges = parse_time_ranges(ranges, duration) if ranges else []
            if not time_ranges:
                return None
            
        any_success = False
        for idx, (start, end) in enumerate(time_ranges, 1):
            out_file = out_directory / f"part_{idx}_{int(start)}-{int(end)}{out_ext}"
            cmd = ["ffmpeg", "-ss", str(start), "-to", str(end), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                if interactive:
                    console.print(f" [bold green]✓[/bold green] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold green]DONE[/bold green]")
                any_success = True
            else:
                if interactive:
                    console.print(f" [bold red]✗[/bold red] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold red]FAILED[/bold red]")
            
        if any_success:
            if interactive:
                console.print(f"\n[bold green]Custom split finished! Files are in {out_directory.name}/[/bold green]")
            return out_directory
        return None

    elif chosen_mode in ('3', 'parts', 'n_parts', 'split_parts'):
        if interactive:
            num_str = get_input("Number of parts: ")
            try:
                parts_count = int(num_str)
                if parts_count < 1:
                    raise ValueError
            except ValueError:
                console.print("[bold red]Invalid input.[/bold red]")
                return None
        else:
            try:
                parts_count = int(num_parts) if num_parts is not None else 2
                if parts_count < 1:
                    parts_count = 2
            except (ValueError, TypeError):
                parts_count = 2
            
        split_interval = duration / parts_count
        if interactive and parts_count > 50:
            console.print(f"\n[bold yellow]Found {parts_count} parts to create. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        if interactive:
            console.print(f"[bold cyan]Splitting into {parts_count} equal parts (~{split_interval:.2f}s each)...[/bold cyan]")
        
        any_success = False
        for i in range(parts_count):
            start = i * split_interval
            out_file = out_directory / f"part_{i+1:03d}{out_ext}"
            cmd = ["ffmpeg", "-ss", str(start), "-t", str(split_interval), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                if interactive:
                    console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                any_success = True
            else:
                if interactive:
                    console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
            
        if any_success:
            if interactive:
                console.print(f"\n[bold green]Split finished! Files are in {out_directory.name}/[/bold green]")
            return out_directory
        return None

    return None

def split_gif(
    path,
    mode="frames",
    frame_format="png",
    interval=None,
    ranges=None,
    num_parts=None,
    output_dir=None,
    interactive=True,
):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".gif":
        if interactive:
            console.print(f"[bold red]Error: Could not find GIF at: [white]{path}[/white][/bold red]")
        return None
    
    duration = get_media_duration(path_obj)
    chosen_mode = str(mode).lower() if mode else "frames"

    if interactive:
        console.print(f"\n[bold yellow]Split Options for '{path_obj.name}':[/bold yellow]")
        console.print(" 1. Extract Frames (every frame becomes an individual image)")
        console.print(" 2. Split into GIF Segments (fixed intervals, custom ranges, or N parts)")
        console.print(" [bold white]B[/bold white]. Back")
        
        user_choice = get_char("\nSelect Option: ")
        console.print()
        if user_choice.lower() == 'b':
            return None
        if user_choice == '1':
            chosen_mode = "frames"
        elif user_choice == '2':
            chosen_mode = "segments_prompt"
        
    out_directory = Path(os.path.expanduser(str(output_dir))) if output_dir else (path_obj.parent / f"{path_obj.stem}_split")
    send_to_trash(out_directory)
    out_directory.mkdir(parents=True, exist_ok=True)
    
    if chosen_mode in ('1', 'frames', 'extract', 'images', 'auto'):
        fmt = frame_format.strip().lower() if frame_format else "png"
        if interactive:
            user_fmt = get_input("Format for frames (PNG/JPG, default: png): ").strip().lower()
            if user_fmt in ["png", "jpg"]:
                fmt = user_fmt
            
        if interactive:
            console.print(f"[bold cyan]Extracting frames to {fmt.upper()}...[/bold cyan]")
        out_pattern = out_directory / f"frame_%03d.{fmt}"
        cmd = ["ffmpeg", "-i", str(path_obj), "-y", "-loglevel", "error", str(out_pattern)]
        success, error = run_command(cmd)
        if success:
            if interactive:
                console.print(f"[bold green]Successfully extracted frames to {out_directory.name}/[/bold green]")
            return out_directory
        else:
            if interactive:
                console.print(f"[bold red]FAILED to extract frames[/bold red]")
                if error:
                    console.print(f"   [dim]{error.strip()}[/dim]")
            return None
            
    elif chosen_mode in ('2', 'segments_prompt', 'interval', 'ranges', 'parts'):
        if duration == 0:
            if interactive:
                console.print("[bold red]Error: Could not determine GIF duration or file is empty.[/bold red]")
            return None
            
        sub_mode = chosen_mode
        if interactive and chosen_mode == "segments_prompt":
            console.print(f"\n[bold yellow]GIF Segment Split Options ({format_seconds(duration)}):[/bold yellow]")
            console.print(" 1. Fixed Segments (e.g., every 5 seconds)")
            console.print(" 2. Custom Range (e.g., 00:00:00-00:01:00)")
            console.print(" 3. Split into N parts")
            console.print(" [bold white]B[/bold white]. Back")
            
            sub_choice = get_char("\nSelect Option: ")
            console.print()
            if sub_choice.lower() == 'b':
                return None
            sub_mode = sub_choice
            
        if sub_mode in ('1', 'interval', 'fixed', 'segments_prompt', 'segments'):
            if interactive:
                interval_str = get_input("Interval in seconds (e.g., 5): ")
                try:
                    split_interval = float(interval_str)
                    if split_interval <= 0:
                        raise ValueError
                except ValueError:
                    console.print("[bold red]Invalid interval.[/bold red]")
                    return None
            else:
                try:
                    split_interval = float(interval) if interval is not None else 5.0
                    if split_interval <= 0:
                        split_interval = 5.0
                except (ValueError, TypeError):
                    split_interval = 5.0
                
            num_segments = int(duration // split_interval) + (1 if duration % split_interval > 0 else 0)
            if interactive and num_segments > 50:
                console.print(f"\n[bold yellow]Found {num_segments} segments to create. Proceed? (y/n)[/bold yellow]")
                if get_char("   Choice: ").lower() != 'y':
                    console.print("[yellow]Operation cancelled.[/yellow]")
                    return None

            if interactive:
                console.print(f"[bold cyan]Splitting into segments of {split_interval}s...[/bold cyan]")
            any_success = False
            for i in range(num_segments):
                start = i * split_interval
                out_file = out_directory / f"part_{i+1:03d}.gif"
                cmd = ["ffmpeg", "-ss", str(start), "-t", str(split_interval), "-i", str(path_obj), "-y", "-loglevel", "error", str(out_file)]
                success, _ = run_command(cmd)
                if success:
                    if interactive:
                        console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                    any_success = True
                else:
                    if interactive:
                        console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
                    
            if any_success:
                if interactive:
                    console.print(f"\n[bold green]Split finished! Files are in {out_directory.name}/[/bold green]")
                return out_directory
            return None

        elif sub_mode in ('2', 'ranges', 'range', 'custom'):
            if interactive:
                console.print(f"\n[bold yellow]Enter time ranges separated by commas (e.g., 0-10, 00:01:00-00:02:00):[/bold yellow]")
                input_str = get_input("Ranges: ")
                time_ranges = parse_time_ranges(input_str, duration)
                if not time_ranges:
                    console.print("[bold red]Invalid time ranges provided.[/bold red]")
                    return None
            else:
                time_ranges = parse_time_ranges(ranges, duration) if ranges else []
                if not time_ranges:
                    return None
                    
            any_success = False
            for idx, (start, end) in enumerate(time_ranges, 1):
                out_file = out_directory / f"part_{idx}_{int(start)}-{int(end)}.gif"
                cmd = ["ffmpeg", "-ss", str(start), "-to", str(end), "-i", str(path_obj), "-y", "-loglevel", "error", str(out_file)]
                success, _ = run_command(cmd)
                if success:
                    if interactive:
                        console.print(f" [bold green]✓[/bold green] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold green]DONE[/bold green]")
                    any_success = True
                else:
                    if interactive:
                        console.print(f" [bold red]✗[/bold red] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold red]FAILED[/bold red]")
                    
            if any_success:
                if interactive:
                    console.print(f"\n[bold green]Custom split finished! Files are in {out_directory.name}/[/bold green]")
                return out_directory
            return None

        elif sub_mode in ('3', 'parts', 'n_parts', 'split_parts'):
            if interactive:
                num_str = get_input("Number of parts: ")
                try:
                    parts_count = int(num_str)
                    if parts_count < 1:
                        raise ValueError
                except ValueError:
                    console.print("[bold red]Invalid input.[/bold red]")
                    return None
            else:
                try:
                    parts_count = int(num_parts) if num_parts is not None else 2
                    if parts_count < 1:
                        parts_count = 2
                except (ValueError, TypeError):
                    parts_count = 2
                    
            split_interval = duration / parts_count
            if interactive and parts_count > 50:
                console.print(f"\n[bold yellow]Found {parts_count} parts to create. Proceed? (y/n)[/bold yellow]")
                if get_char("   Choice: ").lower() != 'y':
                    console.print("[yellow]Operation cancelled.[/yellow]")
                    return None

            if interactive:
                console.print(f"[bold cyan]Splitting into {parts_count} equal parts (~{split_interval:.2f}s each)...[/bold cyan]")
            any_success = False
            for i in range(parts_count):
                start = i * split_interval
                out_file = out_directory / f"part_{i+1:03d}.gif"
                cmd = ["ffmpeg", "-ss", str(start), "-t", str(split_interval), "-i", str(path_obj), "-y", "-loglevel", "error", str(out_file)]
                success, _ = run_command(cmd)
                if success:
                    if interactive:
                        console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                    any_success = True
                else:
                    if interactive:
                        console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
                    
            if any_success:
                if interactive:
                    console.print(f"\n[bold green]Split finished! Files are in {out_directory.name}/[/bold green]")
                return out_directory
            return None
                
    return None

def split_office(
    path,
    file_type,
    mode="pages",
    ranges=None,
    num_parts=None,
    output_dir=None,
    interactive=True,
):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != f".{file_type}":
        if interactive:
            console.print(f"[bold red]Error: Could not find {file_type.upper()} at: [white]{path}[/white][/bold red]")
        return None
        
    from modules.doc import convert_office
    
    workspace_dir = Path(__file__).parent.parent.resolve()
    tmp_dir = workspace_dir / ".convergent_tmp"
    tmp_dir.mkdir(exist_ok=True)
    
    unique_id = uuid.uuid4().hex
    temp_office = tmp_dir / f"split_{unique_id}.{file_type}"
    shutil.copy2(path_obj, temp_office)
    temp_pdf = tmp_dir / f"split_{unique_id}.pdf"
    
    try:
        if interactive:
            console.print(f"[dim]Converting {path_obj.name} to temporary PDF for splitting...[/dim]")
        success, err = convert_office(temp_office, "PDF")
        if not success:
            if interactive:
                console.print(f"[bold red]Failed to convert to PDF: {err}[/bold red]")
            return None
            
        expected_pdf = temp_office.with_suffix(".pdf")
        if expected_pdf.exists():
            if expected_pdf != temp_pdf:
                shutil.move(str(expected_pdf), str(temp_pdf))
                
        if not temp_pdf.exists():
            if interactive:
                console.print(f"[bold red]Failed to produce PDF for splitting.[/bold red]")
            return None
            
        target_output_dir = Path(os.path.expanduser(str(output_dir))) if output_dir else (path_obj.parent / f"{path_obj.stem}_split")
        
        return split_pdf(
            str(temp_pdf),
            mode=mode,
            ranges=ranges,
            num_parts=num_parts,
            output_dir=target_output_dir,
            interactive=interactive,
            display_name=path_obj.name,
        )
        
    finally:
        try:
            if temp_office.exists():
                temp_office.unlink()
        except:
            pass
        try:
            if temp_pdf.exists():
                temp_pdf.unlink()
        except:
            pass

def split_docx(path, mode="pages", ranges=None, num_parts=None, output_dir=None, interactive=True):
    return split_office(path, "docx", mode=mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=interactive)

def split_pptx(path, mode="pages", ranges=None, num_parts=None, output_dir=None, interactive=True):
    return split_office(path, "pptx", mode=mode, ranges=ranges, num_parts=num_parts, output_dir=output_dir, interactive=interactive)
