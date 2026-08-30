from apps.base import App, Frame, SettingField
from config import GRID_ROWS, GRID_COLS

STYLE_OPTS = ['ltr', 'rtl', 'center_out', 'outside_in', 'spiral', 'diagonal', 'random']


def generate_pages():
    """Alternating two-colour checkerboard that swaps through several palettes."""
    pages = []
    pairs = [('r', 'b'), ('o', 'p'), ('y', 'g'), ('r', 'w'), ('g', 'b')]
    for a, b in pairs:
        p1 = ''.join(a if (r + c) % 2 == 0 else b for r in range(GRID_ROWS) for c in range(GRID_COLS))
        p2 = ''.join(b if (r + c) % 2 == 0 else a for r in range(GRID_ROWS) for c in range(GRID_COLS))
        pages += [p1, p2]
    return pages


class CheckerApp(App):
    key = 'anim_checker'
    name = 'Checker'
    icon = '🎭'
    desc = 'Checkerboard'
    settings_fields = [
        SettingField('anim_checker_style', 'Update Order', type='select', default='ltr', opts=STYLE_OPTS),
        SettingField('anim_checker_speed', 'Frame Speed (seconds)', type='number', default='0.6',
                      placeholder='0.6', min='0.1', max='3', step='0.1'),
    ]

    def get_pages(self, settings, cache):
        style = settings.get('anim_checker_style', 'ltr')
        speed = max(0.1, float(settings.get('anim_checker_speed', 0.6)))
        return [Frame(text=p, delay=speed, style=style, raw=True) for p in generate_pages()]
