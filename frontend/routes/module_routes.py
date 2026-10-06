import time

from flask import Blueprint, request, jsonify

from config import NUM_MODULES
from settings.store import settings, save_settings
from display.serial_link import send_raw, read_dump, read_all_dumps, calibrate_module
from display.module_protocol import TOGGLE_COMMANDS, Cmd, message, toggle_command
from display.state import state
from display.charset import FLAP_CHARS, COLOR_MAP, QUOTE_CHAR, QUOTE_SUBSTITUTE

bp = Blueprint('module_routes', __name__)

# How long a module takes to reboot and answer on the bus again.
REBOOT_WAIT_S = 1.0


@bp.route('/modules/<int:mod_id>/adjust', methods=['POST'])
def adjust_offset(mod_id):
    delta = int((request.json or {}).get('delta', 0))
    mod_id_str = str(mod_id)

    if mod_id_str not in settings['modules']:
        return jsonify(status='error', message='Unprovisioned module'), 404

    new_offset = int(settings['modules'][mod_id_str]['homeOffset']) + delta
    settings['modules'][mod_id_str]['homeOffset'] = new_offset
    save_settings(settings)
    send_raw(message(mod_id, Cmd.SET_OFFSET, new_offset))
    return jsonify(new_offset=new_offset)


@bp.route('/modules/<int:mod_id>/home', methods=['POST'])
def home_one(mod_id):
    send_raw(message(mod_id, Cmd.HOME))
    state.mark_module_char(mod_id, ' ')
    return jsonify(status='Homing')


@bp.route('/modules/<int:mod_id>/identify', methods=['POST'])
def identify(mod_id):
    """Blink the module's status LED for 10 seconds (firmware `b`), to find
    which physical module has this ID. Works for unprovisioned IDs too."""
    send_raw(message(mod_id, Cmd.IDENTIFY))
    return jsonify(status='success')


@bp.route('/modules/<int:mod_id>/exercise', methods=['POST'])
def exercise(mod_id):
    """Step through every flap one at a time, `cycles` times round the reel
    (firmware `e`), for burn-in. Any other move or /stop ends it."""
    cycles = (request.json or {}).get('cycles')
    if not _is_int(cycles) or not 1 <= cycles <= 255:
        return _error('cycles must be an integer from 1 to 255', 400)
    if str(mod_id) not in settings['modules']:
        return _error('Unprovisioned module', 404)
    send_raw(message(mod_id, Cmd.EXERCISE, cycles))
    return jsonify(status='success', cycles=cycles)


@bp.route('/modules/<int:mod_id>/stop', methods=['POST'])
def stop(mod_id):
    """Stop whatever the module's motor is doing (firmware `x`)."""
    send_raw(message(mod_id, Cmd.STOP))
    return jsonify(status='success')


@bp.route('/modules/<int:mod_id>/reboot', methods=['POST'])
def reboot(mod_id):
    """Restart the module (firmware `r`). Its position is unknown afterwards
    unless auto-home is on."""
    send_raw(message(mod_id, Cmd.REBOOT))
    return jsonify(status='success')


@bp.route('/modules/<int:mod_id>/reset_settings', methods=['POST'])
def reset_settings(mod_id):
    """Reset every setting on the module to its firmware default, keeping its
    ID (firmware `!`, which then reboots), and store what it reports."""
    mod_id_str = str(mod_id)
    if mod_id_str not in settings['modules']:
        return jsonify(status='error', message='Unprovisioned module'), 404
    send_raw(message(mod_id, Cmd.RESET_SETTINGS))
    time.sleep(REBOOT_WAIT_S)
    dump = read_dump(mod_id)
    if not dump:
        return jsonify(status='error', message='Reset sent, but the module did not report back'), 504
    settings['modules'][mod_id_str] = dump
    save_settings(settings)
    return jsonify(status='success', settings=settings)


@bp.route('/modules/<int:mod_id>/calibrate', methods=['POST'])
def calibrate(mod_id):
    mod_id_str = str(mod_id)
    if mod_id_str not in settings['modules']:
        return jsonify(status='error', message='Unprovisioned module'), 500
    steps = calibrate_module(mod_id)
    if steps is None:
        return jsonify(status='error', message='Timeout'), 500

    settings['modules'][mod_id_str]['totalSteps'] = steps
    save_settings(settings)
    return jsonify(status='success', steps=steps)


@bp.route('/modules/<int:mod_id>/sync', methods=['POST'])
def sync_one(mod_id):
    dump = read_dump(mod_id)
    if not dump:
        return jsonify(status='failed', settings=settings)

    mod_id_str = str(mod_id)
    settings['modules'][mod_id_str] = dump

    save_settings(settings)
    return jsonify(status='success', settings=settings)


