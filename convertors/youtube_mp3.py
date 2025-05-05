import os
import re
import tempfile
import shutil
from yt_dlp import YoutubeDL
from typing import Tuple

def convert_youtube_to_mp3(url: str, static_folder: str) -> Tuple[str, str]:
    """
    Download audio from a YouTube URL, convert to MP3,
    move it into static/downloads, and return (filepath_on_disk, download_name).
    """
    # 1) make a temp work dir
    tmpdir = tempfile.mkdtemp()

    # 2) tell yt_dlp to download best audio + convert to mp3
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    # 3) find the produced .mp3
    mp3_list = [f for f in os.listdir(tmpdir) if f.lower().endswith('.mp3')]
    if not mp3_list:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise FileNotFoundError("MP3 not found after conversion")
    actual_filename = mp3_list[0]
    src = os.path.join(tmpdir, actual_filename)

    # 4) move across filesystems into static/downloads
    downloads_dir = os.path.join(static_folder, 'downloads')
    os.makedirs(downloads_dir, exist_ok=True)
    dst = os.path.join(downloads_dir, actual_filename)
    shutil.move(src, dst)

    # 5) clean up temp dir
    shutil.rmtree(tmpdir, ignore_errors=True)

    # 6) sanitize a download‑friendly name
    base, _ = os.path.splitext(actual_filename)
    safe = re.sub(r'\W+', '', base)
    download_name = f"{safe}.mp3"

    return dst, download_name
