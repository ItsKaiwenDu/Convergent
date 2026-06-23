import argparse
import json
import plistlib
import subprocess
import sys
import uuid
from pathlib import Path

SHORTCUTS_FILE = Path.home() / ".convergent_shortcuts.json"
SERVICES_DIR = Path.home() / "Library" / "Services"

def load_shortcuts():
    if not SHORTCUTS_FILE.exists():
        return {}
    try:
        with open(SHORTCUTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def build_shell_command(convergent_dir: str, shortcut_key: str) -> str:
    escaped_dir = convergent_dir.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f'CONVERGENT_DIR="{escaped_dir}"\n'
        f'SHORTCUT_KEY="{shortcut_key}"\n'
        'TMP="$(mktemp /tmp/convergent-qa-XXXXXX.command)"\n'
        '{\n'
        '  echo "#!/bin/bash"\n'
        '  echo "cd \\"$CONVERGENT_DIR\\" || exit 1"\n'
        '  printf "python3 Convergent.py --shortcut %s --path" "$SHORTCUT_KEY"\n'
        '  for f in "$@"; do\n'
        '    printf " %q" "$f"\n'
        '  done\n'
        '  echo\n'
        '} > "$TMP"\n'
        'chmod +x "$TMP"\n'
        'open "$TMP"\n'
    )

def write_workflow(service_path: Path, service_name: str, convergent_dir: str, shortcut_key: str):
    service_path.mkdir(parents=True, exist_ok=True)
    contents = service_path / "Contents"
    contents.mkdir(exist_ok=True)

    info_plist = {
        "NSServices": [
            {
                "NSMenuItem": {"default": service_name},
                "NSMessage": "runWorkflowAsService",
                "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
                "NSSendFileTypes": ["public.item", "public.folder"],
            }
        ]
    }
    with open(contents / "Info.plist", "wb") as f:
        plistlib.dump(info_plist, f)

    action_uuid = str(uuid.uuid4()).upper()
    input_uuid = str(uuid.uuid4()).upper()
    output_uuid = str(uuid.uuid4()).upper()

    wflow = {
        "AMApplicationBuild": "521.1",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [
            {
                "action": {
                    "AMAccepts": {
                        "Container": "List",
                        "Optional": True,
                        "Types": ["com.apple.cocoa.path"],
                    },
                    "AMActionVersion": "2.0.3",
                    "AMApplication": ["Automator"],
                    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                    "ActionName": "Run Shell Script",
                    "ActionParameters": {
                        "COMMAND_STRING": build_shell_command(convergent_dir, shortcut_key),
                        "CheckedForUserDefaultShell": True,
                        "inputMethod": 1,
                        "shell": "/bin/bash",
                        "source": "",
                    },
                    "BundleIdentifier": "com.apple.RunShellScript",
                    "CFBundleVersion": "2.0.3",
                    "CanShowSelectedItemsWhenRun": False,
                    "CanShowWhenRun": True,
                    "Category": ["AMCategoryUtilities"],
                    "Class Name": "RunShellScriptAction",
                    "InputUUID": input_uuid,
                    "OutputUUID": output_uuid,
                    "UUID": action_uuid,
                    "UnlockPlugin": False,
                    "arguments": {},
                    "isViewVisible": 1,
                    "location": "309.500000:253.000000",
                    "nibPath": "/System/Library/Automator/Run Shell Script.action/Contents/Resources/English.lproj/main.nib",
                },
                "isViewVisible": 1,
            }
        ],
        "connectors": {},
        "workflowMetaData": {
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceApplicationPath": "/System/Library/CoreServices/Finder.app",
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": 0,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }
    with open(contents / "document.wflow", "wb") as f:
        plistlib.dump(wflow, f)

def register_service():
    pbs = Path("/System/Library/CoreServices/pbs")
    if pbs.exists():
        subprocess.run([str(pbs), "-update"], check=False)
    subprocess.run(["killall", "Finder"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def pick_shortcut(shortcuts, key=None):
    if key:
        key = key.strip().upper()
        if key not in shortcuts:
            print(f"Error: Shortcut '{key}' not found in {SHORTCUTS_FILE}", file=sys.stderr)
            sys.exit(1)
        return key, shortcuts[key]

    if not shortcuts:
        print(
            "No saved shortcuts found.\n"
            "Run `make start`, press + to create a shortcut, then run `make quick-action` again.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Saved shortcuts:")
    keys = sorted(shortcuts.keys())
    for sym in keys:
        print(f"  [{sym}] {shortcuts[sym]['title']}")

    while True:
        choice = input("\nShortcut key to bind: ").strip().upper()
        if choice in shortcuts:
            return choice, shortcuts[choice]
        print("Invalid key. Choose one of:", ", ".join(keys))

def main():
    parser = argparse.ArgumentParser(description="Install a Finder Quick Action for a Convergent shortcut.")
    parser.add_argument("--repo", required=True, help="Absolute path to the Convergent repository")
    parser.add_argument("--key", help="Shortcut key symbol (e.g. S). Prompts if omitted.")
    parser.add_argument("--name", help="Quick Action menu label. Defaults to 'Convergent: <shortcut title>'.")
    args = parser.parse_args()

    if sys.platform != "darwin":
        print("Error: Finder Quick Actions are macOS only.", file=sys.stderr)
        sys.exit(1)

    repo = Path(args.repo).resolve()
    if not (repo / "Convergent.py").exists():
        print(f"Error: Convergent.py not found in {repo}", file=sys.stderr)
        sys.exit(1)

    shortcuts = load_shortcuts()
    shortcut_key, shortcut = pick_shortcut(shortcuts, args.key)
    service_name = args.name or f"Convergent: {shortcut['title']}"

    service_path = SERVICES_DIR / f"{service_name}.workflow"
    if service_path.exists():
        answer = input(f"\n'{service_name}' already exists. Replace it? (y/n): ").strip().lower()
        if answer != "y":
            print("Cancelled.")
            sys.exit(0)

    write_workflow(service_path, service_name, str(repo), shortcut_key)
    register_service()

    print(f"\nInstalled Quick Action: {service_path}")
    print(f"Shortcut key: [{shortcut_key}] {shortcut['title']}")
    print("\nIn Finder, right-click file(s) or folder(s) → Quick Actions →", service_name)
    print("\nTo remove:")
    print(f"  rm -rf '{service_path}'")
    print("  /System/Library/CoreServices/pbs -update && killall Finder")

if __name__ == "__main__":
    main()
