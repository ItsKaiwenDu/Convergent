import json
import os
import time
from pathlib import Path

SHORTCUTS_FILE = Path.home() / ".convergent_shortcuts.json"
MENU_LABEL_WIDTH = 14
CONVERT_MENU_KEYS = [("3", "2"), ("4", "3"), ("5", "4"), ("6", "5")]
COMPRESS_FORMATS = [
    ("1", "7Z"),
    ("2", "RAR"),
    ("3", "TAR.BZ2"),
    ("4", "TAR.GZ"),
    ("5", "TAR.XZ"),
    ("6", "ZIP"),
]

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

def get_menu_entries(conv):
    entries = [
        {"key": "0", "label": "Combine:", "exts": "gif, mp3, mp4, pdf", "operation": "combine"},
        {"key": "1", "label": "Split:", "exts": "gif, mp3, mp4, pdf", "operation": "split"},
        {"key": "2", "label": "Resize:", "exts": "mp4, jpg, png, heic", "operation": "resize"},
    ]
    for key, cat_id in CONVERT_MENU_KEYS:
        cat = conv.categories[cat_id]
        entries.append({
            "key": key,
            "label": f"{cat['name']}:",
            "exts": ", ".join(cat["extensions"]).lower(),
            "operation": "convert",
            "category_id": cat_id,
        })
    entries.extend([
        {"key": "7", "label": "Compress:", "exts": "7z, rar, tar.(gz/bz2/xz), zip", "operation": "compress"},
        {"key": "8", "label": "Decompress:", "exts": "7z, rar, tar.(gz/bz2/xz), zip", "operation": "decompress"},
    ])
    return entries

def get_menu_entry(conv, key):
    for entry in get_menu_entries(conv):
        if entry["key"] == key:
            return entry
    return None

def print_source_menu(console, conv, title):
    console.print(title)
    for entry in get_menu_entries(conv):
        console.print(
            f" [bold cyan]{entry['key']}.[/bold cyan] "
            f"{entry['label'].ljust(MENU_LABEL_WIDTH)} {entry['exts']}"
        )

def get_operation_label(sc, conv):
    operation = sc.get("operation", "convert")
    if operation == "convert":
        return conv.categories[sc["category"]]["name"]
    return operation.title()

def prompt_compress_format(console, get_char):
    console.print("\n[bold yellow]Select target format:[/bold yellow]")
    for key, fmt in COMPRESS_FORMATS:
        console.print(f" {key}. {fmt.lower()}")
    console.print(" [bold white]B[/bold white]. Back")
    fmt_choice = get_char("\nPick a #: ")
    if fmt_choice.lower() == 'b':
        return None
    for key, fmt in COMPRESS_FORMATS:
        if fmt_choice == key:
            return fmt
    return False

def _prompt_shortcut_identity(console, get_input, get_char):
    sym = get_input("\nInput a single symbol/key for this shortcut (e.g., 'S'): ").strip().upper()
    reserved_keys = [str(i) for i in range(10)] + ['+', '-', '=', 'Q']
    if sym in reserved_keys:
        console.print(f"\n[bold red][!] '{sym}' is a reserved key. Please choose a letter not in: {' '.join(reserved_keys)}[/bold red]")
        get_char("\nPress any key to continue...")
        return None, None
    title = get_input("Input a label title (e.g., 'Quick JPG Convert'): ").strip()
    if not sym or not title:
        return None, None
    return sym, title

def _prompt_fixed_path(console, get_char, get_input, flush_stdin, clean_paths):
    console.print(f"\n[bold yellow]Do you want to fix a file/folder path for this shortcut? (y/n)[/bold yellow]")
    fix_path = get_char("Choice: ")
    fixed_path = ""
    if fix_path.lower() == 'y':
        flush_stdin()
        fixed_paths = clean_paths(get_input("\nEnter path: "))
        fixed_path = " ".join([f'"{p}"' for p in fixed_paths]) if fixed_paths else ""
        flush_stdin()
    return fixed_path

