import json
from pathlib import Path

SHORTCUTS_FILE = Path.home() / ".convergent_shortcuts.json"

def load_shortcuts():
    if SHORTCUTS_FILE.exists():
        try:
            with open(SHORTCUTS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_shortcuts(shortcuts):
    with open(SHORTCUTS_FILE, 'w') as f:
        json.dump(shortcuts, f, indent=4)