@bp.route('/modules/sync_all', methods=['POST'])
def sync_all():
    """Read every module's dump with one broadcast (each module answers in
    its own time slot), then ask any provisioned module that didn't answer
    on its own, e.g. because it was still moving."""
    dumps = {i: d for i, d in read_all_dumps(NUM_MODULES - 1).items() if i < NUM_MODULES}
    for mod_id_str in list(settings['modules']):
        i = int(mod_id_str)
        if i not in dumps and i < NUM_MODULES:
            dump = read_dump(i)
            if dump:
                dumps[i] = dump
    for i, dump in dumps.items():
        settings['modules'][str(i)] = dump
    save_settings(settings)
    return jsonify(status='success', settings=settings)


@bp.route('/modules/<int:mod_id>/setting', methods=['POST'])
def set_module_setting(mod_id):
    data = request.json or {}
    key = data.get('setting')
    value = data.get('value')

    if not isinstance(key, str) or key not in TOGGLE_COMMANDS:
        return jsonify(status='error', message=f'Unknown setting: {key}'), 400
    # Strict: bool("false") is True, so a stringly-typed value must not slip through.
    if not isinstance(value, bool):
        return jsonify(status='error', message='value must be true or false'), 400

    mod = settings['modules'].get(str(mod_id))
    if mod is None:
        return jsonify(status='error', message='Unprovisioned module'), 404

    send_raw(toggle_command(mod_id, key, value))
    mod[key] = value
    save_settings(settings)
    return jsonify(status='success', setting=key, value=value)


# --- Manual controls in the Hardware Inspector -----------------------------
MAX_TOTAL_STEPS = 32767   # well past any real reel; the firmware accepts up to 65535
NUM_FLAPS = len(FLAP_CHARS)


def _is_int(value):
    # bool is a subclass of int; true/false must not pass as 1/0.
    return isinstance(value, int) and not isinstance(value, bool)


def _error(message, status):
    return jsonify(status='error', message=message), status


def _to_flap_char(value):
    """Normalise one typed character the way display.player.send_to_display
    does for a whole page (uppercase, colour emoji -> codes, " -> q).
    Returns None unless the result is a single character that has a flap."""
    if not isinstance(value, str):
        return None
    text = value.upper()
    for emoji, code in COLOR_MAP.items():
        text = text.replace(emoji, code)
    text = text.replace(QUOTE_CHAR, QUOTE_SUBSTITUTE)
    return text if len(text) == 1 and text in FLAP_CHARS else None


@bp.route('/modules/<int:mod_id>/total_steps', methods=['POST'])
def set_total_steps(mod_id):
    steps = (request.json or {}).get('steps')
    if not _is_int(steps) or not 1 <= steps <= MAX_TOTAL_STEPS:
        return _error(f'steps must be an integer from 1 to {MAX_TOTAL_STEPS}', 400)

    mod = settings['modules'].get(str(mod_id))
    if mod is None:
        return _error('Unprovisioned module', 404)

    send_raw(message(mod_id, Cmd.SET_TOTAL_STEPS, steps))
    mod['totalSteps'] = steps
    save_settings(settings)
    return jsonify(status='success', steps=steps)


@bp.route('/modules/<int:mod_id>/display', methods=['POST'])
def display_on_module(mod_id):
    """Show one flap, given either {"char": "A"} or {"index": 7}."""
    data = request.json or {}
    if ('char' in data) == ('index' in data):
        return _error('Provide exactly one of char or index', 400)

    if 'index' in data:
        index = data['index']
        if not _is_int(index) or not 0 <= index < NUM_FLAPS:
            return _error(f'index must be an integer from 0 to {NUM_FLAPS - 1}', 400)
        char = FLAP_CHARS[index]
        command = message(mod_id, Cmd.DISPLAY_INDEX, index)
    else:
        char = _to_flap_char(data['char'])
        if char is None:
            return _error('char must be a single character that has a flap', 400)
        command = message(mod_id, Cmd.DISPLAY_CHAR, char)

    if str(mod_id) not in settings['modules']:
        return _error('Unprovisioned module', 404)

    send_raw(command)
    state.mark_module_char(mod_id, char)
    return jsonify(status='success', char=char, index=FLAP_CHARS.index(char))


@bp.route('/modules/<int:mod_id>/goto_step', methods=['POST'])
def goto_step(mod_id):
    """Move to a raw step position (firmware `g`). Only ever moves forward."""
    step = (request.json or {}).get('step')
    if not _is_int(step) or step < 0:
        return _error('step must be a non-negative integer', 400)

    mod = settings['modules'].get(str(mod_id))
    if mod is None:
        return _error('Unprovisioned module', 404)
    total = mod.get('totalSteps')
    if _is_int(total) and step >= total:
        return _error(f'step must be less than total steps ({total})', 400)

    send_raw(message(mod_id, Cmd.MOVE_TO_STEP, step))
    return jsonify(status='success', step=step)
