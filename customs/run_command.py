import os
import sys
import subprocess
import threading
import contextvars
from collections import defaultdict
from pathlib import Path
from typing import Optional, Tuple

CURRENT_REQUEST_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("CURRENT_REQUEST_ID", default=None)
CURRENT_CANCEL_EVENT: contextvars.ContextVar[Optional[threading.Event]] = contextvars.ContextVar("CURRENT_CANCEL_EVENT", default=None)

_ACTIVE_PROCESSES = set()
_REQUEST_PROCESSES = defaultdict(set)
_PROCESSES_LOCK = threading.Lock()

def set_request_context(request_id: Optional[str] = None, cancel_event: Optional[threading.Event] = None):
    """Sets the current request context variables."""
    CURRENT_REQUEST_ID.set(request_id)
    CURRENT_CANCEL_EVENT.set(cancel_event)

def is_current_request_cancelled() -> bool:
    """Checks whether the active request has been cancelled."""
    evt = CURRENT_CANCEL_EVENT.get()
    return evt.is_set() if evt is not None else False

def terminate_active_processes(request_id: Optional[str] = None):
    """
    Terminates and kills child processes spawned by run_command.
    If request_id is provided, only terminates processes belonging to that request.
    Otherwise, terminates all active processes.
    """
    with _PROCESSES_LOCK:
        if request_id is not None:
            procs = list(_REQUEST_PROCESSES.get(request_id, []))
        else:
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
    if is_current_request_cancelled():
        return False, "Operation cancelled."

    req_id = CURRENT_REQUEST_ID.get()
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
            if req_id:
                _REQUEST_PROCESSES[req_id].add(proc)
        try:
            stdout, stderr = proc.communicate()
        finally:
            with _PROCESSES_LOCK:
                _ACTIVE_PROCESSES.discard(proc)
                if req_id and req_id in _REQUEST_PROCESSES:
                    _REQUEST_PROCESSES[req_id].discard(proc)
                    if not _REQUEST_PROCESSES[req_id]:
                        _REQUEST_PROCESSES.pop(req_id, None)

        if is_current_request_cancelled():
            return False, "Operation cancelled."

        if proc.returncode == 0:
            return True, ""
        else:
            err_msg = stderr.strip() or stdout.strip()
            if proc.returncode < 0:
                signal_desc = f"Process terminated by signal {-proc.returncode}"
                err_msg = f"{signal_desc}: {err_msg}" if err_msg else signal_desc
            elif not err_msg:
                err_msg = f"Process exited with code {proc.returncode}"
            if len(err_msg) > 1500:
                err_msg = err_msg[-1500:]
            return False, err_msg
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)


def run_command_output(cmd, cwd=None) -> Tuple[int, str, str]:
    """
    Unified command execution utility returning (returncode, stdout, stderr).
    Tracked by active processes registry and request context.
    """
    if is_current_request_cancelled():
        return -1, "", "Operation cancelled."

    req_id = CURRENT_REQUEST_ID.get()
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
            if req_id:
                _REQUEST_PROCESSES[req_id].add(proc)
        try:
            stdout, stderr = proc.communicate()
        finally:
            with _PROCESSES_LOCK:
                _ACTIVE_PROCESSES.discard(proc)
                if req_id and req_id in _REQUEST_PROCESSES:
                    _REQUEST_PROCESSES[req_id].discard(proc)
                    if not _REQUEST_PROCESSES[req_id]:
                        _REQUEST_PROCESSES.pop(req_id, None)

        return proc.returncode, stdout, stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)


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

