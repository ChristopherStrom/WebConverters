import os
import re
import tempfile
import shutil
import subprocess
from yt_dlp import YoutubeDL
from typing import Tuple, Dict, Any

def convert_youtube_to_mp3(url: str, static_folder: str) -> Tuple[str, str]:
    """
    Download audio from a YouTube URL, convert to MP3,
    move it into static/downloads, and return (filepath_on_disk, download_name).
    """
    # 1) make a temp work dir
    tmpdir = tempfile.mkdtemp()
    
    try:
        # Extract video ID from URL for safe filename
        video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else "video"
        safe_filename = f"youtube_{video_id}"
        
        # 2) tell yt_dlp to download best audio + convert to mp3 with safe filename
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(tmpdir, safe_filename + '.%(ext)s'),  # Use safe filename pattern
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'verbose': True,
            'ffmpeg_location': '/usr/bin/ffmpeg'
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown Title')
            
            # Get a clean, readable title for the download name
            clean_title = re.sub(r'[^\w\s-]', '', title)
            clean_title = re.sub(r'\s+', '_', clean_title)
        
        # 3) The output file should be predictable now
        mp3_filename = f"{safe_filename}.mp3"
        mp3_path = os.path.join(tmpdir, mp3_filename)
        
        if not os.path.exists(mp3_path):
            # Look for any mp3 file if the expected one doesn't exist
            mp3_files = [f for f in os.listdir(tmpdir) if f.lower().endswith('.mp3')]
            if mp3_files:
                mp3_filename = mp3_files[0]
                mp3_path = os.path.join(tmpdir, mp3_filename)
            else:
                # Try to find any files and convert if needed
                source_files = os.listdir(tmpdir)
                if not source_files:
                    raise FileNotFoundError("No files were downloaded")
                    
                # Take the first downloaded file and convert it manually
                source_file = os.path.join(tmpdir, source_files[0])
                
                try:
                    print(f"Manually converting {source_file} to {mp3_path}")
                    subprocess.run([
                        'ffmpeg', '-i', source_file,
                        '-vn',  # No video
                        '-ar', '44100',  # Audio sample rate
                        '-ac', '2',  # Stereo
                        '-b:a', '192k',  # Bitrate
                        mp3_path
                    ], check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Manual FFmpeg conversion failed: {e.stderr}")
                
                if not os.path.exists(mp3_path):
                    raise FileNotFoundError("MP3 not found after conversion attempts")

        # 4) Move the file to static/downloads
        downloads_dir = os.path.join(static_folder, 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)
        
        dst = os.path.join(downloads_dir, mp3_filename)
        shutil.move(mp3_path, dst)

        # 5) Create a sensible download name using the video title
        download_name = f"{clean_title or safe_filename}.mp3"
        
        print(f"Returning file path: {dst}, download name: {download_name}")
        return dst, download_name
        
    except Exception as e:
        # Clean up on error
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError(f"YouTube to MP3 conversion failed: {str(e)}")
