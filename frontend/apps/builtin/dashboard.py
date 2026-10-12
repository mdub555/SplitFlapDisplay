from datetime import datetime

from apps.base import App, Frame
from apps.builtin._shared import clock, get_tz
from apps.builtin.weather import weather_page


class DashboardApp(App):
    key = 'dashboard'
    name = 'Dashboard'
    icon = '🏠'
    desc = 'Time + weather'
    order = 30

    def get_pages(self, settings, cache, grid):
        dt = datetime.now(get_tz(settings))
        time_page = grid.page(
            dt.strftime('%A').upper(),
            dt.strftime('%b %d %Y').upper(),
            clock(dt),
        )
        return [Frame(text=time_page, delay=5), Frame(text=weather_page(settings, cache, grid), delay=5)]
