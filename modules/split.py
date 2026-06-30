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

def parse_timestamp(ts):
    try:
        if ":" in ts:
            parts = ts.split(":")
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        return float(ts)
    except:
        return None

def split_pdf(path):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".pdf":
        console.print(f"[bold red]Error: Could not find PDF at: [white]{path}[/white][/bold red]")
        return None
    total_pages = get_pdf_page_count(str(path_obj))
    if total_pages == 0:
        console.print("[bold red]Error: Could not determine PDF page count or file is empty.[/bold red]")
        return None
    console.print(f"\n[bold yellow]Split Options for '{path_obj.name}' ({total_pages} pages):[/bold yellow]")
    console.print(" 1. Individual Pages (every page becomes its own PDF)")
    console.print(" 2. Custom Split (e.g., 1-5, 6-10...)")
    console.print(" 3. Split into N parts")
    console.print(" [bold white]B[/bold white]. Back")
    mode = get_char("\nPick a #: ")
    console.print()
    if mode.lower() == 'b':
        return None
    output_dir = path_obj.parent / f"{path_obj.stem}_split"
    send_to_trash(output_dir)
    output_dir.mkdir(exist_ok=True)
    if mode == '1':
        if total_pages > 50:
            console.print(f"\n[bold yellow]Found {total_pages} pages to split. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None
        console.print(f"[bold cyan]Splitting into {total_pages} individual pages...[/bold cyan]")
        output_pattern = output_dir / "page_%03d.pdf"
        cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(output_pattern), str(path_obj)]
        success, error = run_command(cmd)
        if success:
            console.print(f"[bold green]Successfully split into {output_dir.name}/[/bold green]")
            return output_dir
        else:
            console.print(f"[bold red]FAILED to split PDF[/bold red]")
            return None
    elif mode == '2':
        console.print(f"\n[bold yellow]Enter page ranges for each PDF separated by commas:[/bold yellow]")
        input_str = get_input("Page ranges: ")
        ranges = []
        try:
            for part in input_str.split(','):
                part = part.strip()
                if not part: continue
                if '-' not in part: raise ValueError(f"'{part}' is not a valid range")
                start_str, end_str = part.split('-', 1)
                start, end = int(start_str.strip()), int(end_str.strip())
                if start < 1 or end > total_pages or start > end: raise ValueError(f"Range {start}-{end} invalid")
                ranges.append((start, end))
        except ValueError as e:
            console.print(f"[bold red]Invalid input: {e}[/bold red]")
            return None
        any_success = False
        for idx, (start, end) in enumerate(ranges, 1):
            out_file = output_dir / f"part_{idx}_{start}-{end}.pdf"
            cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(out_file), f"-dFirstPage={start}", f"-dLastPage={end}", str(path_obj)]
            success, _ = run_command(cmd)
            if success:
                console.print(f" [bold green]✓[/bold green] Part {idx} (Pages {start}-{end}): [bold green]DONE[/bold green]")
                any_success = True
            else: console.print(f" [bold red]✗[/bold red] Part {idx} (Pages {start}-{end}): [bold red]FAILED[/bold red]")
        console.print(f"\n[bold green]Custom split finished! Files are in {output_dir.name}/[/bold green]")
        return output_dir if any_success else None
    elif mode == '3':
        num_str = get_input("Number of PDFs: ")
        try:
            num_parts = int(num_str)
            if num_parts < 1 or num_parts > total_pages: raise ValueError
        except ValueError:
            console.print("[bold red]Invalid input.[/bold red]")
            return None
        base_size = total_pages // num_parts
        remainder = total_pages % num_parts
        current_page = 1
        any_success = False
        for i in range(num_parts):
            count = base_size + (1 if i < remainder else 0)
            end_page = current_page + count - 1
            out_file = output_dir / f"part_{i+1}_{current_page}-{end_page}.pdf"
            cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(out_file), f"-dFirstPage={current_page}", f"-dLastPage={end_page}", str(path_obj)]
            success, _ = run_command(cmd)
            if success:
                console.print(f" [bold green]✓[/bold green] Part {i+1} (Pages {current_page}-{end_page}): [bold green]DONE[/bold green]")
                any_success = True
            else: console.print(f" [bold red]✗[/bold red] Part {i+1} (Pages {current_page}-{end_page}): [bold red]FAILED[/bold red]")
            current_page = end_page + 1
        console.print(f"\n[bold green]Split finished! Files are in {output_dir.name}/[/bold green]")
        return output_dir if any_success else None

