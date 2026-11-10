import os
import time
import uuid
import shutil
import subprocess
import multiprocessing
import concurrent.futures
from pathlib import Path
from customs.run_command import run_command, send_to_trash
from customs.file_process import prompt_move_files
from customs.console import prompt_strip_metadata, prompt_video_fps
from customs.check_deps import ensure_dependencies
from customs.hwaccel import get_video_encoder

VIDEO_EXTS = {".mp4", ".mov"}

try:
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

def get_image_dimensions(path):
    """
    Returns orientation-adjusted (width, height) of an image using ImageMagick identify.
    """
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return get_pdf_dimensions(path)

    if not shutil.which("magick"):
        raise RuntimeError("ImageMagick ('magick') is not installed or not in PATH. Please install it with 'brew install imagemagick'.")
    try:
        cmd = ["magick", "identify", "-format", "%w %h %[orientation]", str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, errors="replace")
        parts = result.stdout.strip().split()
        if len(parts) >= 2:
            w = int(parts[0])
            h = int(parts[1])
            orient = parts[2].lower() if len(parts) >= 3 else ""
            if any(o in orient for o in ["righttop", "leftbottom", "lefttop", "rightbottom", "6", "8", "5", "7"]):
                w, h = h, w
            return w, h
    except subprocess.CalledProcessError:
        pass
    except Exception:
        pass
    return None, None

def get_pdf_dimensions(path):
    """
    Returns orientation-adjusted (width, height) in points of first page of a PDF.
    Tries ImageMagick identify (with [0] selector) first, then falls back to Ghostscript MediaBox.
    """
    path = Path(path)
    if shutil.which("magick"):
        try:
            cmd = ["magick", "identify", "-format", "%w %h %[orientation]", f"{path.resolve()}[0]"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, errors="replace")
            parts = result.stdout.strip().split()
            if len(parts) >= 2:
                w = int(parts[0])
                h = int(parts[1])
                orient = parts[2].lower() if len(parts) >= 3 else ""
                if any(o in orient for o in ["righttop", "leftbottom", "lefttop", "rightbottom", "6", "8", "5", "7"]):
                    w, h = h, w
                return w, h
        except subprocess.CalledProcessError:
            pass
        except Exception:
            pass

    if shutil.which("gs"):
        try:
            resolved_p = str(path.resolve())
            cmd = [
                "gs", "-q", "-dNODISPLAY", "-dSAFER",
                f"--permit-file-read={resolved_p}",
                "-c",
                f"({resolved_p}) (r) file runpdfbegin 1 pdfgetpage /MediaBox pget {{ == }} if quit"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, errors="replace")
            parts = result.stdout.replace("[", "").replace("]", "").strip().split()
            if len(parts) >= 4:
                w = int(round(float(parts[2]) - float(parts[0])))
                h = int(round(float(parts[3]) - float(parts[1])))
                return w, h
        except Exception:
            pass

    if not shutil.which("magick") and not shutil.which("gs"):
        raise RuntimeError("Neither ImageMagick ('magick') nor Ghostscript ('gs') is installed or in PATH.")

    return None, None

def get_video_dimensions(path):
    """
    Returns rotation-adjusted (width, height) of a video using ffprobe.
    """
    if not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg ('ffprobe') is not installed or not in PATH. Please install it with 'brew install ffmpeg'.")
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, errors="replace")
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
    Returns nearest even integer to n, ensuring video format compatibility.
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
        '1': 16/9,
        '2': 4/3,
        '3': 1/1,
        '4': 9/16,
        '16:9': 16/9,
        '4:3': 4/3,
        '1:1': 1/1,
        '9:16': 9/16,
    }
    
    if target_aspect and str(target_aspect) not in ('5', 'none', 'auto'):
        if str(target_aspect) in aspect_map:
            aspect = aspect_map[str(target_aspect)]
            orig_aspect = w / h
            if orig_aspect > aspect:
                h_crop = h
                w_crop = int(round(h * aspect))
            else:
                w_crop = w
                h_crop = int(round(w / aspect))
        else:
            raise ValueError(f"Invalid target aspect ratio: {target_aspect}. Supported: 16:9, 4:3, 1:1, 9:16")
    else:
        w_crop = w
        h_crop = h

    if method == '1':
        if scale_val is None or scale_val <= 0:
            raise ValueError(f"Scale percentage must be greater than 0, got {scale_val}")
        p = scale_val / 100.0
        w_final = int(round(w_crop * p))
        h_final = int(round(h_crop * p))
    elif method == '2':
        if scale_val is None or scale_val <= 0:
            raise ValueError(f"Target height must be greater than 0, got {scale_val}")
        h_final = scale_val
        w_final = int(round(scale_val * (w_crop / h_crop)))
    elif method == '3':
        if not scale_val or len(scale_val) < 2 or scale_val[0] <= 0 or scale_val[1] <= 0:
            raise ValueError(f"Target dimensions must be greater than 0, got {scale_val}")
        w_final, h_final = scale_val[0], scale_val[1]
    elif method == 'w':
        if scale_val is None or scale_val <= 0:
            raise ValueError(f"Target width must be greater than 0, got {scale_val}")
        w_final = scale_val
        h_final = int(round(scale_val * (h_crop / w_crop)))
    else:
        w_final = w_crop
        h_final = h_crop

    return w_crop, h_crop, w_final, h_final

