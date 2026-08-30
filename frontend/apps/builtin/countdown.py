import logging
from datetime import datetime

import pytz

from apps.base import App, Frame, SettingField
from apps.builtin._shared import get_tz, center_page


class CountdownApp(App):
    key = 'countdown'
    name = 'Countdown'
    icon = '⏳'
    desc = 'Timer to event'
    settings_fields = [
        SettingField('countdown_event', 'Event Name', default='NEW YEAR', placeholder='NEW YEAR'),
        SettingField('countdown_target', 'Target Date & Time', type='datetime-local',
                      default='2027-01-01T00:00:00'),
    ]

    def get_pages(self, settings, cache):
        event = settings.get('countdown_event', 'NEW YEAR').upper()[:16]
        target_str = settings.get('countdown_target', '2027-01-01T00:00:00')
        tz = get_tz(settings)
        try:
            try:
                target = datetime.fromisoformat(target_str)
            except ValueError:
                target = datetime.strptime(target_str[:16], '%Y-%m-%dT%H:%M')
            if target.tzinfo is None:
                target = tz.localize(target)
            diff = target - datetime.now(pytz.utc).astimezone(tz)
            if diff.total_seconds() <= 0:
                text = center_page(event, 'TIME IS UP!', '')
            else:
                total = int(diff.total_seconds())
                d, rem = divmod(total, 86400)
                h, rem = divmod(rem, 3600)
                mn, s = divmod(rem, 60)
                text = center_page(event, f"{d}D {h:02d}H", f"{mn:02d}M {s:02d}S")
        except Exception as e:
            logging.error(f"Countdown error: {e}")
            text = center_page('COUNTDOWN', 'CONFIG ERROR', '')
        return [Frame(text=text, delay=1)]
