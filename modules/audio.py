import os
import subprocess
from pathlib import Path
from customs.run_command import run_command, send_to_trash

def convert_audio(source, target_ext, bitrate=None):
    output = source.with_suffix(f".{target_ext.lower()}")
    cmd = ["ffmpeg", "-i", str(source), "-y", "-loglevel", "error"]
    if target_ext.upper() == "MP3":
        if bitrate in ["128k", "192k", "320k"]:
            cmd += ["-acodec", "libmp3lame", "-b:a", bitrate]
        else:
            cmd += ["-acodec", "libmp3lame", "-q:a", "2"]
    elif target_ext.upper() == "M4A":
        cmd += ["-acodec", "aac", "-q:a", "2"]
    elif target_ext.upper() == "WAV":
        cmd += ["-acodec", "pcm_s16le"]
    elif target_ext.upper() == "FLAC":
        cmd += ["-acodec", "flac"]
    
    cmd.append(str(output))
    return run_command(cmd)

def get_audio_duration(path):
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

def combine_audios(paths):
    import re
    from customs.console import console, get_input, get_char
    
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
        duration = get_audio_duration(str(f))
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

def split_audio(path):
    from customs.console import console, get_input, get_char
    
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".mp3":
        console.print(f"[bold red]Error: Could not find MP3 at: [white]{path}[/white][/bold red]")
        return None
    
    duration = get_audio_duration(path_obj)
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
