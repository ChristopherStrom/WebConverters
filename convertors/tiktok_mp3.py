import os
import re
import json
import tempfile
import requests
from typing import Any, Dict, List, Tuple, Union


def _find_key(obj: Union[Dict[str, Any], List[Any]], key: str) -> Any:
    """
    Recursively search for given key in a nested dict/list.
    """
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            try:
                return _find_key(value, key)
            except KeyError:
                continue
    elif isinstance(obj, list):
        for item in obj:
            try:
                return _find_key(item, key)
            except KeyError:
                continue
    raise KeyError(f'{key} not found')


def convert_tiktok_to_mp3(page_url: str) -> Tuple[str, str]:
    """
    Fetches the TikTok music detail page, parses JSON to extract title and musicUrl,
    downloads the MP3 to a temp file named after the title (no spaces),
    and returns a tuple of (filepath, filename).
    """
    # Retrieve page HTML
    resp = requests.get(page_url)
    resp.raise_for_status()
    html = resp.text

    # Extract JSON from <script id="__NEXT_DATA__">
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise RuntimeError('Could not find NEXT_DATA JSON on page')
    data = json.loads(match.group(1))

    # Extract title and musicUrl
    try:
        title = _find_key(data, 'title')
        music_url = _find_key(data, 'musicUrl')
    except KeyError as e:
        raise RuntimeError(str(e))

    # Sanitize filename: remove spaces and unsafe chars
    base_name = re.sub(r'\s+', '', title)
    filename = f"{base_name}.mp3"

    # Download MP3
    tmpdir = tempfile.mkdtemp()
    filepath = os.path.join(tmpdir, filename)
    dl_resp = requests.get(music_url, stream=True)
    dl_resp.raise_for_status()

    with open(filepath, 'wb') as f:
        for chunk in dl_resp.iter_content(chunk_size=8192):
            f.write(chunk)

    return filepath, filename