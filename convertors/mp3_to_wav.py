import os
import re
import tempfile
import shutil
from pydub import AudioSegment
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
        
        # 2) Load the audio file using pydub
        if ext.lower() in ['.mp3', '.mp4', '.m4a']:
            audio = AudioSegment.from_file(file_path)
        else:
            raise ValueError("Unsupported file format. Please upload an MP3 or MP4 audio file.")
            
        # 3) Convert to WAV
        wav_filename = f"{base_name}.wav"
        wav_path = os.path.join(tmpdir, wav_filename)
        audio.export(wav_path, format="wav")
        
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
