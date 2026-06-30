import os
from pathlib import Path
from customs.run_command import run_command, send_to_trash

def convert_pdf_to_image(source, target_ext):
    path_obj = Path(os.path.expanduser(source)).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".pdf":
        return False, f"Not a valid PDF file: {source}"
    
    output_dir = path_obj.parent / f"{path_obj.stem}_images"
    send_to_trash(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    target_ext = target_ext.lower()
    # Ghostscript devices: jpeg, png16m (24-bit color), tiff24nc (24-bit color TIFF), bmp16m (24-bit color BMP)
    device = "jpeg" if target_ext in ["jpg", "jpeg"] else "tiff24nc" if target_ext in ["tiff", "tif"] else "bmp16m" if target_ext == "bmp" else "png16m"
    output_pattern = output_dir / f"page_%03d.{target_ext}"
    
    cmd = [
        "gs", 
        "-dNOPAUSE", 
        "-dBATCH", 
        "-dNOSAFER",
        "-sDEVICE=" + device, 
        "-r300", 
        f"-sOUTPUTFILE={output_pattern}", 
        str(path_obj)
    ]
    
    success, error = run_command(cmd)
    if success:
        return True, ""
    return False, error
