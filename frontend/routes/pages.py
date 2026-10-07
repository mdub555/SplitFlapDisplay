"""The page itself. Everything it needs that the backend already knows
(grid size, character set, animation styles, the settings forms) is put into
the page when it's rendered, so the frontend never keeps its own copy."""
from flask import Blueprint, render_template

from config import GRID_ROWS, GRID_COLS, NUM_MODULES
from display.charset import COLOR_TILES, DISPLAY_CHARS, FLAP_CHARS
from display.layout import STYLES
from display.module_protocol import (
    BROADCAST, DUMP_FIELDS, GLOBAL_SETTINGS, MODULE_TOGGLES, Cmd, dump_format, message)

bp = Blueprint('pages', __name__)

# The serial debug panel's quick commands: (message, label).
DEBUG_COMMANDS = [
    (message(BROADCAST, Cmd.HOME), 'Home All'),
    (message(1, Cmd.DUMP_STATE), 'Dump Mod 01'),
    (message(1, Cmd.CALIBRATE), 'Calib Mod 01'),
]


def client_config():
    """What the page's scripts read as CONFIG (see constants.js)."""
    dump_by_key = {field.key: field for field in DUMP_FIELDS.values()}
    return {
        'grid_rows': GRID_ROWS,
        'grid_cols': GRID_COLS,
        'num_modules': NUM_MODULES,
        'flap_chars': FLAP_CHARS,
        'display_chars': DISPLAY_CHARS,
        'color_tiles': [{'emoji': emoji, 'name': name} for emoji, _, name in COLOR_TILES],
        'styles': [{'value': key, 'label': style.label} for key, style in STYLES.items()],
        # The shared settings each module reports in its dump, which the
        # inspector compares with the saved values.
        'timing_fields': [
            {'key': key, 'name': dump_by_key[key].name, 'unit': dump_by_key[key].unit}
            for key, spec in GLOBAL_SETTINGS.items() if spec['type'] == 'int'
        ],
        'dump_format': dump_format(),
    }


@bp.route('/')
def index():
    return render_template(
        'index.html',
        config=client_config(),
        debug_commands=DEBUG_COMMANDS,
        firmware_settings=GLOBAL_SETTINGS,
        module_toggles=MODULE_TOGGLES,
    )
