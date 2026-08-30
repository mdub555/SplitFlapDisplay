from datetime import datetime

import pytz

from apps.base import App, Frame, SettingField
from apps.builtin._shared import center_page

LABELS = {
    'US/Eastern': 'EST', 'US/Pacific': 'PST', 'US/Central': 'CST',
    'US/Mountain': 'MST', 'Europe/London': 'LON', 'Europe/Paris': 'PAR',
    'Europe/Berlin': 'BER', 'Asia/Tokyo': 'TYO', 'Asia/Singapore': 'SIN',
    'Asia/Dubai': 'DXB', 'Australia/Sydney': 'SYD', 'UTC': 'UTC',
    'America/New_York': 'NYC', 'America/Los_Angeles': 'LAX',
    'America/Chicago': 'CHI', 'America/Denver': 'DEN',
}


class WorldClockApp(App):
    key = 'world_clock'
    name = 'World Clock'
    icon = '🌍'
    desc = '3 time zones'
    settings_fields = [
        SettingField('world_clock_zones', 'Timezones (comma-separated)',
                      default='US/Eastern,US/Pacific,Europe/London',
                      placeholder='US/Eastern,US/Pacific,Europe/London'),
    ]

    def get_pages(self, settings, cache):
        zones_str = settings.get('world_clock_zones', 'US/Eastern,US/Pacific,Europe/London')
        zones = [z.strip() for z in zones_str.split(',') if z.strip()][:3]
        while len(zones) < 3:
            zones.append('UTC')
        rows = []
        for zone in zones:
            try:
                now = datetime.now(pytz.timezone(zone))
                tstr = now.strftime('%I:%M%p').lstrip('0')
                label = LABELS.get(zone, zone.split('/')[-1][:4].upper())
                rows.append(f"{label:<4} {tstr}")
            except Exception:
                rows.append('ERR')
        # One zone per row (rather than the old 3-zones-crammed-into-one-row
        # layout, which only worked because it happened to match a 15-col
        # grid) — this generalizes cleanly to any GRID_COLS/GRID_ROWS.
        return [Frame(text=center_page(*rows), delay=1)]
