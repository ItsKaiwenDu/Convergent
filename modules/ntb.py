import zipfile
import re
from pathlib import Path
from customs.run_command import run_command

def natural_sort_key(s):
    """
    Key for natural alphanumeric sorting (e.g. so thumbnail_2.png comes before thumbnail_10.png)
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def convert_ntb(source, target_ext):
    """
    Converts a Notability .ntb bundle file to PDF format.
    
    If the .ntb note contains imported PDF assets, it extracts and merges them
    in natural order to produce a high-fidelity multi-page background PDF.
    If no background PDF is imported, it falls back to extracting all available
    thumbnail/preview/page images and combining them into a single multi-page PDF.
    
    Args:
        source (Path): The path to the source .ntb file.
        target_ext (str): The target format extension (must be 'PDF').
        
    Returns:
        tuple: (success (bool), error_message (str))
    """
    if target_ext.upper() != "PDF":
        return False, f"Unsupported target format: {target_ext}"
        
    output = source.with_suffix(f".{target_ext.lower()}")
    temp_files = []
    
    try:
        with zipfile.ZipFile(source, 'r') as zip_ref:
            namelist = zip_ref.namelist()
            
            # 1. Search for PDF assets in the ZIP archive
            pdf_names = [name for name in namelist if name.lower().endswith('.pdf')]
            
            if pdf_names:
                # Prefer PDFs under the 'assets/' folder as they are the primary background documents
                pdf_assets = [name for name in pdf_names if 'assets/' in name.lower()]
                selected_pdfs = pdf_assets if pdf_assets else pdf_names
                
                # Sort PDFs naturally by filename to ensure correct page sequence
                selected_pdfs = sorted(selected_pdfs, key=natural_sort_key)
                
                if len(selected_pdfs) == 1:
                    # Single PDF: Extract directly to output path
                    with zip_ref.open(selected_pdfs[0]) as s_file, open(output, 'wb') as t_file:
                        t_file.write(s_file.read())
                    return True, ""
                else:
                    # Multiple PDFs: Extract to temporary files and combine them
                    for idx, pdf_name in enumerate(selected_pdfs):
                        temp_pdf = source.with_suffix(f".temp_ntb_page_{idx}.pdf")
                        temp_files.append(temp_pdf)
                        with zip_ref.open(pdf_name) as s_file, open(temp_pdf, 'wb') as t_file:
                            t_file.write(s_file.read())
                            
                    # Run Ghostscript to merge all temporary PDFs into the output PDF
                    cmd = ["gs", "-dNOPAUSE", "-sDEVICE=pdfwrite", f"-sOUTPUTFILE={output}", "-dBATCH"] + [str(f) for f in temp_files]
                    success, error = run_command(cmd)
                    return success, error
                    
            # 2. Fallback: Search for thumbnail/preview/page images
            image_extensions = ('.png', '.jpg')
            image_names = [
                name for name in namelist 
                if name.lower().endswith(image_extensions) and 
                any(keyword in name.lower() for keyword in ('thumbnail', 'preview', 'page'))
            ]
            
            if image_names:
                # Sort images naturally to preserve the page order (e.g. thumbnail_1, thumbnail_2...)
                image_names = sorted(image_names, key=natural_sort_key)
                
                if len(image_names) == 1:
                    # Single Image: Extract and convert via ImageMagick
                    temp_png = source.with_suffix(".temp_thumb.png")
                    temp_files.append(temp_png)
                    with zip_ref.open(image_names[0]) as s_file, open(temp_png, 'wb') as t_file:
                        t_file.write(s_file.read())
                        
                    success, error = run_command(["magick", str(temp_png), str(output)])
                    return success, error
                else:
                    # Multiple Images: Extract all and convert them into a single multi-page PDF
                    for idx, img_name in enumerate(image_names):
                        img_suffix = Path(img_name).suffix.lower()
                        temp_img = source.with_suffix(f".temp_thumb_{idx}{img_suffix}")
                        temp_files.append(temp_img)
                        with zip_ref.open(img_name) as s_file, open(temp_img, 'wb') as t_file:
                            t_file.write(s_file.read())
                            
                    # Run ImageMagick to combine all images into a single multi-page PDF
                    cmd = ["magick"] + [str(f) for f in temp_files] + [str(output)]
                    success, error = run_command(cmd)
                    return success, error
                    
            return False, "No background PDF asset or preview thumbnail found inside the .ntb file."
            
    except zipfile.BadZipFile:
        return False, "Invalid or corrupted .ntb file (not a valid ZIP archive)."
    except Exception as e:
        return False, str(e)
    finally:
        # Clean up any temporary files created during the process
        for f in temp_files:
            if f.exists():
                try:
                    f.unlink()
                except:
                    pass

