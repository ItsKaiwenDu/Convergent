import os
import subprocess
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

def run_command(cmd, cwd=None):
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

def compress(path, output_name, format_choice, password=None):
    path_obj = Path(os.path.expanduser(path)).resolve()
    if not path_obj.exists():
        return False, f"Path does not exist: {path}"
    
    # Ensure output name has correct extension
    if format_choice == "ZIP" and not output_name.lower().endswith(".zip"):
        output_name += ".zip"
    elif format_choice == "TAR.GZ" and not (output_name.lower().endswith(".tar.gz") or output_name.lower().endswith(".tgz")):
        output_name += ".tar.gz"
        
    output_path = path_obj.parent / output_name
    cwd = path_obj.parent
    
    if format_choice == "ZIP":
        if password:
            # -r for recursive, -P for password
            cmd = ["zip", "-P", password, "-r", str(output_path), path_obj.name]
        else:
            cmd = ["zip", "-r", str(output_path), path_obj.name]
    elif format_choice == "TAR.GZ":
        # -c create, -z gzip, -f file
        cmd = ["tar", "-czf", str(output_path), path_obj.name]
    else:
        return False, f"Unsupported format: {format_choice}"

    return run_command(cmd, cwd=cwd)
