import os
import time
import subprocess
import multiprocessing
import concurrent.futures
from pathlib import Path
from customs.run_command import run_command, send_to_trash
from customs.file_process import prompt_move_files

try:
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

def get_image_dimensions(path):
    """
    Returns the orientation-adjusted (width, height) of an image using ImageMagick identify.
    """
    try:
        cmd = ["magick", "identify", "-format", "%w %h %[orientation]", str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        parts = result.stdout.strip().split()
        if len(parts) >= 2:
            w = int(parts[0])
            h = int(parts[1])
            orient = parts[2].lower() if len(parts) >= 3 else ""
            if any(o in orient for o in ["righttop", "leftbottom", "lefttop", "rightbottom", "6", "8", "5", "7"]):
                w, h = h, w
            return w, h
    except:
        pass
    return None, None

def get_video_dimensions(path):
    """
    Returns the rotation-adjusted (width, height) of a video using ffprobe.
    """
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().splitlines()
        if len(lines) >= 2:
            w = int(lines[0])
            h = int(lines[1])
            
            # Check rotation tag
            rot_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream_tags=rotate", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
            rot_result = subprocess.run(rot_cmd, capture_output=True, text=True)
            rotation = 0
            if rot_result.returncode == 0 and rot_result.stdout.strip():
                try:
                    rotation = int(float(rot_result.stdout.strip()))
                except:
                    pass
            
            # Check displaymatrix side data rotation
            if rotation == 0:
                side_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream_side_data=rotation", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
                side_result = subprocess.run(side_cmd, capture_output=True, text=True)
                if side_result.returncode == 0 and side_result.stdout.strip():
                    try:
                        rotation = int(float(side_result.stdout.strip()))
                    except:
                        pass
            
            if rotation in [90, 270, -90, -270]:
                w, h = h, w
            return w, h
    except:
        pass
    return None, None

def make_even(n):
    """
    Returns the nearest even integer to n, ensuring video format compatibility.
    """
    val = int(round(n))
    if val % 2 != 0:
        val += 1
    return val

def calculate_crop_and_scale(w, h, method, scale_val, target_aspect):
    """
    Given original dimensions w, h, target resize method, scale value, and target aspect ratio,
    returns (w_crop, h_crop, w_final, h_final).
    """
    aspect_map = {
        '2': 16/9,
        '3': 4/3,
        '4': 1/1,
        '5': 9/16
    }
    
    # 1. Target Aspect Ratio Cropping Dimensions
    if target_aspect in aspect_map:
        aspect = aspect_map[target_aspect]
        orig_aspect = w / h
        if orig_aspect > aspect:
            # Original is wider than target aspect ratio -> Crop width
            h_crop = h
            w_crop = int(round(h * aspect))
        else:
            # Original is taller than target aspect ratio -> Crop height
            w_crop = w
            h_crop = int(round(w / aspect))
    else:
        w_crop = w
        h_crop = h

    # 2. Scale Calculations
    if method == '1':
        # Scale by Percentage
        p = scale_val / 100.0
        w_final = int(round(w_crop * p))
        h_final = int(round(h_crop * p))
    elif method == '2':
        # Set Target Height
        h_final = scale_val
        w_final = int(round(scale_val * (w_crop / h_crop)))
    elif method == '3':
        # Custom width and height
        w_final, h_final = scale_val
    else:
        # No change
        w_final = w_crop
        h_final = h_crop

    return w_crop, h_crop, w_final, h_final

def resize_single_file(f, method, scale_val, target_aspect):
    """
    Resizes/crops a single file (image or video) and saves it with a '_resized' suffix.
    """
    start_time = time.perf_counter()
    is_video = f.suffix.lower() == ".mp4"
    
    if is_video:
        w, h = get_video_dimensions(f)
    else:
        w, h = get_image_dimensions(f)
        
    if not w or not h:
        duration = time.perf_counter() - start_time
        return f.name, False, "Could not determine original dimensions", duration

    w_crop, h_crop, w_final, h_final = calculate_crop_and_scale(w, h, method, scale_val, target_aspect)
    
    if is_video:
        w_crop = make_even(w_crop)
        h_crop = make_even(h_crop)
        w_final = make_even(w_final)
        h_final = make_even(h_final)

    crop_needed = (w_crop != w or h_crop != h)
    scale_needed = (w_final != w_crop or h_final != h_crop)
    
    output = f.parent / f"{f.stem}_resized{f.suffix}"
    send_to_trash(output)

    success = False
    error = ""
    
    if is_video:
        filters = []
        if crop_needed:
            filters.append(f"crop={w_crop}:{h_crop}")
        if scale_needed:
            filters.append(f"scale={w_final}:{h_final}")
            
        cmd = ["ffmpeg", "-i", str(f)]
        if filters:
            cmd += ["-vf", ",".join(filters)]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", "-y", "-loglevel", "error", str(output)]
        success, error = run_command(cmd)
    else:
        cmd = ["magick", str(f), "-auto-orient"]
        if crop_needed:
            cmd += ["-gravity", "center", "-crop", f"{w_crop}x{h_crop}+0+0", "+repage"]
        if scale_needed:
            cmd += ["-resize", f"{w_final}x{h_final}!"]
        cmd.append(str(output))
        success, error = run_command(cmd)
        
    duration = time.perf_counter() - start_time
    return f.name, success, error, duration

def resize_media(paths, conv, console, get_char, get_input):
    """
    Interactive orchestrator to resize files in the given paths.
    """
    supported_exts = {".mp4", ".jpg", ".jpeg", ".png", ".heic"}
    files = []
    
    # 1. Collect files
    for p in paths:
        path_obj = Path(os.path.expanduser(p))
        if path_obj.is_file():
            if path_obj.suffix.lower() in supported_exts:
                files.append(path_obj)
        elif path_obj.is_dir():
            for item in path_obj.iterdir():
                if item.is_file() and item.suffix.lower() in supported_exts:
                    files.append(item)
                    
    files = sorted(list(set(files)))
    
    if not files:
        console.print("[bold red]No MP4, JPG, PNG, or HEIC files found in the provided paths.[/bold red]")
        get_char("\nPress any key to continue...")
        return

    # 2. Display files and dimensions
    console.print("\n[bold yellow]Files to Resize:[/bold yellow]")
    for idx, f in enumerate(files, 1):
        if f.suffix.lower() == ".mp4":
            w, h = get_video_dimensions(f)
        else:
            w, h = get_image_dimensions(f)
        dim_str = f"({w}x{h})" if w and h else "(unknown dimensions)"
        console.print(f" {idx}. {f.name} [dim]{dim_str}[/dim]")

    # 3. Select Resize Method
    console.print("\n[bold yellow]Select Resize Method:[/bold yellow]")
    console.print(" 1. Scale by Percentage (e.g., 50%)")
    console.print(" 2. Set Target Height (maintain aspect ratio, e.g., 720px)")
    console.print(" 3. Set Custom Width & Height (e.g., 800x600)")
    console.print(" 4. No Change (Keep original resolution)")
    console.print(" [bold white]B[/bold white]. Back")
    
    method = get_char("\nPick a #: ")
    if method.lower() == 'b':
        return
    if method not in ('1', '2', '3', '4'):
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return
        
    scale_val = None
    if method == '1':
        pct_str = get_input("\nEnter percentage (e.g. 50): ")
        try:
            scale_val = float(pct_str)
            if scale_val <= 0:
                raise ValueError
        except ValueError:
            console.print("[bold red]Invalid percentage.[/bold red]")
            get_char("\nPress any key to continue...")
            return
    elif method == '2':
        h_str = get_input("\nEnter target height in pixels (e.g. 720): ")
        try:
            scale_val = int(h_str)
            if scale_val <= 0:
                raise ValueError
        except ValueError:
            console.print("[bold red]Invalid height.[/bold red]")
            get_char("\nPress any key to continue...")
            return
    elif method == '3':
        dims_str = get_input("\nEnter target width and height (e.g. 800x600): ")
        try:
            if 'x' in dims_str:
                w_str, h_str = dims_str.split('x', 1)
            else:
                w_str, h_str = dims_str.split(None, 1)
            w_val = int(w_str.strip())
            h_val = int(h_str.strip())
            if w_val <= 0 or h_val <= 0:
                raise ValueError
            scale_val = (w_val, h_val)
        except ValueError:
            console.print("[bold red]Invalid width and height format. Use e.g. 800x600 or 800 600.[/bold red]")
            get_char("\nPress any key to continue...")
            return

    # 4. Select Aspect Ratio
    console.print("\n[bold yellow]Select Target Aspect Ratio:[/bold yellow]")
    console.print(" 1. Keep Original Aspect Ratio")
    console.print(" 2. 16:9 (Widescreen)")
    console.print(" 3. 4:3 (Standard)")
    console.print(" 4. 1:1 (Square)")
    console.print(" 5. 9:16 (Vertical)")
    console.print(" [bold white]B[/bold white]. Back")
    
    target_aspect = get_char("\nPick a #: ")
    if target_aspect.lower() == 'b':
        return
    if target_aspect not in ('1', '2', '3', '4', '5'):
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return

    if method == '4' and target_aspect == '1':
        console.print("\n[yellow]No changes selected (No Change & Keep Original aspect ratio).[/yellow]")
        get_char("\nPress any key to continue...")
        return

    # 5. Confirm
    console.print(f"\n[bold yellow]Confirm resizing of {len(files)} file(s)? (y/n):[/bold yellow] ", end="")
    confirm = get_char("")
    console.print()
    if confirm.lower() != 'y':
        console.print("[yellow]Operation cancelled.[/yellow]")
        get_char("\nPress any key to continue...")
        return

    num_files = len(files)
    if num_files > 50:
        console.print(f"\n[bold yellow]Found {num_files} files to resize. Proceed? (y/n)[/bold yellow]")
        if get_char("   Choice: ").lower() != 'y':
            console.print("[yellow]Operation cancelled.[/yellow]")
            get_char("\nPress any key to continue...")
            return

    # 6. Execute Batch
    success_count = 0
    fail_count = 0
    batch_start_time = time.perf_counter()
    converted_files = []
    
    jobs = min(multiprocessing.cpu_count(), len(files))

    if HAS_RICH:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Resizing...", total=len(files))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
                futures = {executor.submit(resize_single_file, f, method, scale_val, target_aspect): f for f in files}
                
                for future in concurrent.futures.as_completed(futures):
                    name, success, error, duration = future.result()
                    if success:
                        success_count += 1
                        progress.console.print(f" [bold green]✓[/bold green] {name} [dim]→ {duration:.1f}s[/dim]")
                        orig_file = futures[future]
                        out_path = orig_file.parent / f"{orig_file.stem}_resized{orig_file.suffix}"
                        converted_files.append(out_path)
                    else:
                        fail_count += 1
                        progress.console.print(f" [bold red]✗[/bold red] {name}: [dim]{error.strip()} ({duration:.1f}s)[/dim]")
                    progress.update(task, advance=1)
    else:
        for f in files:
            name, success, error, duration = resize_single_file(f, method, scale_val, target_aspect)
            if success:
                success_count += 1
                console.print(f" > {name}... [bold green]DONE[/bold green] [dim]({duration:.1f}s)[/dim]")
                out_path = f.parent / f"{f.stem}_resized{f.suffix}"
                converted_files.append(out_path)
            else:
                fail_count += 1
                console.print(f" > {name}... [bold red]FAILED[/bold red] [dim]({duration:.1f}s)[/dim]")
                if error:
                    console.print(f"   [dim]{error.strip()}[/dim]")

    total_time = time.perf_counter() - batch_start_time
    summary_parts = [
        f"[bold green]✓ {success_count} resized[/bold green]",
        f"[bold red]✗ {fail_count} failed[/bold red]",
        f"[bold cyan]⏱ {total_time:.1f}s total[/bold cyan]"
    ]
    console.print(f"\n{', '.join(summary_parts)}")

    if converted_files:
        prompt_move_files(console, get_char, get_input, converted_files)
    else:
        get_char("\nPress any key to continue...")