def _collect_convert_options(console, get_char, category_id, target_fmt):
    bitrate = "ask"
    if target_fmt == "MP3":
        console.print("\n[bold yellow]Select Audio Bitrate for MP3:[/bold yellow]")
        console.print(" 1. Ask every time")
        console.print(" 2. Default")
        console.print(" 3. 128k")
        console.print(" 4. 192k")
        console.print(" 5. 320k")
        bitrate_choice = get_char("\nPick a #: ")
        if bitrate_choice == '1':
            bitrate = "ask"
        elif bitrate_choice == '2':
            bitrate = "default"
        elif bitrate_choice == '3':
            bitrate = "128k"
        elif bitrate_choice == '4':
            bitrate = "192k"
        elif bitrate_choice == '5':
            bitrate = "320k"
        else:
            console.print("\n [dim]Invalid choice. Defaulting to 'Ask every time'[/dim]")
            bitrate = "ask"
            time.sleep(0.5)
        console.print()

    strip_metadata = "ask"
    if category_id == "2":
        console.print("\n[bold yellow]Select Metadata Stripping for Images:[/bold yellow]")
        console.print(" 1. Ask every time")
        console.print(" 2. Always strip")
        console.print(" 3. Never strip")
        strip_choice = get_char("\nPick a #: ")
        if strip_choice == '1':
            strip_metadata = "ask"
        elif strip_choice == '2':
            strip_metadata = True
        elif strip_choice == '3':
            strip_metadata = False
        else:
            console.print("\n [dim]Invalid choice. Defaulting to 'Ask every time'[/dim]")
            strip_metadata = "ask"
            time.sleep(0.5)
        console.print()

    return bitrate, strip_metadata

def _build_shortcut_data(entry, target_fmt=None, fixed_path="", bitrate="ask", strip_metadata="ask",
                         combine_type="auto", password=None, output_name="", output_dir=""):
    sc_data = {
        "title": "",
        "operation": entry["operation"],
        "fixed_path": fixed_path,
    }
    if entry["operation"] == "convert":
        sc_data["category"] = entry["category_id"]
        sc_data["target_fmt"] = target_fmt
        if target_fmt == "MP3":
            sc_data["bitrate"] = bitrate
        if entry["category_id"] == "2":
            sc_data["strip_metadata"] = strip_metadata
    elif entry["operation"] == "combine":
        sc_data["combine_type"] = combine_type
    elif entry["operation"] == "compress":
        sc_data["target_fmt"] = target_fmt
        sc_data["password"] = password
        sc_data["output_name"] = output_name
    elif entry["operation"] == "decompress":
        sc_data["output_dir"] = output_dir
    return sc_data

