import json
import time
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

def add_shortcut(shortcuts, conv, console, get_char, get_input, flush_stdin, clean_paths):
    console.print()
    console.print("\n\n[bold yellow]--- Add New Shortcut ---[/bold yellow]")
    console.print("Select source category:")
    category_keys = sorted(conv.categories.keys())
    label_w = 14
    for i, key in enumerate(category_keys, 1):
        cat = conv.categories[key]
        exts_str = ", ".join(cat["extensions"]).lower()
        console.print(f" [bold cyan]{i}.[/bold cyan] {(cat['name'] + ':').ljust(label_w)} {exts_str}")
    console.print(" [bold white]C[/bold white]. Cancel")
    cat_choice = get_char("\nPick category #: ")
    
    if cat_choice.lower() == 'c':
        return
    
    selected_cat_key = None
    try:
        idx = int(cat_choice) - 1
        if 0 <= idx < len(category_keys):
            selected_cat_key = category_keys[idx]
    except ValueError:
        pass
        
    if not selected_cat_key:
        console.print(" [dim]Invalid choice[/dim]")
        time.sleep(0.5)
        return
    
    console.print()
        
    category = conv.categories[selected_cat_key]
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
        
    # 3. Bitrate selection (only if target format is MP3)
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

    # 3c. Strip metadata selection (only if target category is Image ("2"))
    strip_metadata = "ask"
    if selected_cat_key == "2":
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

    console.print(f"\n[bold yellow]Do you want to fix a file/folder path for this shortcut? (y/n)[/bold yellow]")
    fix_path = get_char("Choice: ")
    fixed_path = ""
    if fix_path.lower() == 'y':
        flush_stdin()
        fixed_paths = clean_paths(get_input("\nEnter path: "))
        fixed_path = " ".join([f'"{p}"' for p in fixed_paths]) if fixed_paths else ""
        flush_stdin()
        
    flush_stdin()
    sym = get_input("\nInput a single symbol/key for this shortcut (e.g., 'S'): ").strip().upper()
    
    reserved_keys = [str(i) for i in range(10)] + ['+', '-', '=', 'Q']
    if sym in reserved_keys:
        console.print(f"\n[bold red][!] '{sym}' is a reserved key. Please choose a letter not in: {' '.join(reserved_keys)}[/bold red]")
        get_char("\nPress any key to continue...")
        return
        
    title = get_input("Input a label title (e.g., 'Quick JPG Convert'): ").strip()
    
    if sym and title:
        sc_data = {
            "title": title,
            "category": selected_cat_key,
            "target_fmt": target_fmt,
            "fixed_path": fixed_path
        }
        if target_fmt == "MP3":
            sc_data["bitrate"] = bitrate
        if selected_cat_key == "2":
            sc_data["strip_metadata"] = strip_metadata
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
    
    # 1. Update Category
    console.print(f"\n[bold yellow]1. Category[/bold yellow] (Current: {conv.categories[old_sc['category']]['name']})")
    category_keys = sorted(conv.categories.keys())
    for i, key in enumerate(category_keys, 1):
        cat = conv.categories[key]
        console.print(f" {i}. {cat['name']}")
    console.print(" [bold white]Enter[/bold white]. Keep Current")
    
    cat_choice = get_input("Pick category # (or Enter): ")
    new_cat_key = old_sc['category']
    if cat_choice:
        try:
            idx = int(cat_choice) - 1
            if 0 <= idx < len(category_keys):
                new_cat_key = category_keys[idx]
        except ValueError:
            pass

    # 2. Update Target Format
    category = conv.categories[new_cat_key]
    source_fmts = category["extensions"]
    available_targets = set()
    for fmt in source_fmts:
        available_targets.update(conv.formats.get(fmt, []))
    sorted_targets = sorted(list(available_targets))
    
    console.print(f"\n[bold yellow]2. Target Format[/bold yellow] (Current: {old_sc['target_fmt'].lower()})")
    for i, fmt in enumerate(sorted_targets, 1):
        console.print(f" {i}. {fmt.lower()}")
    console.print(" [bold white]Enter[/bold white]. Keep Current")
    
    target_choice = get_input("Pick target # (or Enter): ")
    new_target_fmt = old_sc['target_fmt']
    if target_choice:
        try:
            to_idx = int(target_choice) - 1
            if 0 <= to_idx < len(sorted_targets):
                new_target_fmt = sorted_targets[to_idx]
        except ValueError:
            pass

    # 3. Update Fixed Path
    current_path = old_sc.get("fixed_path", "")
    console.print(f"\n[bold yellow]3. Fixed Path[/bold yellow] (Current: {'[None]' if not current_path else current_path})")
    console.print(" [bold white]Enter[/bold white]. Keep Current")
    console.print(" [bold white]N[/bold white]. No fixed path (ask every time)")
    new_path_input = get_input("Enter new path (or Enter/N): ")
    
    new_fixed_path = current_path
    if new_path_input.upper() == 'N':
        new_fixed_path = ""
    elif new_path_input:
        fixed_paths = clean_paths(new_path_input)
        new_fixed_path = " ".join([f'"{p}"' for p in fixed_paths]) if fixed_paths else ""

    # 3b. Update Bitrate (only if target format is MP3)
    new_bitrate = old_sc.get("bitrate", "ask")
    if new_target_fmt == "MP3":
        current_bitrate_str = {
            "ask": "Ask every time",
            "default": "Default",
            "128k": "128k",
            "192k": "192k",
            "320k": "320k"
        }.get(new_bitrate, "Ask every time")
        console.print(f"\n[bold yellow]3b. Bitrate for MP3[/bold yellow] (Current: {current_bitrate_str})")
        console.print(" 1. Ask every time")
        console.print(" 2. Default")
        console.print(" 3. 128k")
        console.print(" 4. 192k")
        console.print(" 5. 320k")
        console.print(" [bold white]Enter[/bold white]. Keep Current")
        bitrate_choice = get_input("Pick bitrate # (or Enter): ")
        if bitrate_choice == '1':
            new_bitrate = "ask"
        elif bitrate_choice == '2':
            new_bitrate = "default"
        elif bitrate_choice == '3':
            new_bitrate = "128k"
        elif bitrate_choice == '4':
            new_bitrate = "192k"
        elif bitrate_choice == '5':
            new_bitrate = "320k"

    # 3c. Update Strip Metadata (only if category is Image ("2"))
    new_strip_metadata = old_sc.get("strip_metadata", "ask")
    if new_cat_key == "2":
        current_strip_str = {
            "ask": "Ask every time",
            True: "Always strip",
            False: "Never strip"
        }.get(new_strip_metadata, "Ask every time")
        console.print(f"\n[bold yellow]3c. Metadata Stripping[/bold yellow] (Current: {current_strip_str})")
        console.print(" 1. Ask every time")
        console.print(" 2. Always strip")
        console.print(" 3. Never strip")
        console.print(" [bold white]Enter[/bold white]. Keep Current")
        strip_choice = get_input("Pick choice # (or Enter): ")
        if strip_choice == '1':
            new_strip_metadata = "ask"
        elif strip_choice == '2':
            new_strip_metadata = True
        elif strip_choice == '3':
            new_strip_metadata = False

    # 4. Update Symbol
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

    # 5. Update Title
    console.print(f"\n[bold yellow]5. Label Title[/bold yellow] (Current: {old_sc['title']})")
    console.print(" [bold white]Enter[/bold white]. Keep Current")
    new_title = get_input("Enter new label title (or Enter): ").strip()
    if not new_title:
        new_title = old_sc['title']

    # Save Changes
    if new_sym != sym_to_edit:
        del shortcuts[sym_to_edit]
    
    sc_data = {
        "title": new_title,
        "category": new_cat_key,
        "target_fmt": new_target_fmt,
        "fixed_path": new_fixed_path
    }
    if new_target_fmt == "MP3":
        sc_data["bitrate"] = new_bitrate
    if new_cat_key == "2":
        sc_data["strip_metadata"] = new_strip_metadata
        
    shortcuts[new_sym] = sc_data
    save_shortcuts(shortcuts)
    console.print(f"\n[bold green]Shortcut '{new_sym}' updated successfully![/bold green]")
    get_char("\nPress any key to continue...")
