from datetime import datetime

import pytz

from apps.base import App, Frame, SettingField
from apps.builtin._shared import clock, split_list

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
    desc = 'Time zones'
    order = 120
    settings_fields = [
        SettingField('world_clock_zones', 'Timezones (comma-separated, one per display row)',
                      default='US/Eastern,US/Pacific,Europe/London',
                      placeholder='US/Eastern,US/Pacific,Europe/London'),
    ]

    def get_pages(self, settings, cache, grid):
        zones = split_list(self.setting(settings, 'world_clock_zones'), limit=grid.rows) or ['UTC']
        rows = []
        for zone in zones:
            try:
                label = LABELS.get(zone, zone.split('/')[-1][:4].upper())
                # Right-aligned, so 9:30AM lines up under 12:30PM.
                rows.append(f"{label:<4} {clock(datetime.now(pytz.timezone(zone)), spaced=False):>7}")
            except Exception:
                rows.append('ERR')
        # One zone per row.
        return [Frame(text=grid.page(*rows), delay=1)]
