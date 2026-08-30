import requests

from apps.base import App, Frame
from apps.builtin._shared import cache_get_or_fetch, center_page
from display.charset import FLAP_CHARS
from config import GRID_COLS


def _fetch(settings):
    api_key = settings.get('yt_api_key', '').strip()
    video_id = settings.get('yt_video_id', '').strip()
    if not api_key or not video_id:
        return [('YT COMMENTS', 'MISSING API KEY', 'OR VIDEO ID')]
    url = (f"https://www.googleapis.com/youtube/v3/commentThreads"
           f"?part=snippet&videoId={video_id}&maxResults=5&order=time&textFormat=plainText&key={api_key}")
    try:
        items = requests.get(url, timeout=5).json().get('items', [])
        if not items:
            return [('YT COMMENTS', 'NO COMMENTS', 'FOUND')]
        pages = []
        for item in items:
            sn = item['snippet']['topLevelComment']['snippet']
            author = ''.join(c for c in sn['authorDisplayName'].upper() if c in FLAP_CHARS)
            text = sn['textDisplay'].upper().replace('\n', ' ')
            pages.append((author[:GRID_COLS], text[:GRID_COLS], text[GRID_COLS:GRID_COLS * 2]))
        return pages or [('YT COMMENTS', 'FETCH ERROR', '')]
    except Exception:
        return [('YT COMMENTS', 'API ERROR', '')]


class YoutubeCommentsApp(App):
    key = 'yt_comments'
    name = 'Comments'
    icon = '💬'
    desc = 'YT comments'
    # yt_api_key / yt_video_id live in Global Settings — shared with YouTube & Livestream.
    settings_fields = []

    def get_pages(self, settings, cache):
        rows_pages = cache_get_or_fetch(cache, 'yt_comments', 60, lambda: _fetch(settings))
        return [Frame(text=center_page(*rows), delay=5) for rows in rows_pages]
