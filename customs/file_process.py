import os
import time
import concurrent.futures
import multiprocessing
from pathlib import Path

def process_single_file(conv, f, target_format, fps=None, bitrate=None):
    """
    Processes a single file conversion using the provided Converter instance.
    """
    start_time = time.perf_counter()
    source_fmt = f.suffix.lower()[1:].upper()
    
    if target_format not in conv.formats.get(source_fmt, []):
        duration = time.perf_counter() - start_time
        if source_fmt == target_format:
            return f.name, True, "Skipped (Same format)", duration
        return f.name, False, f"Target {target_format} not supported for {source_fmt}", duration

    success = False
    error = ""
    
    if source_fmt == "HEIC":
        success, error = conv.convert_heic(f, target_format)
    elif source_fmt in ["MOV", "MP4", "WEBM", "GIF", "AVI"]:
        success, error = conv.convert_video(f, target_format, fps=fps, bitrate=bitrate)
    elif source_fmt in ["WAV", "M4A", "MP3"]:
        success, error = conv.convert_audio(f, target_format, bitrate=bitrate)
    elif source_fmt in ["DOCX", "PPTX", "RTF"]:
        success, error = conv.convert_office(f, target_format)
    elif source_fmt == "PDF":
        success, error = conv.convert_pdf(f, target_format)
    elif source_fmt in ["JPG", "PNG", "WEBP", "ARW", "DNG"]:
        success, error = conv.convert_image(f, target_format)
    
    duration = time.perf_counter() - start_time
    return f.name, success, error, duration

def process(conv, console, get_char, source_formats, target_format, paths, fps=None, bitrate=None, jobs=None, overwrite=False, skip=False):
    """
    Processes a batch of files for conversion.
    """
    if isinstance(paths, str):
        paths = [paths]
        
    files = []
    source_fmts_upper = [fmt.upper() for fmt in source_formats]
    found_extensions = set()
    
    for p in paths:
        path_obj = Path(os.path.expanduser(p))
        if path_obj.is_file():
            ext = path_obj.suffix.lower()[1:].upper()
            if ext in source_fmts_upper:
                files.append(path_obj)
            else:
                if path_obj.suffix:
                    found_extensions.add(path_obj.suffix.lower())
        elif path_obj.is_dir():
            for item in path_obj.iterdir():
                if item.is_file():
                    ext = item.suffix.lower()[1:].upper()
                    if ext in source_fmts_upper:
                        files.append(item)
                    if item.suffix:
                        found_extensions.add(item.suffix.lower())
    
    if not files:
        if len(source_formats) == 1:
            msg = f"No {source_formats[0]} files found in the provided paths."
        else:
            msg = "No matching files found in the provided paths."
        
        if found_extensions:
            sorted_exts = sorted(list(found_extensions))
            msg += f" Found: {', '.join(sorted_exts)}"
            
        console.print(f"[bold red]{msg}[/bold red]")
        return

    final_files = []
    temp_symlinks = {}
    
    try:
        for f in files:
            output = f.with_suffix(f".{target_format.lower()}")
            if output.exists() and not overwrite and not skip:
                console.print(f"\n[bold yellow]⚠  File already exists: {output.name}[/bold yellow]")
                console.print("   [bold][O][/bold] Overwrite   [bold][S][/bold] Skip   [bold][K][/bold] Keep both   [bold][C][/bold] Cancel")
                
                while True:
                    choice = get_char("   Choice: ").lower()
                    if choice == 'o':
                        console.print()
                        final_files.append(f)
                        break
                    elif choice == 's':
                        console.print()
                        break
                    elif choice == 'k':
                        console.print()
                        counter = 1
                        stem = f.stem
                        suffix = f.suffix
                        target_suffix = f".{target_format.lower()}"
                        while True:
                            candidate_output = f.parent / f"{stem} ({counter}){target_suffix}"
                            if not candidate_output.exists():
                                break
                            counter += 1
                        
                        temp_source = f.parent / f"{stem} ({counter}){suffix}"
                        try:
                            if temp_source.exists() or temp_source.is_symlink():
                                temp_source.unlink()
                            os.symlink(f.name, str(temp_source))
                            final_files.append(temp_source)
                            temp_symlinks[temp_source] = f
                            console.print(f"   [dim]Will save as: {candidate_output.name}[/dim]")
                        except Exception as e:
                            console.print(f"   [bold red]Error creating temporary file: {e}[/bold red]")
                        break
                    elif choice == 'c':
                        console.print()
                        console.print("[yellow]Operation cancelled.[/yellow]")
                        return
                    else:
                        console.print(" [dim]Invalid choice[/dim]")
                        time.sleep(0.5)
            else:
                if output.exists():
                    if overwrite:
                        final_files.append(f)
                else:
                    final_files.append(f)
        
        skipped_count = len(files) - len(final_files)
        if skipped_count > 0 and skip:
            console.print(f"[dim]Skipped {skipped_count} already existing files.[/dim]")
                
        files = final_files
        
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
        fail_count = 0
        batch_start_time = time.perf_counter()
        
        try:
            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
            
            actual_source_formats = sorted(list(set(f.suffix.lower()[1:].upper() for f in files if f.suffix)))
            if not actual_source_formats:
                actual_source_formats = [fmt.upper() for fmt in source_formats]
            source_label = " + ".join(actual_source_formats) if actual_source_formats else "Files"
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"{source_label} → {target_format}...", total=len(files))
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
                    futures = {executor.submit(process_single_file, conv, f, target_format, fps, bitrate): f for f in files}
                    
                    for future in concurrent.futures.as_completed(futures):
                        name, success, error, duration = future.result()
                        if success:
                            success_count += 1
                            if error != "Skipped (Same format)":
                                progress.console.print(f" [bold green]✓[/bold green] {name} [dim]→ {duration:.1f}s[/dim]")
                        else:
                            fail_count += 1
                            progress.console.print(f" [bold red]✗[/bold red] {name}: [dim]{error.strip()} ({duration:.1f}s)[/dim]")
                        progress.update(task, advance=1)
        except ImportError:
            # Fallback for systems without rich
            for f in files:
                name, success, error, duration = process_single_file(conv, f, target_format, fps, bitrate)
                if success:
                    success_count += 1
                    if error != "Skipped (Same format)":
                        console.print(f" > {name}... [bold green]DONE[/bold green] [dim]({duration:.1f}s)[/dim]")
            else:
                fail_count += 1
                console.print(f" > {name}... [bold red]FAILED[/bold red] [dim]({duration:.1f}s)[/dim]")
                if error:
                    console.print(f"   [dim]{error.strip()}[/dim]")
        
        total_time = time.perf_counter() - batch_start_time
        summary_parts = [
            f"[bold green]✓ {success_count} converted[/bold green]",
            f"[bold red]✗ {fail_count} failed[/bold red]"
        ]
        if skipped_count > 0:
            summary_parts.append(f"[bold yellow]↷ {skipped_count} skipped[/bold yellow]")
        summary_parts.append(f"[bold cyan]⏱ {total_time:.1f}s total[/bold cyan]")
        
        console.print(f"\n{', '.join(summary_parts)}")
    finally:
        for sym in temp_symlinks:
            try:
                sym.unlink()
            except:
                pass