def split_video(path):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".mp4":
        console.print(f"[bold red]Error: Could not find MP4 at: [white]{path}[/white][/bold red]")
        return None
    
    duration = get_media_duration(path_obj)
    if duration == 0:
        console.print("[bold red]Error: Could not determine video duration or file is empty.[/bold red]")
        return None
    
    console.print(f"\n[bold yellow]Split Options for '{path_obj.name}' ({format_seconds(duration)}):[/bold yellow]")
    console.print(" 1. Fixed Segments (e.g., every 60 seconds)")
    console.print(" 2. Custom Range (e.g., 00:00:00-00:01:00)")
    console.print(" 3. Split into N parts")
    console.print(" [bold white]B[/bold white]. Back")
    
    mode = get_char("\nPick a #: ")
    console.print()
    if mode.lower() == 'b':
        return None
    output_dir = path_obj.parent / f"{path_obj.stem}_split"
    send_to_trash(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    if mode == '1':
        interval_str = get_input("Interval in seconds (e.g., 60): ")
        try:
            interval = float(interval_str)
            if interval <= 0: raise ValueError
        except ValueError:
            console.print("[bold red]Invalid interval.[/bold red]")
            return None
        
        num_segments = int(duration // interval) + (1 if duration % interval > 0 else 0)
        
        if num_segments > 50:
            console.print(f"\n[bold yellow]Found {num_segments} segments to create. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        console.print(f"[bold cyan]Splitting into segments of {interval}s...[/bold cyan]")
        
        any_success = False
        for i in range(num_segments):
            start = i * interval
            out_file = output_dir / f"part_{i+1:03d}.mp4"
            cmd = ["ffmpeg", "-ss", str(start), "-t", str(interval), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                any_success = True
            else: console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
            
        console.print(f"\n[bold green]Split finished! Files are in {output_dir.name}/[/bold green]")
        return output_dir if any_success else None

    elif mode == '2':
        console.print(f"\n[bold yellow]Enter time ranges separated by commas (e.g., 0-10, 00:01:00-00:02:00):[/bold yellow]")
        input_str = get_input("Ranges: ")
        ranges = []
        try:
            for part in input_str.split(','):
                part = part.strip()
                if not part: continue
                if '-' not in part: raise ValueError(f"'{part}' is not a valid range")
                start_str, end_str = part.split('-', 1)
                start = parse_timestamp(start_str.strip())
                end = parse_timestamp(end_str.strip())
                if start is None or end is None or start < 0 or end > duration or start >= end:
                    raise ValueError(f"Range {start_str}-{end_str} invalid")
                ranges.append((start, end))
        except ValueError as e:
            console.print(f"[bold red]Invalid input: {e}[/bold red]")
            return None
            
        any_success = False
        for idx, (start, end) in enumerate(ranges, 1):
            out_file = output_dir / f"part_{idx}_{int(start)}-{int(end)}.mp4"
            cmd = ["ffmpeg", "-ss", str(start), "-to", str(end), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                console.print(f" [bold green]✓[/bold green] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold green]DONE[/bold green]")
                any_success = True
            else: console.print(f" [bold red]✗[/bold red] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold red]FAILED[/bold red]")
            
        console.print(f"\n[bold green]Custom split finished! Files are in {output_dir.name}/[/bold green]")
        return output_dir if any_success else None

    elif mode == '3':
        num_str = get_input("Number of parts: ")
        try:
            num_parts = int(num_str)
            if num_parts < 1: raise ValueError
        except ValueError:
            console.print("[bold red]Invalid input.[/bold red]")
            return None
            
        interval = duration / num_parts
        if num_parts > 50:
            console.print(f"\n[bold yellow]Found {num_parts} parts to create. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        console.print(f"[bold cyan]Splitting into {num_parts} equal parts (~{interval:.2f}s each)...[/bold cyan]")
        
        any_success = False
        for i in range(num_parts):
            start = i * interval
            out_file = output_dir / f"part_{i+1:03d}.mp4"
            cmd = ["ffmpeg", "-ss", str(start), "-t", str(interval), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                any_success = True
            else: console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
            
        console.print(f"\n[bold green]Split finished! Files are in {output_dir.name}/[/bold green]")
        return output_dir if any_success else None

def split_audio(path):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".mp3":
        console.print(f"[bold red]Error: Could not find MP3 at: [white]{path}[/white][/bold red]")
        return None
    
    duration = get_media_duration(path_obj)
    if duration == 0:
        console.print("[bold red]Error: Could not determine audio duration or file is empty.[/bold red]")
        return None
    
    console.print(f"\n[bold yellow]Split Options for '{path_obj.name}' ({format_seconds(duration)}):[/bold yellow]")
    console.print(" 1. Fixed Segments (e.g., every 60 seconds)")
    console.print(" 2. Custom Range (e.g., 00:00:00-00:01:00)")
    console.print(" 3. Split into N parts")
    console.print(" [bold white]B[/bold white]. Back")
    
    mode = get_char("\nPick a #: ")
    console.print()
    if mode.lower() == 'b':
        return None
        
    output_dir = path_obj.parent / f"{path_obj.stem}_split"
    send_to_trash(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    if mode == '1':
        interval_str = get_input("Interval in seconds (e.g., 60): ")
        try:
            interval = float(interval_str)
            if interval <= 0: raise ValueError
        except ValueError:
            console.print("[bold red]Invalid interval.[/bold red]")
            return None
        
        num_segments = int(duration // interval) + (1 if duration % interval > 0 else 0)
        
        if num_segments > 50:
            console.print(f"\n[bold yellow]Found {num_segments} segments to create. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        console.print(f"[bold cyan]Splitting into segments of {interval}s...[/bold cyan]")
        
        any_success = False
        for i in range(num_segments):
            start = i * interval
            out_file = output_dir / f"part_{i+1:03d}.mp3"
            cmd = ["ffmpeg", "-ss", str(start), "-t", str(interval), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                any_success = True
            else:
                console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
            
        console.print(f"\n[bold green]Split finished! Files are in {output_dir.name}/[/bold green]")
        return output_dir if any_success else None

    elif mode == '2':
        console.print(f"\n[bold yellow]Enter time ranges separated by commas (e.g., 0-10, 00:01:00-00:02:00):[/bold yellow]")
        input_str = get_input("Ranges: ")
        ranges = []
        try:
            for part in input_str.split(','):
                part = part.strip()
                if not part: continue
                if '-' not in part: raise ValueError(f"'{part}' is not a valid range")
                start_str, end_str = part.split('-', 1)
                start = parse_timestamp(start_str.strip())
                end = parse_timestamp(end_str.strip())
                if start is None or end is None or start < 0 or end > duration or start >= end:
                    raise ValueError(f"Range {start_str}-{end_str} invalid")
                ranges.append((start, end))
        except ValueError as e:
            console.print(f"[bold red]Invalid input: {e}[/bold red]")
            return None
            
        any_success = False
        for idx, (start, end) in enumerate(ranges, 1):
            out_file = output_dir / f"part_{idx}_{int(start)}-{int(end)}.mp3"
            cmd = ["ffmpeg", "-ss", str(start), "-to", str(end), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                console.print(f" [bold green]✓[/bold green] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold green]DONE[/bold green]")
                any_success = True
            else:
                console.print(f" [bold red]✗[/bold red] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold red]FAILED[/bold red]")
            
        console.print(f"\n[bold green]Custom split finished! Files are in {output_dir.name}/[/bold green]")
        return output_dir if any_success else None

    elif mode == '3':
        num_str = get_input("Number of parts: ")
        try:
            num_parts = int(num_str)
            if num_parts < 1: raise ValueError
        except ValueError:
            console.print("[bold red]Invalid input.[/bold red]")
            return None
            
        interval = duration / num_parts
        if num_parts > 50:
            console.print(f"\n[bold yellow]Found {num_parts} parts to create. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return None

        console.print(f"[bold cyan]Splitting into {num_parts} equal parts (~{interval:.2f}s each)...[/bold cyan]")
        
        any_success = False
        for i in range(num_parts):
            start = i * interval
            out_file = output_dir / f"part_{i+1:03d}.mp3"
            cmd = ["ffmpeg", "-ss", str(start), "-t", str(interval), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success:
                console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                any_success = True
            else:
                console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
            
        console.print(f"\n[bold green]Split finished! Files are in {output_dir.name}/[/bold green]")
        return output_dir if any_success else None

def split_gif(path):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".gif":
        console.print(f"[bold red]Error: Could not find GIF at: [white]{path}[/white][/bold red]")
        return None
    
    duration = get_media_duration(path_obj)
    
    console.print(f"\n[bold yellow]Split Options for '{path_obj.name}':[/bold yellow]")
    console.print(" 1. Extract Frames (every frame becomes an individual image)")
    console.print(" 2. Split into GIF Segments (fixed intervals, custom ranges, or N parts)")
    console.print(" [bold white]B[/bold white]. Back")
    
    choice = get_char("\nPick a #: ")
    console.print()
    if choice.lower() == 'b':
        return None
        
    output_dir = path_obj.parent / f"{path_obj.stem}_split"
    send_to_trash(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    if choice == '1':
        fmt = get_input("Format for frames (PNG/JPG, default: png): ").strip().lower()
        if not fmt:
            fmt = "png"
        if fmt not in ["png", "jpg", "jpeg"]:
            console.print("[bold red]Invalid format. Defaulting to png.[/bold red]")
            fmt = "png"
            
        console.print(f"[bold cyan]Extracting frames to {fmt.upper()}...[/bold cyan]")
        out_pattern = output_dir / f"frame_%03d.{fmt}"
        cmd = ["ffmpeg", "-i", str(path_obj), "-y", "-loglevel", "error", str(out_pattern)]
        success, error = run_command(cmd)
        if success:
            console.print(f"[bold green]Successfully extracted frames to {output_dir.name}/[/bold green]")
            return output_dir
        else:
            console.print(f"[bold red]FAILED to extract frames[/bold red]")
            if error:
                console.print(f"   [dim]{error.strip()}[/dim]")
            return None
            
    elif choice == '2':
        if duration == 0:
            console.print("[bold red]Error: Could not determine GIF duration or file is empty.[/bold red]")
            return None
            
        console.print(f"\n[bold yellow]GIF Segment Split Options ({format_seconds(duration)}):[/bold yellow]")
        console.print(" 1. Fixed Segments (e.g., every 5 seconds)")
        console.print(" 2. Custom Range (e.g., 00:00:00-00:01:00)")
        console.print(" 3. Split into N parts")
        console.print(" [bold white]B[/bold white]. Back")
        
        mode = get_char("\nPick a #: ")
        console.print()
        if mode.lower() == 'b':
            return None
            
        if mode == '1':
            interval_str = get_input("Interval in seconds (e.g., 5): ")
            try:
                interval = float(interval_str)
                if interval <= 0: raise ValueError
            except ValueError:
                console.print("[bold red]Invalid interval.[/bold red]")
                return None
            
            num_segments = int(duration // interval) + (1 if duration % interval > 0 else 0)
            if num_segments > 50:
                console.print(f"\n[bold yellow]Found {num_segments} segments to create. Proceed? (y/n)[/bold yellow]")
                if get_char("   Choice: ").lower() != 'y':
                    console.print("[yellow]Operation cancelled.[/yellow]")
                    return None

            console.print(f"[bold cyan]Splitting into segments of {interval}s...[/bold cyan]")
            any_success = False
            for i in range(num_segments):
                start = i * interval
                out_file = output_dir / f"part_{i+1:03d}.gif"
                cmd = ["ffmpeg", "-ss", str(start), "-t", str(interval), "-i", str(path_obj), "-y", "-loglevel", "error", str(out_file)]
                success, _ = run_command(cmd)
                if success:
                    console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                    any_success = True
                else: console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
                
            console.print(f"\n[bold green]Split finished! Files are in {output_dir.name}/[/bold green]")
            return output_dir if any_success else None

        elif mode == '2':
            console.print(f"\n[bold yellow]Enter time ranges separated by commas (e.g., 0-10, 00:01:00-00:02:00):[/bold yellow]")
            input_str = get_input("Ranges: ")
            ranges = []
            try:
                for part in input_str.split(','):
                    part = part.strip()
                    if not part: continue
                    if '-' not in part: raise ValueError(f"'{part}' is not a valid range")
                    start_str, end_str = part.split('-', 1)
                    start = parse_timestamp(start_str.strip())
                    end = parse_timestamp(end_str.strip())
                    if start is None or end is None or start < 0 or end > duration or start >= end:
                        raise ValueError(f"Range {start_str}-{end_str} invalid")
                    ranges.append((start, end))
            except ValueError as e:
                console.print(f"[bold red]Invalid input: {e}[/bold red]")
                return None
                
            any_success = False
            for idx, (start, end) in enumerate(ranges, 1):
                out_file = output_dir / f"part_{idx}_{int(start)}-{int(end)}.gif"
                cmd = ["ffmpeg", "-ss", str(start), "-to", str(end), "-i", str(path_obj), "-y", "-loglevel", "error", str(out_file)]
                success, _ = run_command(cmd)
                if success:
                    console.print(f" [bold green]✓[/bold green] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold green]DONE[/bold green]")
                    any_success = True
                else: console.print(f" [bold red]✗[/bold red] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold red]FAILED[/bold red]")
                
            console.print(f"\n[bold green]Custom split finished! Files are in {output_dir.name}/[/bold green]")
            return output_dir if any_success else None

        elif mode == '3':
            num_str = get_input("Number of parts: ")
            try:
                num_parts = int(num_str)
                if num_parts < 1: raise ValueError
            except ValueError:
                console.print("[bold red]Invalid input.[/bold red]")
                return None
                
            interval = duration / num_parts
            if num_parts > 50:
                console.print(f"\n[bold yellow]Found {num_parts} parts to create. Proceed? (y/n)[/bold yellow]")
                if get_char("   Choice: ").lower() != 'y':
                    console.print("[yellow]Operation cancelled.[/yellow]")
                    return None

            console.print(f"[bold cyan]Splitting into {num_parts} equal parts (~{interval:.2f}s each)...[/bold cyan]")
            any_success = False
            for i in range(num_parts):
                start = i * interval
                out_file = output_dir / f"part_{i+1:03d}.gif"
                cmd = ["ffmpeg", "-ss", str(start), "-t", str(interval), "-i", str(path_obj), "-y", "-loglevel", "error", str(out_file)]
                success, _ = run_command(cmd)
                if success:
                    console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
                    any_success = True
                else: console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
                
            console.print(f"\n[bold green]Split finished! Files are in {output_dir.name}/[/bold green]")
            return output_dir if any_success else None
            
    return None
