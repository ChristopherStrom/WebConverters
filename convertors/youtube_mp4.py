import os
import re
import tempfile
import shutil
from yt_dlp import YoutubeDL
from typing import Tuple

def convert_youtube_to_mp4(url: str, static_folder: str) -> Tuple[str, str]:
    """
    Download video from a YouTube URL in MP4 format,
    move it into static/downloads, and return (filepath_on_disk, download_name).
    """
    # 1) temp work dir
    tmpdir = tempfile.mkdtemp()

    # 2) download best mp4 into tmpdir
    ydl_opts = {
        'format': 'mp4',
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # 3) find the .mp4 file
    mp4_list = [f for f in os.listdir(tmpdir) if f.lower().endswith('.mp4')]
    if not mp4_list:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise FileNotFoundError("MP4 not found after download")
    actual = mp4_list[0]
    src = os.path.join(tmpdir, actual)

    # 4) move across filesystems into static/downloads
    downloads_dir = os.path.join(static_folder, 'downloads')
    os.makedirs(downloads_dir, exist_ok=True)
    dst = os.path.join(downloads_dir, actual)
    shutil.move(src, dst)

    # 5) cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)

    # 6) sanitize download‑name
    base, _ = os.path.splitext(actual)
    safe = re.sub(r'\W+', '', base)
    download_name = f"{safe}.mp4"

    return dst, download_name
