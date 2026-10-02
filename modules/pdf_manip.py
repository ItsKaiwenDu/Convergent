import os
import uuid
import shutil
from pathlib import Path
from customs.run_command import run_command, send_to_trash

def required_dependencies(source_format, target_format, **options):
    return ["ghostscript"]


def convert_pdf_to_image(source, target_ext, dpi=300, output_dir=None):
    path_obj = Path(os.path.expanduser(source))
    if not path_obj.is_file() or path_obj.suffix.lower() != ".pdf":
        return False, f"Not a valid PDF file: {source}"
    
    if output_dir:
        dest_p = Path(os.path.expanduser(str(output_dir)))
        if dest_p.name == f"{path_obj.stem}_images":
            output_dir = dest_p
        else:
            output_dir = dest_p / f"{path_obj.stem}_images"
    else:
        output_dir = path_obj.parent / f"{path_obj.stem}_images"
        send_to_trash(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    target_ext = target_ext.lower()
    staging_dir = output_dir / f".tmp_staging_{uuid.uuid4().hex[:8]}"
    staging_dir.mkdir(parents=True, exist_ok=True)

    device = "jpeg" if target_ext == "jpg" else "tiff24nc" if target_ext == "tif" else "bmp16m" if target_ext == "bmp" else "png16m"
    output_pattern = staging_dir / f"page_%03d.{target_ext}"
    
    dpi_val = int(dpi) if dpi is not None and int(dpi) > 0 else 300
    cmd = [
        "gs", 
        "-dNOPAUSE", 
        "-dBATCH", 
        "-dSAFER",
        f"--permit-file-read={path_obj.resolve()}",
        f"--permit-file-write={staging_dir.resolve()}/*",
        "-sDEVICE=" + device, 
        f"-r{dpi_val}", 
        f"-sOUTPUTFILE={output_pattern}", 
        str(path_obj.resolve())
    ]
    
    try:
        success, error = run_command(cmd)
        if success:
            new_pages = sorted(list(staging_dir.glob(f"page_*.{target_ext}")))
            if new_pages:
                # Pre-validate all target destinations before deleting or moving anything
                for p in new_pages:
                    target_p = output_dir / p.name
                    if target_p.is_dir() or target_p.is_symlink():
                        return False, f"Destination conflict: '{target_p}' is an existing directory or symlink."

                # Staging backup of existing page files for rollback protection
                old_pages = [f for f in output_dir.glob(f"page_*.{target_ext}") if f.is_file()]
                backup_dir = staging_dir / "old_backup"
                backup_dir.mkdir(parents=True, exist_ok=True)
                moved_to_backup = []
                try:
                    for old_f in old_pages:
                        bak_p = backup_dir / old_f.name
                        shutil.move(str(old_f), str(bak_p))
                        moved_to_backup.append((old_f, bak_p))
                except Exception as e:
                    # Rollback moving to backup
                    for orig_p, bak_p in moved_to_backup:
                        if bak_p.exists():
                            try:
                                shutil.move(str(bak_p), str(orig_p))
                            except Exception:
                                pass
                    return False, f"Failed to prepare destination page updates: {e}"

                # Move new pages into place
                moved_new = []
                try:
                    for p in new_pages:
                        target_p = output_dir / p.name
                        shutil.move(str(p), str(target_p))
                        moved_new.append(target_p)
                except Exception as e:
                    # Rollback: remove partially placed new pages and restore original old pages
                    for np in moved_new:
                        if np.exists():
                            try:
                                np.unlink()
                            except Exception:
                                pass
                    for orig_p, bak_p in moved_to_backup:
                        if bak_p.exists():
                            try:
                                shutil.move(str(bak_p), str(orig_p))
                            except Exception:
                                pass
                    return False, f"Failed to publish new pages: {e}"
            return True, ""
        return False, error
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

