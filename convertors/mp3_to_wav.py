import os
import re
import tempfile
import shutil
import subprocess
from typing import Tuple

def convert_to_wav(file_path: str, static_folder: str) -> Tuple[str, str]:
    """
    Convert an MP3 or MP4A file to WAV format,
    move it into static/downloads, and return (filepath_on_disk, download_name).
    """
    # 1) make a temp work dir
    tmpdir = tempfile.mkdtemp()
    
    try:
        # Get the filename and extension
        filename = os.path.basename(file_path)
        base_name, ext = os.path.splitext(filename)
        
        # 2) Check file format
        if ext.lower() not in ['.mp3', '.mp4', '.m4a']:
            raise ValueError("Unsupported file format. Please upload an MP3 or MP4 audio file.")
            
        # 3) Convert to WAV using ffmpeg
        wav_filename = f"{base_name}.wav"
        wav_path = os.path.join(tmpdir, wav_filename)
        
        try:
            subprocess.run([
                'ffmpeg', '-i', file_path,
                '-acodec', 'pcm_s16le',
                '-ar', '44100',
                wav_path
            ], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to convert file: {e.stderr}")
        
        # 4) Move to static/downloads
        downloads_dir = os.path.join(static_folder, 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)
        dst = os.path.join(downloads_dir, wav_filename)
        shutil.move(wav_path, dst)
        
        # 5) Clean up temp dir
        shutil.rmtree(tmpdir, ignore_errors=True)
        
        # 6) Sanitize a download-friendly name
        safe = re.sub(r'\W+', '', base_name)
        download_name = f"{safe}.wav"
        
        return dst, download_name
        
    except Exception as e:
        # Clean up on error
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise e