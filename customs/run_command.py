import subprocess

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
