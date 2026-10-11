import random

from apps.builtin.animations.base import AnimationApp


def generate_pages(grid, n=12):
    """Sparse random colour dots."""
    colors = 'roygbpw   '  # extra spaces for sparsity
    return [''.join(random.choice(colors) for _ in range(grid.size)) for _ in range(n)]


class TwinkleApp(AnimationApp):
    key = 'anim_twinkle'
    name = 'Twinkle'
    icon = '✨'
    desc = 'Sparkle effect'
    order = 170
    fixed_style = 'random'

    def frames(self, grid):
        return generate_pages(grid)
