from datetime import datetime

from apps.base import App, Frame
from apps.builtin._shared import clock, get_tz, center_page


class DateApp(App):
    key = 'date'
    name = 'Date'
    icon = '📅'
    desc = 'Full date view'

    def get_pages(self, settings, cache):
        dt = datetime.now(get_tz(settings))
        text = center_page(
            clock(dt),
            dt.strftime('%B %d').upper(),
            dt.strftime('%A').upper(),
        )
        return [Frame(text=text, delay=1)]
