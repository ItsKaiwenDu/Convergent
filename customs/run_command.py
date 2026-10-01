import os
import sys
import subprocess
import threading
from pathlib import Path

_ACTIVE_PROCESSES = set()
_PROCESSES_LOCK = threading.Lock()

def terminate_active_processes():
    """
    Terminates and kills all active child processes spawned by run_command.
    Useful for clean cancellation handling in MCP servers or signals.
    """
    with _PROCESSES_LOCK:
        procs = list(_ACTIVE_PROCESSES)
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    for p in procs:
        try:
            p.kill()
        except Exception:
            pass

def run_command(cmd, cwd=None):
    """
    Unified command execution utility.
    
    Args:
        cmd (list): The command to run as a list of strings.
        cwd (str, optional): The working directory to run command in.
        
    Returns:
        tuple: (success (bool), error_message (str))
    """
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            cwd=cwd,
        )
        with _PROCESSES_LOCK:
            _ACTIVE_PROCESSES.add(proc)
        try:
            stdout, stderr = proc.communicate()
        finally:
            with _PROCESSES_LOCK:
                _ACTIVE_PROCESSES.discard(proc)

        if proc.returncode == 0:
            return True, ""
        else:
            err_msg = stderr.strip() or stdout.strip()
            if len(err_msg) > 1500:
                err_msg = err_msg[-1500:]
            return False, err_msg
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
        path (str or Path): The path to file or directory to move to Trash.
        
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
            result = subprocess.run(["trash", str(path)], capture_output=True, stdin=subprocess.DEVNULL, text=True)
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
            result = subprocess.run(["osascript", "-e", applescript], capture_output=True, stdin=subprocess.DEVNULL, text=True)
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
            result = subprocess.run(["gio", "trash", str(path)], capture_output=True, stdin=subprocess.DEVNULL, text=True)
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
            result = subprocess.run(["trash-put", str(path)], capture_output=True, stdin=subprocess.DEVNULL, text=True)
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

