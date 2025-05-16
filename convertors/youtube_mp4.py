import os
import re
import tempfile
import shutil
import subprocess
from yt_dlp import YoutubeDL
from typing import Tuple, Dict, Any

import os
import re
import tempfile
import shutil
import subprocess
from yt_dlp import YoutubeDL
from typing import Tuple, Dict, Any

def sanitize_filename(filename):
    """Remove all non-alphanumeric characters from filename"""
    # Extract base name and extension
    base_name, ext = os.path.splitext(filename)
    # Replace all non-alphanumeric chars with underscores
    safe_name = re.sub(r'[^\w\s-]', '', base_name)
    # Replace any remaining whitespace with underscores
    safe_name = re.sub(r'\s+', '_', safe_name)
    # Return sanitized name with original extension
    return f"{safe_name}{ext}"

def convert_youtube_to_mp4(url: str, static_folder: str) -> Tuple[str, str]:
    """
    Download video from a YouTube URL in MP4 format,
    move it into static/downloads, and return (filepath_on_disk, download_name).
    """
    # 1) temp work dir
    tmpdir = tempfile.mkdtemp()
    
    try:
        # 2) download best mp4 into tmpdir
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'verbose': True,  # Add verbose output for debugging
            'ffmpeg_location': '/usr/bin/ffmpeg'  # Explicitly set ffmpeg path
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')

        # 3) Find all files in the temp directory
        all_files = os.listdir(tmpdir)
        
        # Process MP4 files first
        mp4_list = [f for f in all_files if f.lower().endswith('.mp4')]
        
        if not mp4_list:
            # Try to find any downloaded files
            source_files = all_files
            if not source_files:
                raise FileNotFoundError("No files were downloaded")
                
            # If a file was downloaded but not in mp4 format, convert it
            source_file_name = source_files[0]
            source_path = os.path.join(tmpdir, source_file_name)
            
            # Create sanitized version of source filename for the MP4
            safe_base_name = re.sub(r'[^\w\s-]', '', os.path.splitext(source_file_name)[0])
            safe_base_name = re.sub(r'\s+', '_', safe_base_name)
            mp4_filename = f"{safe_base_name}.mp4"
            mp4_path = os.path.join(tmpdir, mp4_filename)
            
            try:
                subprocess.run([
                    'ffmpeg', '-i', source_path,
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    mp4_path
                ], check=True, capture_output=True, text=True)
                mp4_list = [mp4_filename]
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Manual FFmpeg conversion failed: {e.stderr}")
        
        if not mp4_list:
            raise FileNotFoundError("MP4 not found after download/conversion")
        
        # Get the original MP4 file 
        original_filename = mp4_list[0]
        
        # Create a sanitized version of the filename
        sanitized_filename = sanitize_filename(original_filename)
        src = os.path.join(tmpdir, original_filename)
        
        # If the original filename has special characters, rename the file
        if sanitized_filename != original_filename:
            sanitized_path = os.path.join(tmpdir, sanitized_filename)
            os.rename(src, sanitized_path)
            src = sanitized_path

        # 4) move across filesystems into static/downloads
        downloads_dir = os.path.join(static_folder, 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)
        
        dst = os.path.join(downloads_dir, sanitized_filename)
        shutil.move(src, dst)

        # 5) Create a download-friendly name
        base, _ = os.path.splitext(sanitized_filename)
        download_name = f"{base}.mp4"
        
        print(f"Returning file path: {dst}, download name: {download_name}")
        return dst, download_name
        
    except Exception as e:
        # Clean up on error
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError(f"YouTube to MP4 conversion failed: {str(e)}")
