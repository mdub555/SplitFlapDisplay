from datetime import datetime

import pytz
import requests

from apps.base import App, Frame, SettingField
from apps.builtin._shared import cache_get_or_fetch, center_page


def _fetch(settings):
    stop = settings.get('mbta_stop', 'place-bbsta')
    route = settings.get('mbta_route', 'Orange')
    url = (f"https://api-v3.mbta.com/predictions"
           f"?filter[stop]={stop}&filter[route]={route}&page[limit]=20&sort=departure_time")
    try:
        predictions = requests.get(url, timeout=5).json().get('data', [])
        dirs = {0: [], 1: []}
        for p in predictions:
            dt = p['attributes']['departure_time']
            if not dt:
                continue
            mins = int((datetime.fromisoformat(dt).astimezone(pytz.utc)
                        - datetime.now(pytz.utc)).total_seconds() / 60)
            if mins < 0:
                continue
            d = p['attributes']['direction_id']
            if d in dirs and len(dirs[d]) < 2:
                dirs[d].append(str(mins))

        def fmt(name, times):
            if not times:
                return f"{name} ---"
            return f"{name} {','.join(times)}M"

        header = '\U0001f7e7\U0001f7e7' + route.upper()[:9] + '\U0001f7e7\U0001f7e7'
        return (header, fmt('OAK GRV', dirs[1]), fmt('FRST HLS', dirs[0]))
    except Exception:
        return ('METRO ERROR', '', '')


class MetroApp(App):
    key = 'metro'
    name = 'Metro'
    icon = '🚇'
    desc = 'MBTA arrivals'
    settings_fields = [
        SettingField('mbta_stop', 'Stop ID (e.g. place-NSTAT)', placeholder='place-NSTAT'),
        SettingField('mbta_route', 'Route (e.g. Orange)', placeholder='Orange'),
    ]

    def get_pages(self, settings, cache):
        rows = cache_get_or_fetch(cache, 'metro', 30, lambda: _fetch(settings))
        return [Frame(text=center_page(*rows), delay=5)]
