import logging

import requests

from apps.base import App
from apps.builtin._shared import cache_get_or_fetch, row_frames


def _fetch(settings):
    try:
        pos = requests.get('http://api.open-notify.org/iss-now.json', timeout=5).json()['iss_position']
        lat = float(pos['latitude'])
        lon = float(pos['longitude'])
        ld = 'N' if lat >= 0 else 'S'
        lnd = 'E' if lon >= 0 else 'W'
        try:
            crew = len(requests.get('http://api.open-notify.org/astros.json', timeout=3).json()['people'])
            hdr = f"ISS CREW:{crew}"
        except Exception:
            hdr = 'ISS TRACKER'
        row2 = f"LAT {abs(lat):6.2f}{ld}"
        row3 = f"LON {abs(lon):7.2f}{lnd}"
        return (hdr, row2, row3)
    except Exception as e:
        logging.error(f"ISS fetch error: {e}")
        return ('ISS ERR', 'CHECK CONN', '')


class IssApp(App):
    key = 'iss'
    name = 'ISS Tracker'
    icon = '🛸'
    desc = 'Space station'

    def get_pages(self, settings, cache):
        return row_frames([cache_get_or_fetch(cache, 'iss', 5, lambda: _fetch(settings))], delay=5)
