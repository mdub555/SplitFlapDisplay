import logging
from datetime import datetime

import requests

from apps.base import App, Frame, SettingField
from apps.builtin._shared import get_tz, cache_get_or_fetch, center_page


def _fetch_viewers(settings):
    api_key = settings.get('yt_api_key', '').strip()
    video_id = settings.get('yt_video_id', '').strip()
    if not api_key or not video_id:
        return None
    url = (f"https://www.googleapis.com/youtube/v3/videos"
           f"?part=liveStreamingDetails&id={video_id}&key={api_key}")
    try:
        items = requests.get(url, timeout=5).json().get('items', [])
        if not items:
            return None
        details = items[0].get('liveStreamingDetails', {}) or {}
        v = details.get('concurrentViewers')
        return int(v) if v is not None else None
    except Exception as e:
        logging.error(f"YT viewers fetch error: {e}")
        return None


def _parse_comments(settings):
    raw = settings.get('livestream_comments', '').strip()
    if not raw:
        return []
    raw = raw.replace('\r\n', '\n').replace('\r', '\n')
    blocks = [b for b in raw.split('\n\n') if b.strip()]
    pages = []
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        while len(lines) < 3:
            lines.append('')
        pages.append(tuple(lines[:3]))
    return pages


class LivestreamApp(App):
    key = 'livestream'
    name = 'Livestream'
    icon = '🔴'
    desc = 'Launch day rotate'
    settings_fields = [
        SettingField('livestream_interval', 'Rotation Interval (seconds)', type='number',
                      default='25', placeholder='25', min='5', max='180', step='1'),
        SettingField('livestream_comments',
                      'Comments (blank line separates slides, up to 3 lines each)',
                      type='textarea',
                      placeholder='JOHNDOE\nGreat video!\nSubscribed\n\nUSER_123\nLove the build'),
    ]
    # yt_channel_id / yt_api_key / yt_video_id live in Global Settings — the
    # same channel/video config used by the YouTube and Comments apps.

    def get_pages(self, settings, cache):
        from apps.builtin.youtube import fetch_youtube

        frames = []
        tz = get_tz(settings)
        time_str = datetime.now(tz).strftime('%I:%M %p').lstrip('0')

        yt = cache_get_or_fetch(cache, 'youtube', 60, lambda: fetch_youtube(settings))
        if yt:
            frames.append(Frame(text=center_page(time_str, yt['name'][:16], f"{yt['subs']} SUBS"), style='ltr'))

        viewers = cache_get_or_fetch(cache, 'livestream_viewers', 30, lambda: _fetch_viewers(settings))
        if viewers is not None:
            frames.append(Frame(text=center_page('WATCHING NOW', f"{viewers:,}", 'LIVE VIEWERS'), style='diagonal'))

        varied_styles = ['outside_in', 'spiral', 'anti_diagonal', 'rtl', 'rain', 'center_out']
        for i, rows in enumerate(_parse_comments(settings)):
            frames.append(Frame(text=center_page(*rows), style=varied_styles[i % len(varied_styles)]))

        interval = max(5.0, float(settings.get('livestream_interval', 25) or 25))
        for f in frames:
            f.delay = interval
        return frames
