import logging
import re

import requests

from apps.base import App, Frame, Grid, SettingField
from apps.builtin._shared import cache_get_or_fetch, plain_text
from apps.oauth import OAuthProvider

NOW_PLAYING_URL = 'https://api.spotify.com/v1/me/player/currently-playing?additional_types=episode'

# Spotify only lets an http:// redirect address be a loopback one, and
# this server is reached over plain http on the LAN, so sign-in comes back
# to an address that doesn't load and the person pastes it in.
REDIRECT_URI = 'http://127.0.0.1:8888/callback'

# Clutter on the end of a title: " - Remastered 2011", " (feat. Someone)".
_TITLE_EXTRAS = re.compile(
    r'\s+-\s+.*\b(remaster(ed)?|mono|stereo|radio edit|single version)\b.*$'
    r'|\s*[(\[](feat\.?|ft\.|with)\s[^)\]]*[)\]]', re.I)


def clean_title(title):
    return _TITLE_EXTRAS.sub('', title).strip() or title


def _fetch(token):
    """{'playing', 'title', 'by'} for what's playing now, None if nothing
    is, or 'error' if Spotify couldn't be asked."""
    try:
        res = requests.get(NOW_PLAYING_URL, headers={'Authorization': f'Bearer {token}'}, timeout=5)
    except requests.RequestException as e:
        logging.error(f'Spotify fetch error: {e}')
        return 'error'
    if res.status_code == 204:
        return None
    if not res.ok:
        logging.error(f'Spotify fetch error: HTTP {res.status_code} {res.text[:200]}')
        return 'error'
    body = res.json()
    item = body.get('item')
    if not item:   # an ad, or something Spotify won't say
        return None
    if item.get('type') == 'episode':
        by = (item.get('show') or {}).get('name', '')
    else:
        by = ', '.join(a['name'] for a in item.get('artists', [])[:2])
    return {'playing': bool(body.get('is_playing')), 'title': clean_title(item.get('name', '')), 'by': by}


def now_playing_page(grid, track):
    """The title centred in all but the bottom row (cut off if it needs
    more), and the artist on the bottom row, so the two don't run together."""
    if grid.rows == 1:
        return grid.page(plain_text(track['title']))
    above = Grid(grid.rows - 1, grid.cols)
    return above.page(*above.wrap(plain_text(track['title']))) + Grid(1, grid.cols).page(plain_text(track['by']))


class SpotifyApp(App):
    key = 'spotify'
    name = 'Spotify'
    icon = '🎵'
    desc = 'Now playing'
    order = 115
    settings_fields = [
        SettingField('spotify_client_id', 'Spotify Client ID', placeholder='From your app at developer.spotify.com'),
    ]
    oauth = OAuthProvider(
        name='Spotify',
        authorize_url='https://accounts.spotify.com/authorize',
        token_url='https://accounts.spotify.com/api/token',
        client_id_key='spotify_client_id',
        scopes=['user-read-currently-playing'],
        redirect_uri=REDIRECT_URI,
        help=('Create an app at developer.spotify.com/dashboard (any name; tick Web API), add the '
              f'redirect URI {REDIRECT_URI}, and copy its Client ID into the field above.'),
    )

    def get_pages(self, settings, cache, grid):
        token = self.access_token(settings)
        if not token:
            return [Frame(text=grid.page('SPOTIFY', 'NOT CONNECTED'), delay=10)]
        # Asked every 10 s; the page is only sent when the track changes.
        track = cache_get_or_fetch(cache, 'now_playing', 10, lambda: _fetch(token))
        if track == 'error':
            return [Frame(text=grid.page('SPOTIFY', 'FETCH ERROR'), delay=10)]
        if not track:
            return [Frame(text=grid.page('SPOTIFY', 'NOTHING PLAYING'), delay=5)]
        if not track['playing']:
            return [Frame(text=grid.page('SPOTIFY', 'PAUSED'), delay=5)]
        return [Frame(text=now_playing_page(grid, track), delay=5)]
