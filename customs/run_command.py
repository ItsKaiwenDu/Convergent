import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, cwd=None):
    """
    Unified command execution utility.
    
    Args:
        cmd (list): The command to run as a list of strings.
        cwd (str, optional): The working directory to run the command in.
        
    Returns:
        tuple: (success (bool), error_message (str))
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)

def send_to_trash(path):
    """
    Moves a file or directory to macOS/Linux Trash using platform-specific commands.
    On macOS: uses `trash` CLI or AppleScript Finder integration.
    On Linux: uses `gio trash` or `trash-put` (trash-cli package).
    
    Args:
        path (str or Path): The path to the file or directory to move to Trash.
        
    Returns:
        bool: True if successfully trashed, not on macOS/Linux, or did not exist. False otherwise.
    """
    try:
        path = Path(os.path.expanduser(path)).resolve()
    except Exception:
        return False
        
    if not (path.exists() or path.is_symlink()):
        return True
        
    if sys.platform == "darwin":
        # Attempt using `trash` CLI utility
        try:
            result = subprocess.run(["trash", str(path)], capture_output=True, text=True)
            if result.returncode == 0:
                try:
                    from customs.console import console
                    console.print(f"[dim]Moved to Trash: {path.name}[/dim]")
                except Exception:
                    pass
                return True
        except FileNotFoundError:
            pass
        except Exception:
            pass
            
        # Fallback to AppleScript Finder delete
        try:
            escaped_path = str(path).replace('\\', '\\\\').replace('"', '\\"')
            applescript = f'tell application "Finder" to delete POSIX file "{escaped_path}"'
            result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)
            if result.returncode == 0:
                try:
                    from customs.console import console
                    console.print(f"[dim]Moved to Trash: {path.name}[/dim]")
                except Exception:
                    pass
                return True
        except Exception:
            pass
            
        return False

    elif sys.platform.startswith("linux"):
        # Attempt using `gio trash`
        try:
            result = subprocess.run(["gio", "trash", str(path)], capture_output=True, text=True)
            if result.returncode == 0:
                try:
                    from customs.console import console
                    console.print(f"[dim]Moved to Trash: {path.name}[/dim]")
                except Exception:
                    pass
                return True
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Fallback to `trash-put` from trash-cli
        try:
            result = subprocess.run(["trash-put", str(path)], capture_output=True, text=True)
            if result.returncode == 0:
                try:
                    from customs.console import console
                    console.print(f"[dim]Moved to Trash: {path.name}[/dim]")
                except Exception:
                    pass
                return True
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Warning when both fail on Linux
        try:
            from customs.console import console
            console.print(f"[yellow]⚠ Warning: Could not trash '{path.name}'. Make sure 'trash-cli' or 'gio' is installed.[/yellow]")
        except Exception:
            pass
        return False

    return True

