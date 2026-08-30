import random

from apps.base import App, Frame, SettingField
from config import NUM_MODULES


def generate_pages(n=12):
    """Sparse random colour dots."""
    colors = 'roygbpw   '  # extra spaces for sparsity
    return [''.join(random.choice(colors) for _ in range(NUM_MODULES)) for _ in range(n)]


class TwinkleApp(App):
    key = 'anim_twinkle'
    name = 'Twinkle'
    icon = '✨'
    desc = 'Sparkle effect'
    settings_fields = [
        SettingField('anim_twinkle_speed', 'Frame Speed (seconds)', type='number', default='0.5',
                      placeholder='0.5', min='0.1', max='3', step='0.1'),
    ]

    def get_pages(self, settings, cache):
        speed = max(0.1, float(settings.get('anim_twinkle_speed', 0.5)))
        return [Frame(text=p, delay=speed, style='random', raw=True) for p in generate_pages()]
