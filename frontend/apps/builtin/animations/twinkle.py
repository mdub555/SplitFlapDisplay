import random

from apps.builtin.animations.base import AnimationApp
from config import NUM_MODULES


def generate_pages(n=12):
    """Sparse random colour dots."""
    colors = 'roygbpw   '  # extra spaces for sparsity
    return [''.join(random.choice(colors) for _ in range(NUM_MODULES)) for _ in range(n)]


class TwinkleApp(AnimationApp):
    key = 'anim_twinkle'
    name = 'Twinkle'
    icon = '✨'
    desc = 'Sparkle effect'
    fixed_style = 'random'

    def frames(self):
        return generate_pages()