def add_shortcut(shortcuts, conv, console, get_char, get_input, flush_stdin, clean_paths):
    console.print()
    console.print("\n\n[bold yellow]--- Add New Shortcut ---[/bold yellow]")
    print_source_menu(console, conv, "Select source category:")
    console.print(" [bold white]C[/bold white]. Cancel")
    cat_choice = get_char("\nPick a #: ")

    if cat_choice.lower() == 'c':
        return

    entry = get_menu_entry(conv, cat_choice)
    if not entry:
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return

    console.print()
    target_fmt = None
    combine_type = "auto"
    password = None
    output_name = ""
    output_dir = ""
    bitrate = "ask"
    strip_metadata = "ask"

    if entry["operation"] == "convert":
        category = conv.categories[entry["category_id"]]
        source_fmts = category["extensions"]
        available_targets = set()
        for fmt in source_fmts:
            available_targets.update(conv.formats.get(fmt, []))
        sorted_targets = sorted(list(available_targets))

        console.print(f"\n[bold yellow]Select target format ('To') for {category['name']}:[/bold yellow]")
        for i, fmt in enumerate(sorted_targets, 1):
            console.print(f" {i}. {fmt.lower()}")
        console.print(" [bold white]B[/bold white]. Back")

        target_choice = get_char("\nPick target #: ")
        if target_choice.lower() == 'b':
            console.print()
            return

        try:
            to_idx = int(target_choice) - 1
            if to_idx < 0 or to_idx >= len(sorted_targets):
                raise ValueError
            target_fmt = sorted_targets[to_idx]
        except ValueError:
            console.print(" [dim]Invalid choice[/dim]")
            time.sleep(0.5)
            return

        console.print()
        bitrate, strip_metadata = _collect_convert_options(console, get_char, entry["category_id"], target_fmt)

    elif entry["operation"] == "combine":
        console.print("\n[bold yellow]When multiple file types are present:[/bold yellow]")
        console.print(" 1. Auto-detect (ask if mixed)")
        console.print(" 2. Always combine PDFs")
        console.print(" 3. Always combine MP4s")
        console.print(" 4. Always combine MP3s")
        console.print(" 5. Always combine GIFs")
        combine_choice = get_char("\nPick a #: ")
        if combine_choice == '2':
            combine_type = "pdf"
        elif combine_choice == '3':
            combine_type = "mp4"
        elif combine_choice == '4':
            combine_type = "mp3"
        elif combine_choice == '5':
            combine_type = "gif"

    elif entry["operation"] == "compress":
        target_fmt = prompt_compress_format(console, get_char)
        if target_fmt is None:
            console.print()
            return
        if target_fmt is False:
            console.print(" [dim]Invalid choice[/dim]")
            time.sleep(0.5)
            return

        console.print()
        if target_fmt in ["ZIP", "7Z", "RAR"]:
            console.print(f"\n[bold yellow]Add password protection? (y/n):[/bold yellow]", end=" ")
            pwd_yn = get_char("")
            if pwd_yn.lower() == 'y':
                password = get_input("\nEnter password: ")

        output_name = get_input(f"\nEnter default archive name (blank for compressed.{target_fmt.lower()}): ").strip()

    elif entry["operation"] == "decompress":
        console.print(f"\n[bold yellow]Fix an output directory for this shortcut? (y/n)[/bold yellow]")
        fix_out = get_char("Choice: ")
        if fix_out.lower() == 'y':
            flush_stdin()
            out_dirs = clean_paths(get_input("\nEnter output directory: "))
            output_dir = out_dirs[0] if out_dirs else ""
            flush_stdin()

    fixed_path = _prompt_fixed_path(console, get_char, get_input, flush_stdin, clean_paths)
    flush_stdin()
    sym, title = _prompt_shortcut_identity(console, get_input, get_char)
    if not sym:
        return

    sc_data = _build_shortcut_data(
        entry,
        target_fmt=target_fmt,
        fixed_path=fixed_path,
        bitrate=bitrate,
        strip_metadata=strip_metadata,
        combine_type=combine_type,
        password=password,
        output_name=output_name,
        output_dir=output_dir,
    )
    sc_data["title"] = title
    shortcuts[sym] = sc_data
    save_shortcuts(shortcuts)
    console.print(f"\n[bold green]Shortcut '{sym}' added successfully![/bold green]")
    get_char("\nPress any key to continue...")

def remove_shortcut(shortcuts, console, get_input, get_char):
    console.print()
    console.print("\n\n[bold yellow]--- Remove Shortcut ---[/bold yellow]")
    console.print("Existing shortcuts:")
    for sym, sc in shortcuts.items():
        console.print(f" [bold cyan]{sym}.[/bold cyan] {sc['title']}")
    console.print(" [bold white]C[/bold white]. Cancel")

    sym_to_remove = get_input("\nEnter symbol to remove (or 'C' to cancel): ").strip().upper()

    if sym_to_remove == 'C' or not sym_to_remove:
        return

    if sym_to_remove in shortcuts:
        title = shortcuts[sym_to_remove]['title']
        del shortcuts[sym_to_remove]
        save_shortcuts(shortcuts)
        console.print(f"\n[bold green]Shortcut '{sym_to_remove}' ({title}) removed successfully![/bold green]")
        get_char("\nPress any key to continue...")
    else:
        console.print(f"\n[bold red]Shortcut '{sym_to_remove}' not found.[/bold red]")
        get_char("\nPress any key to continue...")

