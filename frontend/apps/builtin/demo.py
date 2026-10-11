from apps.base import App, Frame
from apps.builtin._shared import matrix_burst_frames
from apps.builtin.animations.rainbow import generate_pages as rainbow_pages
from apps.builtin.animations.sweep import generate_pages as sweep_pages
from apps.builtin.animations.twinkle import generate_pages as twinkle_pages


class DemoApp(App):
    key = 'demo'
    name = 'Demo'
    icon = '🎬'
    desc = 'YouTube showcase'
    order = 10

    def get_pages(self, settings, cache, grid):
        # NOTE: every call rebuilds and re-runs the full sequence, including
        # the lead-in pause — so this loops the whole thing (pause included)
        # each time the playlist loop re-requests pages, matching the old
        # script's "loop forever" behaviour. If you want the 8s lead-in only
        # on the very first run, gate it with a `cache['demo_started']` flag.
        frames = [Frame(text=grid.page(), delay=8)]

        frames.append(Frame(text=grid.page('SPLIT  FLAP'), delay=1, style='ltr'))
        frames.append(Frame(text=grid.page('SPLIT  FLAP', 'DISPLAY'), delay=5, style='center_out'))

        frames += [Frame(text=p, delay=0.5, style='columns', raw=True) for p in rainbow_pages(grid) * 3]

        frames.append(Frame(text=grid.page('HANDMADE WITH', f'{grid.size} MODULES', 'EACH ONE UNIQUE'),
                             delay=5, style='spiral'))

        frames += [Frame(text=p, delay=0.2, raw=True) for p in sweep_pages(grid)]

        frames.append(Frame(
            text=grid.page(f"{grid.rows} ROWS OF {grid.cols}", 'CHARACTERS', f"= {grid.size} TOTAL"),
            delay=4, style='rain'))

        frames.append(Frame(text=grid.page('REAL TIME', 'DATA APPS', 'BUILT IN'), delay=5, style='rtl'))

        frames += matrix_burst_frames(
            grid, grid.page('POWERED BY', 'ARDUINO &', 'RASPBERRY PI'), reveal_style='outside_in')

        frames += [Frame(text=p, delay=0.45, style='random', raw=True) for p in twinkle_pages(grid, 10)]

        frames.append(Frame(text=grid.page('ABCDEFGHIJKLMN', 'OPQRSTUVWXYZ', '0123456789!@#$&'),
                             delay=5, style='columns'))

        frames += matrix_burst_frames(grid, grid.page('', 'SUBSCRIBE!', ''), reveal_style='center_out')

        frames.append(Frame(text=grid.page('', 'THANKS FOR', 'WATCHING!'), delay=6, style='center_out'))

        return frames
