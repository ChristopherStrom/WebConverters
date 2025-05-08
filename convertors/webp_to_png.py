import os
import re
import tempfile
import shutil
from PIL import Image
from typing import Tuple

def convert_webp_to_png(file_path: str, static_folder: str) -> Tuple[str, str]:
    """
    Convert a WebP image to PNG format,
    move it into static/downloads, and return (filepath_on_disk, download_name).
    """
    # 1) make a temp work dir
    tmpdir = tempfile.mkdtemp()
    
    try:
        # Get the filename and extension
        filename = os.path.basename(file_path)
        base_name, ext = os.path.splitext(filename)
        
        # 2) Load the image file using PIL
        if ext.lower() == '.webp':
            img = Image.open(file_path)
        else:
            raise ValueError("Unsupported file format. Please upload a WebP image file.")
            
        # 3) Convert to PNG
        png_filename = f"{base_name}.png"
        png_path = os.path.join(tmpdir, png_filename)
        img.save(png_path, format="PNG")
        
        # 4) Move to static/downloads
        downloads_dir = os.path.join(static_folder, 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)
        dst = os.path.join(downloads_dir, png_filename)
        shutil.move(png_path, dst)
        
        # 5) Clean up temp dir
        shutil.rmtree(tmpdir, ignore_errors=True)
        
        # 6) Sanitize a download-friendly name
        safe = re.sub(r'\W+', '', base_name)
        download_name = f"{safe}.png"
        
        return dst, download_name
        
    except Exception as e:
        # Clean up on error
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise e