def edit_shortcut(shortcuts, conv, console, get_char, get_input, clean_paths):
    console.print()
    console.print("\n\n[bold yellow]--- Edit Shortcut ---[/bold yellow]")
    console.print("Existing shortcuts:")
    for sym, sc in shortcuts.items():
        console.print(f" [bold cyan]{sym}.[/bold cyan] {sc['title']}")
    console.print(" [bold white]C[/bold white]. Cancel")

    sym_to_edit = get_input("\nEnter symbol to edit (or 'C' to cancel): ").strip().upper()

    if sym_to_edit == 'C' or not sym_to_edit:
        return

    if sym_to_edit not in shortcuts:
        console.print(f"\n[bold red]Shortcut '{sym_to_edit}' not found.[/bold red]")
        get_char("\nPress any key to continue...")
        return

    old_sc = shortcuts[sym_to_edit]

    console.print(f"\n[bold yellow]1. Operation[/bold yellow] (Current: {get_operation_label(old_sc, conv)})")
    print_source_menu(console, conv, "Select new operation:")
    console.print(" [bold white]Enter[/bold white]. Keep Current")

    op_choice = get_input("Pick a # (or Enter): ").strip()
    new_entry = None
    if op_choice:
        new_entry = get_menu_entry(conv, op_choice)
        if not new_entry:
            console.print(" [dim]Invalid choice. Keeping current operation.[/dim]")
            time.sleep(0.5)

    if new_entry:
        operation = new_entry["operation"]
        new_cat_key = new_entry.get("category_id")
        new_target_fmt = old_sc.get("target_fmt")
        new_bitrate = old_sc.get("bitrate", "ask")
        new_strip_metadata = old_sc.get("strip_metadata", "ask")
        new_combine_type = old_sc.get("combine_type", "auto")
        new_password = old_sc.get("password")
        new_output_name = old_sc.get("output_name", "")
        new_output_dir = old_sc.get("output_dir", "")

        if operation == "convert":
            category = conv.categories[new_cat_key]
            source_fmts = category["extensions"]
            available_targets = set()
            for fmt in source_fmts:
                available_targets.update(conv.formats.get(fmt, []))
            sorted_targets = sorted(list(available_targets))

            console.print(f"\n[bold yellow]Select target format ('To') for {category['name']}:[/bold yellow]")
            for i, fmt in enumerate(sorted_targets, 1):
                console.print(f" {i}. {fmt.lower()}")
            console.print(" [bold white]Enter[/bold white]. Keep Current")

            target_choice = get_input("Pick target # (or Enter): ")
            if target_choice:
                try:
                    to_idx = int(target_choice) - 1
                    if 0 <= to_idx < len(sorted_targets):
                        new_target_fmt = sorted_targets[to_idx]
                except ValueError:
                    pass
        elif operation == "combine":
            console.print("\n[bold yellow]Combine type:[/bold yellow]")
            console.print(" 1. Auto-detect")
            console.print(" 2. Always PDF")
            console.print(" 3. Always MP4")
            console.print(" 4. Always MP3")
            console.print(" 5. Always GIF")
            console.print(" [bold white]Enter[/bold white]. Keep Current")
            combine_choice = get_input("Pick a # (or Enter): ")
            if combine_choice == '2':
                new_combine_type = "pdf"
            elif combine_choice == '3':
                new_combine_type = "mp4"
            elif combine_choice == '4':
                new_combine_type = "mp3"
            elif combine_choice == '5':
                new_combine_type = "gif"
            elif combine_choice == '1':
                new_combine_type = "auto"
        elif operation == "compress":
            console.print("\n[bold yellow]Archive format[/bold yellow]")
            target_fmt = prompt_compress_format(console, get_char)
            if target_fmt and target_fmt is not False:
                new_target_fmt = target_fmt
        elif operation == "decompress":
            console.print(f"\n[bold yellow]Fixed output directory[/bold yellow] (Current: {'[None]' if not new_output_dir else new_output_dir})")
            console.print(" [bold white]Enter[/bold white]. Keep Current")
            console.print(" [bold white]N[/bold white]. No fixed directory")
            out_input = get_input("Enter output directory (or Enter/N): ")
            if out_input.upper() == 'N':
                new_output_dir = ""
            elif out_input:
                out_dirs = clean_paths(out_input)
                new_output_dir = out_dirs[0] if out_dirs else ""

        sc_data = _build_shortcut_data(
            new_entry,
            target_fmt=new_target_fmt,
            fixed_path=old_sc.get("fixed_path", ""),
            bitrate=new_bitrate,
            strip_metadata=new_strip_metadata,
            combine_type=new_combine_type,
            password=new_password,
            output_name=new_output_name,
            output_dir=new_output_dir,
        )
    else:
        operation = old_sc.get("operation", "convert")
        sc_data = dict(old_sc)
        sc_data["operation"] = operation

        if operation == "convert":
            console.print(f"\n[bold yellow]2. Target Format[/bold yellow] (Current: {old_sc['target_fmt'].lower()})")
            category = conv.categories[old_sc['category']]
            source_fmts = category["extensions"]
            available_targets = set()
            for fmt in source_fmts:
                available_targets.update(conv.formats.get(fmt, []))
            sorted_targets = sorted(list(available_targets))
            for i, fmt in enumerate(sorted_targets, 1):
                console.print(f" {i}. {fmt.lower()}")
            console.print(" [bold white]Enter[/bold white]. Keep Current")

            target_choice = get_input("Pick target # (or Enter): ")
            if target_choice:
                try:
                    to_idx = int(target_choice) - 1
                    if 0 <= to_idx < len(sorted_targets):
                        sc_data["target_fmt"] = sorted_targets[to_idx]
                except ValueError:
                    pass

            new_target_fmt = sc_data["target_fmt"]
            if new_target_fmt == "MP3":
                current_bitrate_str = {
                    "ask": "Ask every time",
                    "default": "Default",
                    "128k": "128k",
                    "192k": "192k",
                    "320k": "320k"
                }.get(sc_data.get("bitrate", "ask"), "Ask every time")
                console.print(f"\n[bold yellow]2b. Bitrate for MP3[/bold yellow] (Current: {current_bitrate_str})")
                console.print(" 1. Ask every time")
                console.print(" 2. Default")
                console.print(" 3. 128k")
                console.print(" 4. 192k")
                console.print(" 5. 320k")
                console.print(" [bold white]Enter[/bold white]. Keep Current")
                bitrate_choice = get_input("Pick bitrate # (or Enter): ")
                if bitrate_choice == '1':
                    sc_data["bitrate"] = "ask"
                elif bitrate_choice == '2':
                    sc_data["bitrate"] = "default"
                elif bitrate_choice == '3':
                    sc_data["bitrate"] = "128k"
                elif bitrate_choice == '4':
                    sc_data["bitrate"] = "192k"
                elif bitrate_choice == '5':
                    sc_data["bitrate"] = "320k"

            if sc_data.get("category") == "2":
                current_strip_str = {
                    "ask": "Ask every time",
                    True: "Always strip",
                    False: "Never strip"
                }.get(sc_data.get("strip_metadata", "ask"), "Ask every time")
                console.print(f"\n[bold yellow]2c. Metadata Stripping[/bold yellow] (Current: {current_strip_str})")
                console.print(" 1. Ask every time")
                console.print(" 2. Always strip")
                console.print(" 3. Never strip")
                console.print(" [bold white]Enter[/bold white]. Keep Current")
                strip_choice = get_input("Pick choice # (or Enter): ")
                if strip_choice == '1':
                    sc_data["strip_metadata"] = "ask"
                elif strip_choice == '2':
                    sc_data["strip_metadata"] = True
                elif strip_choice == '3':
                    sc_data["strip_metadata"] = False

    current_path = sc_data.get("fixed_path", old_sc.get("fixed_path", ""))
    console.print(f"\n[bold yellow]3. Fixed Path[/bold yellow] (Current: {'[None]' if not current_path else current_path})")
    console.print(" [bold white]Enter[/bold white]. Keep Current")
    console.print(" [bold white]N[/bold white]. No fixed path (ask every time)")
    new_path_input = get_input("Enter new path (or Enter/N): ")

    if new_path_input.upper() == 'N':
        sc_data["fixed_path"] = ""
    elif new_path_input:
        fixed_paths = clean_paths(new_path_input)
        sc_data["fixed_path"] = " ".join([f'"{p}"' for p in fixed_paths]) if fixed_paths else ""
    else:
        sc_data["fixed_path"] = current_path

    console.print(f"\n[bold yellow]4. Shortcut Key[/bold yellow] (Current: {sym_to_edit})")
    console.print(" [bold white]Enter[/bold white]. Keep Current")
    new_sym = get_input("Enter new single symbol/key (or Enter): ").strip().upper()
    if not new_sym:
        new_sym = sym_to_edit

    reserved_keys = [str(i) for i in range(10)] + ['+', '-', '=', 'Q']
    if new_sym != sym_to_edit and (new_sym in reserved_keys or new_sym in shortcuts):
        error_msg = f"'{new_sym}' is reserved" if new_sym in reserved_keys else f"'{new_sym}' already exists"
        console.print(f"\n[bold red][!] {error_msg}. Keeping old symbol '{sym_to_edit}'.[/bold red]")
        new_sym = sym_to_edit

    console.print(f"\n[bold yellow]5. Label Title[/bold yellow] (Current: {old_sc['title']})")
    console.print(" [bold white]Enter[/bold white]. Keep Current")
    new_title = get_input("Enter new label title (or Enter): ").strip()
    if not new_title:
        new_title = old_sc['title']
    sc_data["title"] = new_title

    if new_sym != sym_to_edit:
        del shortcuts[sym_to_edit]

    shortcuts[new_sym] = sc_data
    save_shortcuts(shortcuts)
    console.print(f"\n[bold green]Shortcut '{new_sym}' updated successfully![/bold green]")
    get_char("\nPress any key to continue...")