def resize_single_file(f, method, scale_val, target_aspect, fps=None, hwaccel="auto", strip_metadata=False, output_path=None, dpi=None):
    """
    Resizes/crops a single file (image, video, or PDF) and saves it with a '_resized' suffix.
    """
    start_time = time.perf_counter()
    f = Path(f)
    is_video = f.suffix.lower() in VIDEO_EXTS
    is_pdf = f.suffix.lower() == ".pdf"
    
    try:
        if is_video:
            w, h = get_video_dimensions(f)
        elif is_pdf:
            w, h = get_pdf_dimensions(f)
        else:
            w, h = get_image_dimensions(f)
    except RuntimeError as e:
        duration = time.perf_counter() - start_time
        return f.name, False, str(e), duration
        
    if not w or not h:
        duration = time.perf_counter() - start_time
        return f.name, False, "Could not determine original dimensions", duration

    try:
        w_crop, h_crop, w_final, h_final = calculate_crop_and_scale(w, h, method, scale_val, target_aspect)
    except ValueError as e:
        duration = time.perf_counter() - start_time
        return f.name, False, str(e), duration
    
    if is_video:
        w_crop = make_even(w_crop)
        h_crop = make_even(h_crop)
        w_final = make_even(w_final)
        h_final = make_even(h_final)

    crop_needed = (w_crop != w or h_crop != h)
    scale_needed = (w_final != w_crop or h_final != h_crop)
    
    if output_path:
        out_p = Path(os.path.expanduser(str(output_path))).resolve()
        if out_p.is_dir() or str(output_path).endswith(os.sep) or str(output_path).endswith("/"):
            output = out_p / f"{f.stem}_resized{f.suffix}"
        else:
            output = out_p
    else:
        output = f.parent / f"{f.stem}_resized{f.suffix}"
    output.parent.mkdir(parents=True, exist_ok=True)

    actual_output = output.parent / f".tmp_{uuid.uuid4().hex[:8]}_{output.name}"

    success = False
    error = ""
    
    if is_video:
        filters = []
        if crop_needed:
            filters.append(f"crop={w_crop}:{h_crop}")
        if scale_needed:
            filters.append(f"scale={w_final}:{h_final}")
            
        video_ext = f.suffix.lstrip(".").upper()
        encoder, extra_flags, mode_tag = get_video_encoder(video_ext, hwaccel)
        cmd = ["ffmpeg", "-i", str(f)]
        if filters:
            cmd += ["-vf", ",".join(filters)]
        if fps:
            cmd += ["-r", str(fps)]
        if strip_metadata:
            cmd += ["-map_metadata", "-1"]
        cmd += ["-c:v", encoder] + extra_flags + ["-c:a", "copy", "-y", "-loglevel", "error", str(actual_output)]
        success, error = run_command(cmd)

        if not success and encoder != "libx264":
            fallback_cmd = ["ffmpeg", "-i", str(f)]
            if filters:
                fallback_cmd += ["-vf", ",".join(filters)]
            if fps:
                fallback_cmd += ["-r", str(fps)]
            if strip_metadata:
                fallback_cmd += ["-map_metadata", "-1"]
            fallback_cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", "-y", "-loglevel", "error", str(actual_output)]
            success, error = run_command(fallback_cmd)
    elif is_pdf:
        if shutil.which("gs"):
            cmd = [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dDEVICEWIDTHPOINTS={w_final}",
                f"-dDEVICEHEIGHTPOINTS={h_final}",
                "-dPDFFitPage",
                "-dFIXEDMEDIA",
                "-dNOPAUSE",
                "-dBATCH",
                "-dSAFER",
                f"--permit-file-read={f.resolve()}",
                f"--permit-file-write={actual_output.parent.resolve()}/*",
            ]

            scale_ratio = min(w_final / w_crop, h_final / h_crop) if w_crop and h_crop else 1.0
            if dpi is not None and int(dpi) > 0:
                target_dpi = int(dpi)
            else:
                target_dpi = max(72, min(300, int(round(300 * scale_ratio))))

            cmd += [
                "-dDownsampleColorImages=true",
                "-dColorImageDownsampleType=/Bicubic",
                f"-dColorImageResolution={target_dpi}",
                "-dDownsampleGrayImages=true",
                "-dGrayImageDownsampleType=/Bicubic",
                f"-dGrayImageResolution={target_dpi}",
                "-dDownsampleMonoImages=true",
                "-dMonoImageDownsampleType=/Bicubic",
                f"-dMonoImageResolution={min(600, target_dpi * 2)}",
            ]

            if strip_metadata:
                cmd += [
                    "-dPreserveAnnots=false",
                    f"-sOutputFile={actual_output}",
                    str(f.resolve()),
                    "-c",
                    "[ /Title () /Author () /Subject () /Keywords () /Creator () /ModDate () /CreationDate () /DOCINFO pdfmark",
                ]
            else:
                cmd += [
                    f"-sOutputFile={actual_output}",
                    str(f.resolve()),
                ]

            success, error = run_command(cmd)

        if not success and shutil.which("magick"):
            cmd = ["magick", str(f), "-auto-orient"]
            if crop_needed:
                cmd += ["-gravity", "center", "-crop", f"{w_crop}x{h_crop}+0+0", "+repage"]
            if scale_needed:
                cmd += ["-resize", f"{w_final}x{h_final}!"]
            if strip_metadata:
                cmd += ["+profile", "exif,iptc,xmp"]
            cmd.append(str(actual_output))
            success, error = run_command(cmd)

        if not success and not error:
            error = "Neither Ghostscript ('gs') nor ImageMagick ('magick') is available to resize PDF."
    else:
        cmd = ["magick", str(f), "-auto-orient"]
        if crop_needed:
            cmd += ["-gravity", "center", "-crop", f"{w_crop}x{h_crop}+0+0", "+repage"]
        if scale_needed:
            cmd += ["-resize", f"{w_final}x{h_final}!"]
        if strip_metadata:
            cmd += ["+profile", "exif,iptc,xmp"]
        cmd.append(str(actual_output))
        success, error = run_command(cmd)

    if success and actual_output.exists():
        try:
            os.replace(str(actual_output), str(output))
        except Exception as e:
            if actual_output.exists():
                try:
                    actual_output.unlink(missing_ok=True)
                except Exception:
                    pass
            success = False
            error = str(e)
    else:
        if actual_output.exists():
            try:
                actual_output.unlink(missing_ok=True)
            except Exception:
                pass
        
    duration = time.perf_counter() - start_time
    return f.name, success, error, duration

