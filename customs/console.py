import sys

try:
    import tty
    import termios
    HAS_TERMIOS = True
except ImportError:
    tty = None
    termios = None
    HAS_TERMIOS = False

class MockConsole:
    def print(self, *args, **kwargs):
        import re
        msg = " ".join(map(str, args))
        msg = re.sub(r"\[.*?\]", "", msg)
        if 'end' in kwargs:
            print(msg, end=kwargs['end'])
        else:
            print(msg)
            
    def rule(self, title):
        print(f"\n{'='*20} {title} {'='*20}")

try:
    from rich.console import Console
    console = Console()
except ImportError:
    console = MockConsole()

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

