from apps.base import App, Frame
from apps.builtin._shared import center_page, matrix_burst_frames
from apps.builtin.animations.rainbow import generate_pages as rainbow_pages
from apps.builtin.animations.sweep import generate_pages as sweep_pages
from apps.builtin.animations.twinkle import generate_pages as twinkle_pages
from config import GRID_ROWS, GRID_COLS, NUM_MODULES


class DemoApp(App):
    key = 'demo'
    name = 'Demo'
    icon = '🎬'
    desc = 'YouTube showcase'

    def get_pages(self, settings, cache):
        # NOTE: every call rebuilds and re-runs the full sequence, including
        # the lead-in pause — so this loops the whole thing (pause included)
        # each time the playlist loop re-requests pages, matching the old
        # script's "loop forever" behaviour. If you want the 8s lead-in only
        # on the very first run, gate it with a `cache['demo_started']` flag.
        frames = [Frame(text='', delay=8)]

        frames.append(Frame(text=center_page('SPLIT  FLAP'), delay=1, style='ltr'))
        frames.append(Frame(text=center_page('SPLIT  FLAP', 'DISPLAY'), delay=5, style='center_out'))

        frames += [Frame(text=p, delay=0.5, style='columns', raw=True) for p in rainbow_pages() * 3]

        frames.append(Frame(text=center_page('HANDMADE WITH', f'{NUM_MODULES} MODULES', 'EACH ONE UNIQUE'),
                             delay=5, style='spiral'))

        frames += [Frame(text=p, delay=0.2, raw=True) for p in sweep_pages()]

        frames.append(Frame(
            text=center_page(f"{GRID_ROWS} ROWS OF {GRID_COLS}", 'CHARACTERS', f"= {NUM_MODULES} TOTAL"),
            delay=4, style='rain'))

        frames.append(Frame(text=center_page('REAL TIME', 'DATA APPS', 'BUILT IN'), delay=5, style='rtl'))

        frames += matrix_burst_frames(
            center_page('POWERED BY', 'ARDUINO &', 'RASPBERRY PI'), reveal_style='outside_in')

        frames += [Frame(text=p, delay=0.45, style='random', raw=True) for p in twinkle_pages(10)]

        frames.append(Frame(text=center_page('ABCDEFGHIJKLMN', 'OPQRSTUVWXYZ', '0123456789!@#$&'),
                             delay=5, style='columns'))

        frames += matrix_burst_frames(center_page('', 'SUBSCRIBE!', ''), reveal_style='center_out')

        frames.append(Frame(text=center_page('', 'THANKS FOR', 'WATCHING!'), delay=6, style='center_out'))

        return frames
