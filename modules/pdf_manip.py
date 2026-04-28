import os
import subprocess
import sys
from pathlib import Path

try:
    from rich.console import Console
    console = Console()
except ImportError:
    class MockConsole:
        def print(self, *args, **kwargs):
            import re
            msg = " ".join(map(str, args))
            msg = re.sub(r"\[.*?\]", "", msg)
            if 'end' in kwargs: print(msg, end=kwargs['end'])
            else: print(msg)
    console = MockConsole()

def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)

def get_input(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""

def get_char(prompt):
    import tty, termios
    console.print(prompt, end="")
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    if ch == '\x03':
        raise KeyboardInterrupt
    console.print(ch)
    return ch

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

def combine_pdfs(path):
    path_obj = Path(os.path.expanduser(path))
    if not path_obj.is_dir():
        console.print("[bold red]Error: PDF Combiner requires a directory path.[/bold red]")
        return
    pdf_files = sorted([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"])
    if not pdf_files:
        console.print("[bold red]No PDF files found in the directory.[/bold red]")
        return
    console.print(f"[bold cyan]Found {len(pdf_files)} PDF files to combine...[/bold cyan]")
    output_name = get_input("\nEnter name for combined PDF (default: combined.pdf): ")
    if not output_name:
        output_name = "combined.pdf"
    if not output_name.endswith(".pdf"):
        output_name += ".pdf"
    output_path = path_obj / output_name
    cmd = ["gs", "-dNOPAUSE", "-sDEVICE=pdfwrite", f"-sOUTPUTFILE={output_path}", "-dBATCH"] + [str(f) for f in pdf_files]
    success, error = run_command(cmd)
    if success:
        console.print(f"[bold green]Successfully combined into {output_name}[/bold green]")
    else:
        console.print(f"[bold red]FAILED to combine PDFs[/bold red]")
        if "command not found" in error:
            console.print("   [bold yellow]Error: 'ghostscript' is required for PDF operations.[/bold yellow]")
            console.print("   [dim]Install via: brew install ghostscript[/dim]")
        elif error:
            console.print(f"   [dim]{error.strip()}[/dim]")

def split_pdf(path):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".pdf":
        console.print(f"[bold red]Error: Could not find PDF at: [white]{path}[/white][/bold red]")
        return
    total_pages = get_pdf_page_count(str(path_obj))
    if total_pages == 0:
        console.print("[bold red]Error: Could not determine PDF page count or file is empty.[/bold red]")
        return
    console.print(f"\n[bold yellow]Split Options for '{path_obj.name}' ({total_pages} pages):[/bold yellow]")
    console.print(" 1. Individual Pages (every page becomes its own PDF)")
    console.print(" 2. Custom Split (e.g., 1-5, 6-10...)")
    console.print(" 3. Split into N parts")
    mode = get_char("\nPick a #: ")
    output_dir = path_obj.parent / f"{path_obj.stem}_split"
    output_dir.mkdir(exist_ok=True)
    if mode == '1':
        console.print(f"[bold cyan]Splitting into {total_pages} individual pages...[/bold cyan]")
        output_pattern = output_dir / "page_%03d.pdf"
        cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(output_pattern), str(path_obj)]
        success, error = run_command(cmd)
        if success: console.print(f"[bold green]Successfully split into {output_dir.name}/[/bold green]")
        else: console.print(f"[bold red]FAILED to split PDF[/bold red]")
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
            return
        for idx, (start, end) in enumerate(ranges, 1):
            out_file = output_dir / f"part_{idx}_{start}-{end}.pdf"
            cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(out_file), f"-dFirstPage={start}", f"-dLastPage={end}", str(path_obj)]
            success, _ = run_command(cmd)
            if success: console.print(f" > Part {idx} (Pages {start}-{end}): [bold green]DONE[/bold green]")
        console.print(f"\n[bold green]Custom split finished! Files are in {output_dir.name}/[/bold green]")
    elif mode == '3':
        num_str = get_input("Number of PDFs: ")
        try:
            num_parts = int(num_str)
            if num_parts < 1 or num_parts > total_pages: raise ValueError
        except ValueError:
            console.print("[bold red]Invalid input.[/bold red]")
            return
        base_size = total_pages // num_parts
        remainder = total_pages % num_parts
        current_page = 1
        for i in range(num_parts):
            count = base_size + (1 if i < remainder else 0)
            end_page = current_page + count - 1
            out_file = output_dir / f"part_{i+1}_{current_page}-{end_page}.pdf"
            cmd = ["gs", "-sDEVICE=pdfwrite", "-o", str(out_file), f"-dFirstPage={current_page}", f"-dLastPage={end_page}", str(path_obj)]
            success, _ = run_command(cmd)
            if success: console.print(f" > Part {i+1} (Pages {current_page}-{end_page}): [bold green]DONE[/bold green]")
            current_page = end_page + 1
        console.print(f"\n[bold green]Split finished! Files are in {output_dir.name}/[/bold green]")
