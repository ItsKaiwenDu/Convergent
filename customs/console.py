import sys
import os
import shlex

try:
    import tty
    import termios
    HAS_TERMIOS = True
except ImportError:
    tty = None
    termios = None
    HAS_TERMIOS = False

class MockConsole:
    def __init__(self, stderr=False):
        self.file = sys.stderr if stderr else sys.stdout

    def print(self, *args, **kwargs):
        import re
        msg = " ".join(map(str, args))
        msg = re.sub(r"\[.*?\]", "", msg)
        file_dest = kwargs.get('file', self.file)
        if 'end' in kwargs:
            print(msg, end=kwargs['end'], file=file_dest)
        else:
            print(msg, file=file_dest)
            
    def rule(self, title):
        file_dest = self.file
        print(f"\n{'='*20} {title} {'='*20}", file=file_dest)

try:
    from rich.console import Console
    console = Console()
except ImportError:
    console = MockConsole()

def set_stderr_mode(enabled=True):
    global console
    if enabled:
        if isinstance(console, MockConsole):
            console.file = sys.stderr
        else:
            console.file = sys.stderr
    else:
        if isinstance(console, MockConsole):
            console.file = sys.stdout
        else:
            console.file = sys.stdout

def get_input(prompt):
    try:
        if isinstance(console, MockConsole):
            import re
            clean_prompt = re.sub(r"\[.*?\]", "", prompt)
            return input(clean_prompt).strip()
        else:
            return console.input(prompt).strip()
    except EOFError:
        return ""

def get_char(prompt):
    console.print(prompt, end="")
    fd = sys.stdin.fileno()
    if not sys.stdin.isatty() or not HAS_TERMIOS:
        ch = sys.stdin.read(1)
        console.print(ch, end="")
        return ch
        
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    if ch == '\x03':
        raise KeyboardInterrupt
        
    console.print(ch, end="")
    return ch

def get_choice(prompt, choices=None, max_option=None):
    use_input = False
    if max_option is not None and max_option >= 10:
        use_input = True
    elif choices is not None:
        if isinstance(choices, int):
            if choices >= 10:
                use_input = True
        elif isinstance(choices, dict):
            for k in choices.keys():
                if (isinstance(k, int) and k >= 10) or len(str(k)) > 1:
                    use_input = True
                    break
        elif hasattr(choices, '__len__'):
            if len(choices) >= 10:
                use_input = True

    if use_input:
        return get_input(prompt)
    else:
        return get_char(prompt)

def prompt_fps():
    import time
    console.print("\n[bold yellow]Select FPS for GIF:[/bold yellow]")
    console.print(" 1. Original FPS")
    console.print(" 2. 30 FPS")
    console.print(" 3. 60 FPS")
    console.print(" [bold white]B[/bold white]. Back")
    fps_choice = get_char("\nSelect Option: ")
    if fps_choice.lower() == 'b':
        console.print()
        return "back", None
    elif fps_choice == '1':
        console.print()
        return "success", None
    elif fps_choice == '2':
        console.print()
        return "success", 30
    elif fps_choice == '3':
        console.print()
        return "success", 60
    else:
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return "invalid", None


def prompt_bitrate():
    import time
    console.print("\n[bold yellow]Select Audio Bitrate for MP3:[/bold yellow]")
    console.print(" 1. Default")
    console.print(" 2. 128k")
    console.print(" 3. 192k")
    console.print(" 4. 320k")
    console.print(" [bold white]B[/bold white]. Back")
    bitrate_choice = get_char("\nSelect Option: ")
    if bitrate_choice.lower() == 'b':
        console.print()
        return "back", None
    elif bitrate_choice == '1':
        console.print()
        return "success", None
    elif bitrate_choice == '2':
        console.print()
        return "success", "128k"
    elif bitrate_choice == '3':
        console.print()
        return "success", "192k"
    elif bitrate_choice == '4':
        console.print()
        return "success", "320k"
    else:
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return "invalid", None


def prompt_strip_metadata():
    import time
    console.print("\n[bold yellow]Strip metadata (EXIF/IPTC) for privacy?[/bold yellow]")
    console.print(" 1. Yes")
    console.print(" 2. No")
    console.print(" [bold white]B[/bold white]. Back")
    choice = get_char("\nSelect Option: ")
    if choice.lower() == 'b':
        console.print()
        return "back", False
    elif choice == '1':
        console.print()
        return "success", True
    elif choice == '2':
        console.print()
        return "success", False
    else:
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return "invalid", False


def clean_paths(path_str):
    if not path_str:
        return []
    if isinstance(path_str, list):
        resolved = []
        for item in path_str:
            resolved.extend(clean_paths(item))
        return resolved
    
    path_str = path_str.replace("\n", "").replace("\r", "").replace("\t", "").strip()
    
    if path_str == "-":
        return ["-"]
    
    # If entire path_str exists as a single file or directory, treat it as one path.
    # This prevents splitting a single path that has spaces but no quotes/escapes.
    try:
        if os.path.exists(os.path.expanduser(path_str)):
            return [path_str]
    except:
        pass
        
    try:
        # Handle shell-escaped paths, quoted paths, and multiple paths separated by spaces
        # shlex.split correctly handles cases like 'History\ \&\ Practice.pdf'
        # or multiple paths like '/path/1' '/path/2' or '/path/1 /path/2'
        if " " in path_str or "\\" in path_str or "'" in path_str or '"' in path_str:
            parts = shlex.split(path_str)
            if parts:
                return [p.strip() for p in parts if p.strip()]
    except:
        pass
    
    # Fallback to manual stripping of quotes if shlex fails or no special chars
    return [path_str.strip("'").strip('"').strip()]


def flush_stdin():
    if termios is not None:
        try:
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except:
            pass


def prompt_paths(action: str, allow_folders: bool = True):
    target_type = "file or folder" if allow_folders else "file"
    console.print(f"\n[bold yellow]Enter {target_type} path(s) to {action}:[/bold yellow]")
    console.print("[dim](Tip: You can either paste or drag and drop here)[/dim]")
    flush_stdin()
    paths = clean_paths(get_input("Path: "))
    flush_stdin()
    return paths

