from apps.base import App, Frame, SettingField
from config import GRID_ROWS, GRID_COLS

STYLE_OPTS = ['ltr', 'rtl', 'center_out', 'outside_in', 'spiral', 'diagonal',
              'anti_diagonal', 'random', 'rain', 'reverse_rain', 'columns', 'columns_rtl']


def generate_pages():
    """7 pages cycling the colour tiles across the board."""
    colors = 'roygbpw'
    return [''.join(colors[(c + off) % 7] for r in range(GRID_ROWS) for c in range(GRID_COLS))
            for off in range(7)]


class RainbowApp(App):
    key = 'anim_rainbow'
    name = 'Rainbow'
    icon = '🌈'
    desc = 'Colour wave'
    settings_fields = [
        SettingField('anim_rainbow_style', 'Update Order', type='select', default='ltr', opts=STYLE_OPTS),
        SettingField('anim_rainbow_speed', 'Frame Speed (seconds)', type='number', default='0.4',
                      placeholder='0.4', min='0.1', max='3', step='0.1'),
    ]

    def get_pages(self, settings, cache):
        style = settings.get('anim_rainbow_style', 'ltr')
        speed = max(0.1, float(settings.get('anim_rainbow_speed', 0.4)))
        return [Frame(text=p, delay=speed, style=style, raw=True) for p in generate_pages()]
