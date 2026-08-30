from datetime import datetime

from apps.base import App, Frame
from apps.builtin._shared import get_tz, center_page


class TimeApp(App):
    key = 'time'
    name = 'Time'
    icon = '⏱️'
    desc = 'Live clock'

    def get_pages(self, settings, cache):
        tz = get_tz(settings)
        text = center_page(datetime.now(tz).strftime('%I:%M %p').lstrip('0'))
        return [Frame(text=text, delay=1)]