def resolve_shortcut_options(sc, interactive, prompt_fps, prompt_bitrate, prompt_strip_metadata, cli_bitrate=None, cli_strip_metadata=False):
    """Resolve per-run options from a saved shortcut config."""
    if sc.get("operation", "convert") != "convert":
        return {"fps": None, "bitrate": None, "strip_metadata": cli_strip_metadata}

    target_fmt = sc["target_fmt"]

    fps = None
    if target_fmt == "GIF":
        if interactive:
            status, val = prompt_fps()
            if status in ("back", "invalid"):
                return None
            fps = val

    bitrate = None
    if target_fmt == "MP3":
        preselected = sc.get("bitrate", "ask")
        if interactive and preselected == "ask":
            status, val = prompt_bitrate()
            if status in ("back", "invalid"):
                return None
            bitrate = val
        elif preselected not in ("ask", "default"):
            bitrate = preselected
        elif cli_bitrate:
            bitrate = cli_bitrate

    strip_metadata = cli_strip_metadata
    if sc.get("category") == "2":
        preselected = sc.get("strip_metadata", "ask")
        if interactive and preselected == "ask":
            status, val = prompt_strip_metadata()
            if status in ("back", "invalid"):
                return None
            strip_metadata = val
        elif preselected != "ask":
            strip_metadata = preselected

    return {"fps": fps, "bitrate": bitrate, "strip_metadata": strip_metadata}

