from datetime import datetime

from apps.base import App, Frame
from apps.builtin._shared import clock, get_tz, center_page


class TimeApp(App):
    key = 'time'
    name = 'Time'
    icon = '⏱️'
    desc = 'Live clock'

    def get_pages(self, settings, cache):
        return [Frame(text=center_page(clock(datetime.now(get_tz(settings)))), delay=1)]
