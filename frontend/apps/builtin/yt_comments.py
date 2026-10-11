import requests

from apps.base import App
from apps.builtin._shared import cache_get_or_fetch, row_frames
from display.charset import FLAP_CHARS


def _fetch(settings):
    """(heading, text) for each of the latest comments: the author and what
    they wrote, or a heading and an error."""
    api_key = settings.get('yt_api_key', '').strip()
    video_id = settings.get('yt_video_id', '').strip()
    if not api_key or not video_id:
        return [('YT COMMENTS', 'MISSING API KEY OR VIDEO ID')]
    url = (f"https://www.googleapis.com/youtube/v3/commentThreads"
           f"?part=snippet&videoId={video_id}&maxResults=5&order=time&textFormat=plainText&key={api_key}")
    try:
        items = requests.get(url, timeout=5).json().get('items', [])
        if not items:
            return [('YT COMMENTS', 'NO COMMENTS FOUND')]
        pages = []
        for item in items:
            sn = item['snippet']['topLevelComment']['snippet']
            author = ''.join(c for c in sn['authorDisplayName'].upper() if c in FLAP_CHARS)
            text = sn['textDisplay'].upper().replace('\n', ' ')
            pages.append((author, text))
        return pages or [('YT COMMENTS', 'FETCH ERROR')]
    except Exception:
        return [('YT COMMENTS', 'API ERROR')]


class YoutubeCommentsApp(App):
    key = 'yt_comments'
    name = 'Comments'
    icon = '💬'
    desc = 'YT comments'
    order = 100
    global_settings = ['yt_api_key', 'yt_video_id']

    def get_items(self, settings, cache, grid):
        comments = cache_get_or_fetch(cache, 'yt_comments', 60, lambda: _fetch(settings))
        # A comment each: the heading on the first row, the text wrapped over
        # the rest.
        return [row_frames(grid, [(heading, *grid.wrap(text, grid.rows - 1))], delay=5)
                for heading, text in comments]
