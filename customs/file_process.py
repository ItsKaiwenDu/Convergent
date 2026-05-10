import os
import time
import concurrent.futures
import multiprocessing
from pathlib import Path

def process_single_file(conv, f, target_format, fps=None):
    """
    Processes a single file conversion using the provided Converter instance.
    """
    source_fmt = f.suffix.lower()[1:].upper()
    
    if target_format not in conv.formats.get(source_fmt, []):
        if source_fmt == target_format:
            return f.name, True, "Skipped (Same format)"
        return f.name, False, f"Target {target_format} not supported for {source_fmt}"

    success = False
    error = ""
    
    if source_fmt == "HEIC":
        success, error = conv.convert_heic(f, target_format)
    elif source_fmt in ["MOV", "MP4", "WEBM", "GIF", "AVI"]:
        success, error = conv.convert_video(f, target_format, fps=fps)
    elif source_fmt in ["WAV", "M4A", "MP3"]:
        success, error = conv.convert_audio(f, target_format)
    elif source_fmt in ["DOCX", "PPTX", "RTF"]:
        success, error = conv.convert_office(f, target_format)
    elif source_fmt in ["JPG", "PNG", "WEBP"]:
        success, error = conv.convert_image(f, target_format)
        
    return f.name, success, error

def process(conv, console, get_char, source_formats, target_format, paths, fps=None, jobs=None, overwrite=False, skip=False):
    """
    Processes a batch of files for conversion.
    """
    if isinstance(paths, str):
        paths = [paths]
        
    files = []
    source_fmts_upper = [fmt.upper() for fmt in source_formats]
    
    for p in paths:
        path_obj = Path(os.path.expanduser(p))
        if path_obj.is_file():
            ext = path_obj.suffix.lower()[1:].upper()
            if ext in source_fmts_upper:
                files.append(path_obj)
        elif path_obj.is_dir():
            for item in path_obj.iterdir():
                if item.is_file():
                    ext = item.suffix.lower()[1:].upper()
                    if ext in source_fmts_upper:
                        files.append(item)
    
    if not files:
        console.print(f"[bold red]No matching files found in the provided paths.[/bold red]")
        return

    collisions = []
    for f in files:
        output = f.with_suffix(f".{target_format.lower()}")
        if output.exists():
            collisions.append(f)
    
    if collisions and not overwrite and not skip:
        console.print(f"\n[bold yellow]⚠  {len(collisions)} files already exist at the target path.[/bold yellow]")
        console.print("   [bold][O][/bold] Overwrite all   [bold][S][/bold] Skip existing   [bold][C][/bold] Cancel")
        
        while True:
            choice = get_char("   Choice: ").lower()
            if choice == 'o':
                console.print()
                overwrite = True
                break
            elif choice == 's':
                console.print()
                skip = True
                break
            elif choice == 'c':
                console.print()
                console.print("[yellow]Operation cancelled.[/yellow]")
                return
            else:
                console.print(" [dim]Invalid choice[/dim]")
                time.sleep(0.5)
    
    if skip:
        original_count = len(files)
        files = [f for f in files if not f.with_suffix(f".{target_format.lower()}").exists()]
        skipped_count = original_count - len(files)
        if skipped_count > 0:
            console.print(f"[dim]Skipped {skipped_count} already existing files.[/dim]")

    if not files:
        console.print("[bold green]All files already exist and were skipped.[/bold green]")
        return

    num_files = len(files)
    if num_files > 50:
        console.print(f"\n[bold yellow]Found {num_files} files. Proceed? (y/n)[/bold yellow]")
        if get_char("   Choice: ").lower() != 'y':
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

    console.print(f"[bold cyan]Found {num_files} files to convert...[/bold cyan]")
    
    if not jobs:
        jobs = min(multiprocessing.cpu_count(), len(files))
        
    success_count = 0
    
    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Converting to {target_format}...", total=len(files))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
                futures = {executor.submit(process_single_file, conv, f, target_format, fps): f for f in files}
                
                for future in concurrent.futures.as_completed(futures):
                    name, success, error = future.result()
                    if success:
                        success_count += 1
                        if error != "Skipped (Same format)":
                            progress.console.print(f" [bold green]✓[/bold green] {name}")
                    else:
                        progress.console.print(f" [bold red]✗[/bold red] {name}: [dim]{error.strip()}[/dim]")
                    progress.update(task, advance=1)
    except ImportError:
        # Fallback for systems without rich
        for f in files:
            name, success, error = process_single_file(conv, f, target_format, fps)
            if success:
                success_count += 1
                if error != "Skipped (Same format)":
                    console.print(f" > {name}... [bold green]DONE[/bold green]")
            else:
                console.print(f" > {name}... [bold red]FAILED[/bold red]")
                if error:
                    console.print(f"   [dim]{error.strip()}[/dim]")
    
    console.print(f"\n[bold green]Finished! Successfully converted {success_count} files.[/bold green]")
