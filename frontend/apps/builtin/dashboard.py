from datetime import datetime

from apps.base import App, Frame
from apps.builtin._shared import get_tz, center_page, cache_get_or_fetch
from apps.builtin.weather import fetch_weather


class DashboardApp(App):
    key = 'dashboard'
    name = 'Dashboard'
    icon = '🏠'
    desc = 'Time + weather'

    def get_pages(self, settings, cache):
        tz = get_tz(settings)
        dt = datetime.now(tz)
        time_page = center_page(
            dt.strftime('%A').upper(),
            dt.strftime('%b %d %Y').upper(),
            dt.strftime('%I:%M %p').upper(),
        )

        # Shares the 'weather' cache key with WeatherApp — if both were ever
        # active at once this avoids a duplicate fetch, though in practice
        # only one app runs at a time.
        w = cache_get_or_fetch(cache, 'weather', 300, lambda: fetch_weather(settings))
        now_t = dt.strftime('%I:%M%p').lstrip('0')
        if not w:
            weather_page = center_page('NO WEATHER DATA', now_t, 'CHECK API KEY')
        else:
            mcl = max(1, 14 - len(now_t))
            l1 = f"{w['city'][:mcl]} {now_t}"
            pfx = f"{w['temp']}F ({w['feels']}F) "
            l2 = pfx + w['desc'][:max(0, 15 - len(pfx))]
            l3 = f"H:{w['high']}F L:{w['low']}F"
            weather_page = center_page(l1, l2, l3)

        return [Frame(text=time_page, delay=5), Frame(text=weather_page, delay=5)]