def _resolve_shortcut_paths(sc, paths, interactive, console, get_input, flush_stdin, clean_paths):
    if paths is None:
        path = sc.get("fixed_path", "")
        if not path:
            if not interactive:
                console.print("[bold red]Error: Shortcut has no fixed path. Provide --path or select files in Finder.[/bold red]")
                return None
            console.print("[bold yellow]Enter file or folder path(s):[/bold yellow]")
            console.print("[dim](Tip: You can either paste or drag and drop here)[/dim]")
            flush_stdin()
            paths = clean_paths(get_input("Path: "))
            flush_stdin()
        else:
            paths = clean_paths(path)
    else:
        paths = clean_paths(paths)

    if not paths:
        return None
    return paths

def _run_combine_shortcut(conv, sc, paths, console, get_char, get_input, prompt_move_files, interactive=True):
    pdf_files = []
    mp4_files = []
    mp3_files = []
    gif_files = []
    for p in paths:
        path_obj = Path(os.path.expanduser(p))
        if path_obj.is_file():
            suffix = path_obj.suffix.lower()
            if suffix == ".pdf":
                pdf_files.append(path_obj)
            elif suffix == ".mp4":
                mp4_files.append(path_obj)
            elif suffix == ".mp3":
                mp3_files.append(path_obj)
            elif suffix == ".gif":
                gif_files.append(path_obj)
        elif path_obj.is_dir():
            pdf_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"])
            mp4_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".mp4"])
            mp3_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"])
            gif_files.extend([f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() == ".gif"])

    combine_type = sc.get("combine_type", "auto")
    if combine_type == "auto":
        available_types = []
        if pdf_files: available_types.append(('pdf', 'PDF files'))
        if mp4_files: available_types.append(('mp4', 'MP4 files'))
        if mp3_files: available_types.append(('mp3', 'MP3 files'))
        if gif_files: available_types.append(('gif', 'GIF files'))
        
        if len(available_types) > 1:
            if not interactive:
                console.print("[bold red]Error: Mixed file types found in non-interactive mode. Cannot determine combination type.[/bold red]")
                return False
            console.print("\n[bold yellow]Found multiple file types. What do you want to combine?[/bold yellow]")
            for i, (t_code, t_name) in enumerate(available_types, 1):
                console.print(f" {i}. {t_name}")
            c_choice = get_char("\nPick a #: ")
            try:
                c_idx = int(c_choice) - 1
                if 0 <= c_idx < len(available_types):
                    combine_type = available_types[c_idx][0]
            except ValueError:
                pass
            if not combine_type:
                return False
        elif len(available_types) == 1:
            combine_type = available_types[0][0]
        else:
            console.print("[bold red]No PDF, MP4, MP3, or GIF files found to combine.[/bold red]")
            if interactive:
                get_char("\nPress any key to continue...")
            return False

    if combine_type == 'pdf':
        out_path = conv.combine_pdfs(paths)
    elif combine_type == 'mp4':
        out_path = conv.combine_videos(paths)
    elif combine_type == 'mp3':
        out_path = conv.combine_audios(paths)
    else:
        out_path = conv.combine_gifs(paths)

    if out_path:
        if interactive and prompt_move_files:
            prompt_move_files(console, get_char, get_input, [out_path])
    else:
        if interactive:
            get_char("\nPress any key to continue...")
    return True

