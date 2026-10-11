from datetime import datetime

from apps.base import App, Frame
from apps.builtin._shared import clock, get_tz


class TimeApp(App):
    key = 'time'
    name = 'Time'
    icon = '⏱️'
    desc = 'Live clock'
    order = 40

    def get_pages(self, settings, cache, grid):
        return [Frame(text=grid.page(clock(datetime.now(get_tz(settings)))), delay=1)]
