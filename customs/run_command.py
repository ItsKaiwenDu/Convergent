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
    Moves a file or directory to macOS Trash using the trash CLI or osascript Finder integration.
    Only active on macOS (sys.platform == 'darwin').
    
    Args:
        path (str or Path): The path to the file or directory to move to Trash.
        
    Returns:
        bool: True if successfully trashed, not on macOS, or did not exist. False otherwise.
    """
    if sys.platform != "darwin":
        return True
        
    try:
        path = Path(os.path.expanduser(path)).resolve()
    except Exception:
        return False
        
    if not (path.exists() or path.is_symlink()):
        return True
        
    # Attempt using `trash` CLI utility
    try:
        result = subprocess.run(["trash", str(path)], capture_output=True, text=True)
        if result.returncode == 0:
            try:
                from customs.console import console
                console.print(f"[dim]Original moved to Trash: {path.name}[/dim]")
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
                console.print(f"[dim]Original moved to Trash: {path.name}[/dim]")
            except Exception:
                pass
            return True
    except Exception:
        pass
        
    return False

