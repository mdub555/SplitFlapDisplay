import random

from apps.base import App, Frame, SettingField
from apps.builtin._shared import center_page
from config import NUM_MODULES

STYLE_OPTS = ['ltr', 'rtl', 'center_out', 'outside_in', 'spiral', 'diagonal', 'anti_diagonal',
              'random', 'rain', 'columns']
_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$&?%*-+'


def _noise():
    return ''.join(random.choice(_CHARS) for _ in range(NUM_MODULES))


class MatrixApp(App):
    key = 'anim_matrix'
    name = 'Matrix'
    icon = '💻'
    desc = 'Cascade reveal'
    settings_fields = [
        SettingField('anim_matrix_text', 'Reveal Text', default='SPLIT  FLAP  DISPLAY',
                      placeholder='SPLIT  FLAP  DISPLAY'),
        SettingField('anim_matrix_style', 'Final Reveal Order', type='select', default='ltr', opts=STYLE_OPTS),
        SettingField('anim_matrix_speed', 'Frame Speed (seconds)', type='number', default='0.4',
                      placeholder='0.4', min='0.1', max='2', step='0.1'),
    ]

    def get_pages(self, settings, cache):
        target = center_page(settings.get('anim_matrix_text', 'SPLIT  FLAP  DISPLAY').upper())
        style = settings.get('anim_matrix_style', 'ltr')
        speed = max(0.1, float(settings.get('anim_matrix_speed', 0.4)))
        return [
            Frame(text=_noise(), delay=speed, style='random', raw=True),
            Frame(text=_noise(), delay=speed, style='rain', raw=True),
            Frame(text=_noise(), delay=speed, style='spiral', raw=True),
            Frame(text=target, delay=speed, style=style),
        ]
