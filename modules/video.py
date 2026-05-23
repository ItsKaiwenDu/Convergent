import os
import subprocess
import sys
from pathlib import Path
from customs.run_command import run_command, send_to_trash

from customs.console import console, get_input, get_char

def get_video_duration(path):
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
    """Parses HH:MM:SS or seconds into float."""
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

def convert_video(source, target_ext, fps=None, bitrate=None):
    output = source.with_suffix(f".{target_ext.lower()}")
    cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
    if target_ext.upper() == "MP4":
        cmd += ["-c:v", "libx264", "-c:a", "aac", "-strict", "experimental"]
    elif target_ext.upper() == "WEBM":
        cmd += ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30", "-c:a", "libopus"]
    elif target_ext.upper() == "GIF":
        vf = "scale=480:-1:flags=lanczos"
        if fps:
            vf = f"fps={fps}," + vf
        cmd += ["-vf", vf]
    elif target_ext.upper() == "MP3":
        if bitrate in ["128k", "192k", "320k"]:
            cmd += ["-vn", "-acodec", "libmp3lame", "-b:a", bitrate]
        else:
            cmd += ["-vn", "-acodec", "libmp3lame", "-q:a", "2"]
    elif target_ext.upper() == "WAV":
        cmd += ["-vn", "-acodec", "pcm_s16le"]
    elif target_ext.upper() == "M4A":
        cmd += ["-vn", "-acodec", "aac", "-q:a", "2"]
    
    cmd.append(str(output))
    return run_command(cmd)

def split_video(path):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".mp4":
        console.print(f"[bold red]Error: Could not find MP4 at: [white]{path}[/white][/bold red]")
        return
    
    duration = get_video_duration(path_obj)
    if duration == 0:
        console.print("[bold red]Error: Could not determine video duration or file is empty.[/bold red]")
        return
    
    console.print(f"\n[bold yellow]Split Options for '{path_obj.name}' ({format_seconds(duration)}):[/bold yellow]")
    console.print(" 1. Fixed Segments (e.g., every 60 seconds)")
    console.print(" 2. Custom Range (e.g., 00:00:00-00:01:00)")
    console.print(" 3. Split into N parts")
    console.print(" [bold white]B[/bold white]. Back")
    
    mode = get_char("\nPick a #: ")
    console.print()
    if mode.lower() == 'b':
        return
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
            return
        
        num_segments = int(duration // interval) + (1 if duration % interval > 0 else 0)
        
        if num_segments > 50:
            console.print(f"\n[bold yellow]Found {num_segments} segments to create. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return

        console.print(f"[bold cyan]Splitting into segments of {interval}s...[/bold cyan]")
        
        for i in range(num_segments):
            start = i * interval
            out_file = output_dir / f"part_{i+1:03d}.mp4"
            cmd = ["ffmpeg", "-ss", str(start), "-t", str(interval), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success: console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
            else: console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
            
        console.print(f"\n[bold green]Split finished! Files are in {output_dir.name}/[/bold green]")

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
            return
            
        for idx, (start, end) in enumerate(ranges, 1):
            out_file = output_dir / f"part_{idx}_{int(start)}-{int(end)}.mp4"
            cmd = ["ffmpeg", "-ss", str(start), "-to", str(end), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success: console.print(f" [bold green]✓[/bold green] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold green]DONE[/bold green]")
            else: console.print(f" [bold red]✗[/bold red] Part {idx} ({format_seconds(start)} to {format_seconds(end)}): [bold red]FAILED[/bold red]")
            
        console.print(f"\n[bold green]Custom split finished! Files are in {output_dir.name}/[/bold green]")

    elif mode == '3':
        num_str = get_input("Number of parts: ")
        try:
            num_parts = int(num_str)
            if num_parts < 1: raise ValueError
        except ValueError:
            console.print("[bold red]Invalid input.[/bold red]")
            return
            
        interval = duration / num_parts
        if num_parts > 50:
            console.print(f"\n[bold yellow]Found {num_parts} parts to create. Proceed? (y/n)[/bold yellow]")
            choice = get_char("   Choice: ")
            console.print()
            if choice.lower() != 'y':
                console.print("[yellow]Operation cancelled.[/yellow]")
                return

        console.print(f"[bold cyan]Splitting into {num_parts} equal parts (~{interval:.2f}s each)...[/bold cyan]")
        
        for i in range(num_parts):
            start = i * interval
            out_file = output_dir / f"part_{i+1:03d}.mp4"
            cmd = ["ffmpeg", "-ss", str(start), "-t", str(interval), "-i", str(path_obj), "-c", "copy", "-y", "-loglevel", "error", str(out_file)]
            success, _ = run_command(cmd)
            if success: console.print(f" [bold green]✓[/bold green] Part {i+1}: [bold green]DONE[/bold green]")
            else: console.print(f" [bold red]✗[/bold red] Part {i+1}: [bold red]FAILED[/bold red]")
            
        console.print(f"\n[bold green]Split finished! Files are in {output_dir.name}/[/bold green]")