def resize_media(paths, conv, console, get_char, get_input):
    """
    Interactive orchestrator to resize files in given paths.
    """
    supported_exts = {".mp4", ".mov", ".jpg", ".png", ".heic", ".pdf"}
    files = []
    
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
        console.print("[bold red]No MP4, MOV, JPG, PNG, HEIC, or PDF files found in provided paths.[/bold red]")
        get_char("\nPress any key to continue...")
        return

    tools = []
    for f in files:
        suf = f.suffix.lower()
        if suf in VIDEO_EXTS:
            tools.append("ffmpeg")
        elif suf == ".pdf":
            tools.append("ghostscript")
        else:
            tools.append("imagemagick7")
    if not ensure_dependencies(tools, interactive=True, install=conv.install_deps):
        return []

    console.print("\n[bold yellow]Files to Resize:[/bold yellow]")
    for idx, f in enumerate(files, 1):
        try:
            if f.suffix.lower() in VIDEO_EXTS:
                w, h = get_video_dimensions(f)
            elif f.suffix.lower() == ".pdf":
                w, h = get_pdf_dimensions(f)
            else:
                w, h = get_image_dimensions(f)
        except RuntimeError:
            w, h = None, None
        dim_str = f"({w}x{h})" if w and h else "(unknown dimensions)"
        console.print(f" [bold cyan]{idx}.[/bold cyan] {f.name} [dim]{dim_str}[/dim]")

    step = 1
    method = None
    scale_val = None
    target_aspect = '5'
    strip_metadata = False
    fps = None
    has_video = any(f.suffix.lower() in VIDEO_EXTS for f in files)

    while True:
        if step == 1:
            console.print("\n[bold yellow]Select Resize Method:[/bold yellow]")
            console.print(" [bold cyan]1.[/bold cyan] By Percentage (e.g., 50%)")
            console.print(" [bold cyan]2.[/bold cyan] By Target Height (e.g., 720px)")
            console.print(" [bold cyan]3.[/bold cyan] By Dimensions (e.g., 800x600)")
            console.print(" [bold cyan]4.[/bold cyan] Skip")
            console.print(" [bold white]B[/bold white]. Back")
            
            method = get_char("\nSelect Option: ")
            if method.lower() == 'b':
                return False
            if method not in ('1', '2', '3', '4'):
                console.print(" [dim]Invalid choice[/dim]")
                time.sleep(0.5)
                continue
                
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
                    continue
            elif method == '2':
                h_str = get_input("\nEnter target height in pixels (e.g. 720): ")
                try:
                    scale_val = int(h_str)
                    if scale_val <= 0:
                        raise ValueError
                except ValueError:
                    console.print("[bold red]Invalid height.[/bold red]")
                    get_char("\nPress any key to continue...")
                    continue
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
                    continue

            if method == '3':
                target_aspect = '5'
                step = 3 if has_video else 4
            else:
                step = 2

        elif step == 2:
            console.print("\n[bold yellow]Select Target Aspect Ratio:[/bold yellow]")
            console.print(" [bold cyan]1.[/bold cyan] 16:9 (Widescreen)")
            console.print(" [bold cyan]2.[/bold cyan] 4:3 (Standard)")
            console.print(" [bold cyan]3.[/bold cyan] 1:1 (Square)")
            console.print(" [bold cyan]4.[/bold cyan] 9:16 (Vertical)")
            console.print(" [bold cyan]5.[/bold cyan] Skip")
            console.print(" [bold white]B[/bold white]. Back")
            
            target_aspect = get_char("\nSelect Option: ")
            if target_aspect.lower() == 'b':
                step = 1
                continue
            if target_aspect not in ('1', '2', '3', '4', '5'):
                console.print(" [dim]Invalid choice[/dim]")
                time.sleep(0.5)
                continue

            if method == '4' and target_aspect == '5':
                console.print("\n[yellow]No changes selected (both scaling and aspect ratio skipped).[/yellow]")
                get_char("\nPress any key to continue...")
                step = 1
                continue

            step = 3 if has_video else 4

        elif step == 3:
            status, val = prompt_video_fps(get_char, get_input)
            if status == "back":
                step = 1 if method == '3' else 2
                continue
            if status == "invalid":
                continue
            fps = val
            step = 4

        elif step == 4:
            status, strip_metadata = prompt_strip_metadata()
            if status == "back":
                step = 3 if has_video else (1 if method == '3' else 2)
                continue
            if status == "invalid":
                continue
            break

    num_files = len(files)
    if num_files > 50:
        console.print(f"\n[bold yellow]Found {num_files} files to resize. Proceed? (y/n)[/bold yellow]")
        if get_char("   Choice: ").lower() != 'y':
            console.print("[yellow]Operation cancelled.[/yellow]")
            get_char("\nPress any key to continue...")
            return False

    success_count = 0
    fail_count = 0
    batch_start_time = time.perf_counter()
    converted_files = []
    original_resized_files = []
    
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
                futures = {executor.submit(resize_single_file, f, method, scale_val, target_aspect, fps=fps, strip_metadata=strip_metadata): f for f in files}
                
                for future in concurrent.futures.as_completed(futures):
                    name, success, error, duration = future.result()
                    if success:
                        success_count += 1
                        progress.console.print(f" [bold green]✓[/bold green] {name} [dim]→ {duration:.1f}s[/dim]")
                        orig_file = futures[future]
                        out_path = orig_file.parent / f"{orig_file.stem}_resized{orig_file.suffix}"
                        converted_files.append(out_path)
                        original_resized_files.append(orig_file)
                    else:
                        fail_count += 1
                        progress.console.print(f" [bold red]✗[/bold red] {name}: [dim]{error.strip()} ({duration:.1f}s)[/dim]")
                    progress.update(task, advance=1)
    else:
        for f in files:
            name, success, error, duration = resize_single_file(f, method, scale_val, target_aspect, fps=fps, strip_metadata=strip_metadata)
            if success:
                success_count += 1
                console.print(f" > {name}... [bold green]DONE[/bold green] [dim]({duration:.1f}s)[/dim]")
                out_path = f.parent / f"{f.stem}_resized{f.suffix}"
                converted_files.append(out_path)
                original_resized_files.append(f)
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
        prompt_move_files(console, get_char, get_input, converted_files, original_files=original_resized_files)
        return True
    else:
        get_char("\nPress any key to continue...")
        return False
