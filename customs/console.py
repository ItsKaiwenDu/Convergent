import sys

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
        return input(prompt).strip()
    except EOFError:
        return ""

def get_char(prompt):
    console.print(prompt, end="")
    fd = sys.stdin.fileno()
    if not sys.stdin.isatty():
        ch = sys.stdin.read(1)
        console.print(ch, end="")
        return ch
        
    import tty, termios
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
