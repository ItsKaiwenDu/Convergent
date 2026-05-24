import zipfile
from pathlib import Path
from customs.run_command import run_command

def convert_ntb(source, target_ext):
    """
    Converts a Notability .ntb bundle file to PDF format.
    
    If the .ntb note contains imported PDF assets (which hold the high-fidelity
    original background content), it extracts the main background PDF asset.
    If no background PDF is imported, it falls back to extracting the fully
    rendered preview thumbnail of the note ('thumbnail.png') and converting it to PDF.
    
    Args:
        source (Path): The path to the source .ntb file.
        target_ext (str): The target format extension (must be 'PDF').
        
    Returns:
        tuple: (success (bool), error_message (str))
    """
    if target_ext.upper() != "PDF":
        return False, f"Unsupported target format: {target_ext}"
        
    output = source.with_suffix(f".{target_ext.lower()}")
    
    try:
        with zipfile.ZipFile(source, 'r') as zip_ref:
            namelist = zip_ref.namelist()
            
            # 1. Search for PDF assets in the ZIP archive
            pdf_names = [name for name in namelist if name.lower().endswith('.pdf')]
            
            if pdf_names:
                # Prefer PDFs under the 'assets/' folder as they are the primary background documents
                pdf_assets = [name for name in pdf_names if 'assets/' in name.lower()]
                selected_pdf = pdf_assets[0] if pdf_assets else pdf_names[0]
                
                # Extract the PDF directly to the output path
                with zip_ref.open(selected_pdf) as s_file, open(output, 'wb') as t_file:
                    t_file.write(s_file.read())
                return True, ""
                
            # 2. Fallback: Search for thumbnail.png preview
            thumbnail_name = next((name for name in namelist if name.lower().endswith('thumbnail.png')), None)
            
            if thumbnail_name:
                temp_png = source.with_suffix(".temp_thumb.png")
                
                # Extract the PNG thumbnail to a temp file
                with zip_ref.open(thumbnail_name) as s_file, open(temp_png, 'wb') as t_file:
                    t_file.write(s_file.read())
                    
                # Convert the extracted PNG to PDF using ImageMagick
                try:
                    success, error = run_command(["magick", str(temp_png), str(output)])
                    return success, error
                finally:
                    if temp_png.exists():
                        temp_png.unlink()
                        
            return False, "No background PDF asset or preview thumbnail found inside the .ntb file."
            
    except zipfile.BadZipFile:
        return False, "Invalid or corrupted .ntb file (not a valid ZIP archive)."
    except Exception as e:
        return False, str(e)