def _run_split_shortcut(conv, paths, console, get_char, get_input, prompt_move_files, interactive=True):
    split_dirs = []
    for path in paths:
        p = Path(path)
        if p.suffix.lower() == ".pdf":
            out_dir = conv.split_pdf(path)
            if out_dir:
                split_dirs.append(out_dir)
        elif p.suffix.lower() == ".mp4":
            out_dir = conv.split_video(path)
            if out_dir:
                split_dirs.append(out_dir)
        elif p.suffix.lower() == ".mp3":
            out_dir = conv.split_audio(path)
            if out_dir:
                split_dirs.append(out_dir)
        elif p.suffix.lower() == ".gif":
            out_dir = conv.split_gif(path)
            if out_dir:
                split_dirs.append(out_dir)
        else:
            console.print(f"[bold red]Error: Unsupported file type '{p.suffix}' for {p.name}. Only PDF, MP4, MP3, and GIF are supported for splitting.[/bold red]")

    if split_dirs:
        if interactive and prompt_move_files:
            prompt_move_files(console, get_char, get_input, split_dirs)
    else:
        if interactive:
            get_char("\nPress any key to continue...")
    return True

def _run_resize_shortcut(paths, conv, console, get_char, get_input, interactive=True):
    if not interactive:
        console.print("[bold red]Error: Resize operations are only supported in interactive mode.[/bold red]")
        return False
    from modules import resize
    resize.resize_media(paths, conv, console, get_char, get_input)
    return True

def _run_compress_shortcut(conv, sc, paths, console, get_char, get_input, prompt_move_files, interactive=True):
    target_fmt = sc["target_fmt"]
    password = sc.get("password")
    output_name = sc.get("output_name") or f"compressed.{target_fmt.lower()}"
    success, error, out_path = conv.compress(paths, output_name, target_fmt, password)
    if success:
        console.print(f"\n[bold green]Successfully compressed into {output_name}[/bold green]")
        if interactive and prompt_move_files:
            prompt_move_files(console, get_char, get_input, [out_path])
    else:
        console.print(f"\n[bold red]FAILED to compress:[/bold red]")
        console.print(f"   [dim]{error.strip()}[/dim]")
        if interactive:
            get_char("\nPress any key to continue...")
    return True

