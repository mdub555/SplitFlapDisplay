import requests

from apps.base import App, Frame
from apps.builtin._shared import cache_get_or_fetch, center_page


def fetch_youtube(settings):
    """Exposed at module level so LivestreamApp can reuse it."""
    cid = settings.get('yt_channel_id', '').strip()
    for url in [
        f"https://mixerno.space/api/youtube-channel-counter/user/{cid}",
        f"https://axern.space/api/get?platform=youtube&type=channel&id={cid}",
    ]:
        try:
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
            name = (r.get('user', [{}])[0].get('count') or
                    r.get('snippet', {}).get('title', '')).upper()
            subs = (r.get('counts', [{}])[0].get('count') or
                    r.get('statistics', {}).get('subscriberCount', '?'))
            if name:
                return {'name': name, 'subs': subs}
        except Exception:
            pass
    return None


class YoutubeApp(App):
    key = 'youtube'
    name = 'YouTube'
    icon = '▶️'
    desc = 'Sub counter'
    # yt_channel_id lives in Global Settings — shared with Comments & Livestream.
    settings_fields = []

    def get_pages(self, settings, cache):
        yt = cache_get_or_fetch(cache, 'youtube', 30, lambda: fetch_youtube(settings))
        if yt:
            text = center_page('YOUTUBE', yt['name'][:16], f"{yt['subs']} SUBS")
        else:
            text = center_page('YOUTUBE', 'FETCH ERROR', 'CHECK API')
        return [Frame(text=text, delay=5)]
