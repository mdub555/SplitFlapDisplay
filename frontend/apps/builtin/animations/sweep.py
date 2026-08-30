from apps.base import App, Frame, SettingField
from config import GRID_ROWS, GRID_COLS

STYLE_OPTS = ['ltr', 'rtl', 'center_out', 'outside_in', 'spiral', 'diagonal', 'anti_diagonal',
              'random', 'columns']


def generate_pages():
    """Colour band sweeping across the board, then back."""
    colors = 'roygbpw'
    pages = []
    for i in range(1, GRID_COLS + 1):
        col = colors[i % 7]
        pages.append(''.join(col if c < i else ' ' for r in range(GRID_ROWS) for c in range(GRID_COLS)))
    for i in range(GRID_COLS - 1, 0, -1):
        col = colors[(i + 3) % 7]
        pages.append(''.join(col if c < i else ' ' for r in range(GRID_ROWS) for c in range(GRID_COLS)))
    return pages


class SweepApp(App):
    key = 'anim_sweep'
    name = 'Sweep'
    icon = '〰️'
    desc = 'Colour sweep'
    settings_fields = [
        SettingField('anim_sweep_style', 'Update Order', type='select', default='ltr', opts=STYLE_OPTS),
        SettingField('anim_sweep_speed', 'Frame Speed (seconds)', type='number', default='0.25',
                      placeholder='0.25', min='0.05', max='2', step='0.05'),
    ]

    def get_pages(self, settings, cache):
        style = settings.get('anim_sweep_style', 'ltr')
        speed = max(0.05, float(settings.get('anim_sweep_speed', 0.25)))
        return [Frame(text=p, delay=speed, style=style, raw=True) for p in generate_pages()]