def _run_decompress_shortcut(conv, sc, paths, console, get_char, get_input, prompt_move_files, flush_stdin, clean_paths, interactive=True):
    out_dir = sc.get("output_dir") or None
    if out_dir:
        out_dirs = clean_paths(out_dir)
        out_dir = out_dirs[0] if out_dirs else None
    elif interactive:
        console.print(f"\n[bold yellow]Enter output directory (leave blank for default):[/bold yellow]")
        flush_stdin()
        out_dirs = clean_paths(get_input("Dir: "))
        out_dir = out_dirs[0] if out_dirs else None
        flush_stdin()

    decompressed_dirs = []
    for path in paths:
        success, error, actual_out_dir = conv.decompress(path, out_dir)
        if success:
            console.print(f"\n[bold green]Successfully decompressed {Path(path).name}.[/bold green]")
            decompressed_dirs.append(actual_out_dir)
        else:
            console.print(f"\n[bold red]FAILED to decompress {Path(path).name}:[/bold red]")
            console.print(f"   [dim]{error.strip()}[/dim]")

    if decompressed_dirs:
        if interactive and prompt_move_files:
            prompt_move_files(console, get_char, get_input, decompressed_dirs)
    else:
        if interactive:
            get_char("\nPress any key to continue...")
    return True

def run_shortcut(
    conv,
    console,
    get_char,
    get_input,
    flush_stdin,
    clean_paths,
    check_and_prompt_md_pdf,
    prompt_move_files,
    key,
    paths=None,
    interactive=True,
    md_pdf_mode=None,
    jobs=None,
    overwrite=False,
    skip=False,
    cli_bitrate=None,
    cli_strip_metadata=False,
    prompt_fps=None,
    prompt_bitrate=None,
    prompt_strip_metadata=None,
):
    """Run a saved shortcut by key. Returns True on success, False if cancelled or missing."""
    shortcuts = load_shortcuts()
    key = key.strip().upper()
    if key not in shortcuts:
        console.print(f"[bold red]Shortcut '{key}' not found. Create one in Convergent or check ~/.convergent_shortcuts.json.[/bold red]")
        return False

    sc = shortcuts[key]
    console.print(f"\n[bold yellow]Executing Shortcut: {sc['title']}[/bold yellow]")
    operation = sc.get("operation", "convert")
    paths = _resolve_shortcut_paths(sc, paths, interactive, console, get_input, flush_stdin, clean_paths)
    if not paths:
        return False

    if operation == "combine":
        return _run_combine_shortcut(conv, sc, paths, console, get_char, get_input, prompt_move_files, interactive)
    if operation == "split":
        return _run_split_shortcut(conv, paths, console, get_char, get_input, prompt_move_files, interactive)
    if operation == "resize":
        return _run_resize_shortcut(paths, conv, console, get_char, get_input, interactive)
    if operation == "compress":
        return _run_compress_shortcut(conv, sc, paths, console, get_char, get_input, prompt_move_files, interactive)
    if operation == "decompress":
        return _run_decompress_shortcut(
            conv, sc, paths, console, get_char, get_input, prompt_move_files, flush_stdin, clean_paths, interactive
        )

    category = conv.categories[sc["category"]]
    source_fmts = category["extensions"]
    target_fmt = sc["target_fmt"]

    options = resolve_shortcut_options(
        sc,
        interactive,
        prompt_fps,
        prompt_bitrate,
        prompt_strip_metadata,
        cli_bitrate=cli_bitrate,
        cli_strip_metadata=cli_strip_metadata,
    )
    if options is None:
        return False

    if md_pdf_mode is None and check_and_prompt_md_pdf:
        md_pdf_mode = check_and_prompt_md_pdf(target_fmt, paths, console, get_char, time)
        if md_pdf_mode == "back":
            return False

    converted = conv.process(
        source_fmts,
        target_fmt,
        paths,
        fps=options["fps"],
        bitrate=options["bitrate"],
        jobs=jobs,
        overwrite=overwrite,
        skip=skip,
        md_pdf_mode=md_pdf_mode,
        strip_metadata=options["strip_metadata"],
        interactive=interactive,
    )
    if interactive and prompt_move_files:
        prompt_move_files(console, get_char, get_input, converted)
    return True
