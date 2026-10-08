"""The page itself. Everything it needs that the backend already knows
(grid size, character set, animation styles, the settings forms) is put into
the page when it's rendered, so the frontend never keeps its own copy."""
from flask import Blueprint, jsonify, render_template, url_for

from config import BAUD_RATE, GRID_ROWS, GRID_COLS, NUM_MODULES
from display.charset import COLOR_TILES, DISPLAY_CHARS, FLAP_CHARS, SECONDS_PER_FLAP, SYMBOL_TILES
from display.debug_commands import DEBUG_COMMANDS
from display.layout import STYLES
from display.module_protocol import (
    BROADCAST, DUMP_FIELDS, GLOBAL_SETTINGS, MODULE_TOGGLES, UNPROVISIONED_ID, Cmd, dump_format, message)

bp = Blueprint('pages', __name__)


def client_config():
    """What the page's scripts read as CONFIG (see constants.js)."""
    dump_by_key = {field.key: field for field in DUMP_FIELDS.values()}
    return {
        'grid_rows': GRID_ROWS,
        'grid_cols': GRID_COLS,
        'num_modules': NUM_MODULES,
        'flap_chars': FLAP_CHARS,
        'display_chars': DISPLAY_CHARS,
        # With each tile's flap code: the black tile is the blank flap (' ').
        'color_tiles': [{'emoji': emoji, 'code': code, 'name': name} for emoji, code, name in COLOR_TILES],
        'symbol_tiles': [{'char': char, 'name': name} for char, _, name in SYMBOL_TILES],
        # Each transition with the order it starts the modules in, for the
        # compose grid's preview (Random's is one random order of many).
        'styles': [{'value': key, 'label': style.label, 'order': style.order()} for key, style in STYLES.items()],
        'seconds_per_flap': SECONDS_PER_FLAP,
        # Bus time each module's start is spaced by, on top of the page's
        # speed (as display/player.py spaces a frame).
        'bus_ms_per_module': (len(message(0, Cmd.DISPLAY_CHAR, 'A')) + 1) * 10 * 1000.0 / BAUD_RATE,
        # The shared settings each module reports in its dump, which the
        # inspector compares with the saved values.
        'timing_fields': [
            {'key': key, 'name': dump_by_key[key].name, 'unit': dump_by_key[key].unit}
            for key, spec in GLOBAL_SETTINGS.items() if spec['type'] == 'int'
        ],
        'dump_format': dump_format(),
        # Everything the Debug page can send (see display/debug_commands.py).
        'debug_commands': DEBUG_COMMANDS,
        'broadcast': BROADCAST,
        'max_module_id': UNPROVISIONED_ID,
    }


@bp.route('/manifest.webmanifest')
def manifest():
    """What a phone needs to put the page on its home screen as an app."""
    icon = lambda name, size, purpose='any': {
        'src': url_for('static', filename=f'icons/{name}'), 'sizes': size, 'type': 'image/png', 'purpose': purpose}
    response = jsonify(
        name='Split-Flap OS',
        short_name='Split-Flap',
        description='Control the split-flap display',
        start_url='/',
        scope='/',
        display='standalone',
        background_color='#121212',
        theme_color='#121212',
        icons=[icon('icon-192.png', '192x192'), icon('icon-512.png', '512x512'),
               icon('icon-maskable-512.png', '512x512', 'maskable')],
    )
    response.mimetype = 'application/manifest+json'
    return response


@bp.route('/')
def index():
    return render_template(
        'index.html',
        config=client_config(),
        debug_commands=DEBUG_COMMANDS,
        firmware_settings=GLOBAL_SETTINGS,
        module_toggles=MODULE_TOGGLES,
    )
