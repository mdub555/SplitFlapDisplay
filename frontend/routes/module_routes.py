import functools
import time

from flask import Blueprint, jsonify

from config import NUM_MODULES
from settings.store import settings, save_settings
from display.serial_link import send_raw, read_dump, read_all_dumps, read_flap_offsets, calibrate_module
from display.module_protocol import (
    FLAP_OFFSET_MAX, FLAP_OFFSET_MIN, TOGGLE_COMMANDS, Cmd, flap_offset_message, message, toggle_command)
from display.state import state
from display.charset import FLAP_CHARS, NUM_FLAPS, to_flap_char
from routes.common import error, is_int, json_body

bp = Blueprint('module_routes', __name__)

# How long a module takes to reboot and answer on the bus again.
REBOOT_WAIT_S = 1.0

# Well past any real reel; the firmware accepts up to 65535.
MAX_TOTAL_STEPS = 32767

# How long to wait for a module to finish a move and report its flap
# offsets: long enough to home first (up to two revolutions) or to lower an
# offset (nearly one).
FLAP_MOVE_TIMEOUT_S = 15.0


def provisioned(view):
    """Route decorator for a module that must be provisioned: passes its
    stored settings to the view as `mod`, or answers 404."""
    @functools.wraps(view)
    def wrapper(mod_id):
        mod = settings['modules'].get(str(mod_id))
        if mod is None:
            return error('Unprovisioned module', 404)
        return view(mod_id, mod)
    return wrapper


def _store_dump(mod_id, dump):
    """Saves a module's dump as its stored settings."""
    settings['modules'][str(mod_id)] = dump
    save_settings(settings)


# --- Commands that work on any module ID -----------------------------------

@bp.route('/modules/<int:mod_id>/home', methods=['POST'])
def home_one(mod_id):
    send_raw(message(mod_id, Cmd.HOME))
    state.mark_module_char(mod_id, ' ')
    return jsonify(status='Homing')


@bp.route('/modules/<int:mod_id>/identify', methods=['POST'])
def identify(mod_id):
    """Blink the module's status LED for 10 seconds, to find which physical
    module has this ID. Works for unprovisioned IDs too."""
    send_raw(message(mod_id, Cmd.IDENTIFY))
    return jsonify(status='success')


@bp.route('/modules/<int:mod_id>/stop', methods=['POST'])
def stop(mod_id):
    """Stop whatever the module's motor is doing."""
    send_raw(message(mod_id, Cmd.STOP))
    return jsonify(status='success')


@bp.route('/modules/<int:mod_id>/reboot', methods=['POST'])
def reboot(mod_id):
    """Restart the module. Its position is unknown afterwards unless
    auto-home is on."""
    send_raw(message(mod_id, Cmd.REBOOT))
    return jsonify(status='success')


@bp.route('/modules/<int:mod_id>/sync', methods=['POST'])
def sync_one(mod_id):
    """Read the module's dump and store it as its settings."""
    dump = read_dump(mod_id)
    state.sync_result(mod_id, bool(dump))
    if not dump:
        return error('The module did not report back', 504)
    _store_dump(mod_id, dump)
    return jsonify(status='success', settings=settings)


# --- Per-flap offsets (the Debug page's flap offset tuner) -------------------
# These work on any module ID, like the Debug page. Each one answers with
# every flap's offset, read back once the module has stopped moving.

def _flap_number(value, lowest=0):
    """`value` as a flap index from `lowest` to the last flap, or None."""
    return value if is_int(value) and lowest <= value < NUM_FLAPS else None


@bp.route('/modules/<int:mod_id>/flap_offsets', methods=['GET'])
def flap_offsets(mod_id):
    """Every flap's offset, in steps."""
    offsets = read_flap_offsets(mod_id)
    if offsets is None:
        return error('The module did not report back', 504)
    return jsonify(offsets=offsets)


@bp.route('/modules/<int:mod_id>/show_flap', methods=['POST'])
def show_flap(mod_id):
    """Show flap `flap` (its offset included), and answer once it's there."""
    flap = _flap_number(json_body().get('flap'))
    if flap is None:
        return error(f'flap must be an integer from 0 to {NUM_FLAPS - 1}', 400)
    offsets = read_flap_offsets(mod_id, before=[message(mod_id, Cmd.DISPLAY_INDEX, flap)],
                                timeout=FLAP_MOVE_TIMEOUT_S)
    # Sent either way, so the live display follows it.
    state.mark_module_char(mod_id, FLAP_CHARS[flap])
    if offsets is None:
        return error('The module did not report back', 504)
    return jsonify(flap=flap, offsets=offsets)


@bp.route('/modules/<int:mod_id>/flap_offset', methods=['POST'])
def set_flap_offset(mod_id):
    """Set flap `flap`'s offset to `offset` steps. The module moves to the
    flap's new position."""
    data = json_body()
    flap = _flap_number(data.get('flap'), lowest=1)
    offset = data.get('offset')
    if flap is None:
        # Flap 0 is where homing ends: the home offset places it.
        return error(f'flap must be an integer from 1 to {NUM_FLAPS - 1}', 400)
    if not is_int(offset) or not FLAP_OFFSET_MIN <= offset <= FLAP_OFFSET_MAX:
        return error(f'offset must be an integer from {FLAP_OFFSET_MIN} to {FLAP_OFFSET_MAX}', 400)
    # The module sets the offset of the flap it's showing, and ignores the
    # offset mid-move, so show the flap and wait for it to arrive first.
    offsets = read_flap_offsets(mod_id, before=[message(mod_id, Cmd.DISPLAY_INDEX, flap)],
                                timeout=FLAP_MOVE_TIMEOUT_S)
    if offsets is not None:
        offsets = read_flap_offsets(mod_id, before=[flap_offset_message(mod_id, offset)],
                                    timeout=FLAP_MOVE_TIMEOUT_S)
    if offsets is None:
        return error('The module did not report back', 504)
    state.mark_module_char(mod_id, FLAP_CHARS[flap])
    if offsets[flap] != offset:
        return error(f'The module did not take the offset (flap {flap} is still at {offsets[flap]})', 409)
    return jsonify(flap=flap, offsets=offsets)


@bp.route('/modules/sync_all', methods=['POST'])
def sync_all():
    """Read every module's dump with one broadcast (each module answers in
    its own time slot), then ask any provisioned module that didn't answer
    on its own, e.g. because it was still moving. Each module's result goes
    out over the live state as it comes in (see DisplayState.sync_result), so
    the Modules page can show the sync's progress. A provisioned module that
    never answers has failed; its stored settings are kept."""
    def answered(mod_id, dump):
        if mod_id < NUM_MODULES:
            state.sync_result(mod_id, True)

    state.start_sync()
    try:
        dumps = {i: d for i, d in read_all_dumps(NUM_MODULES - 1, on_reply=answered).items()
                 if i < NUM_MODULES}
        failed = []
        for mod_id_str in list(settings['modules']):
            i = int(mod_id_str)
            if i not in dumps and i < NUM_MODULES:
                dump = read_dump(i)
                state.sync_result(i, bool(dump))
                if dump:
                    dumps[i] = dump
                else:
                    failed.append(i)
        for i, dump in dumps.items():
            settings['modules'][str(i)] = dump
        save_settings(settings)
    finally:
        state.finish_sync()
    return jsonify(status='success', settings=settings, synced=sorted(dumps), failed=sorted(failed))


# --- Commands for a provisioned module --------------------------------------

@bp.route('/modules/<int:mod_id>/adjust', methods=['POST'])
@provisioned
def adjust_offset(mod_id, mod):
    """Move the home offset by `delta` steps."""
    delta = json_body().get('delta')
    if not is_int(delta):
        return error('delta must be an integer', 400)
    total = mod.get('totalSteps') if is_int(mod.get('totalSteps')) else MAX_TOTAL_STEPS + 1
    new_offset = int(mod['homeOffset']) + delta
    # 0 isn't a usable offset: the firmware reads "O0" as "make here flap 0".
    if not 1 <= new_offset < total:
        return error(f'The offset must stay between 1 and {total - 1}', 400)
    send_raw(message(mod_id, Cmd.SET_OFFSET, new_offset))
    mod['homeOffset'] = new_offset
    save_settings(settings)
    return jsonify(new_offset=new_offset)


@bp.route('/modules/<int:mod_id>/exercise', methods=['POST'])
@provisioned
def exercise(mod_id, mod):
    """Step through every flap one at a time, `cycles` times round the reel,
    for burn-in. Any other move or /stop ends it."""
    cycles = json_body().get('cycles')
    if not is_int(cycles) or not 1 <= cycles <= 255:
        return error('cycles must be an integer from 1 to 255', 400)
    send_raw(message(mod_id, Cmd.EXERCISE, cycles))
    return jsonify(status='success', cycles=cycles)


@bp.route('/modules/<int:mod_id>/reset_settings', methods=['POST'])
@provisioned
def reset_settings(mod_id, mod):
    """Reset every setting on the module to its firmware default, keeping its
    ID (the module then reboots), and store what it reports."""
    send_raw(message(mod_id, Cmd.RESET_SETTINGS))
    time.sleep(REBOOT_WAIT_S)
    dump = read_dump(mod_id)
    if not dump:
        return error('Reset sent, but the module did not report back', 504)
    _store_dump(mod_id, dump)
    return jsonify(status='success', settings=settings)


@bp.route('/modules/<int:mod_id>/calibrate', methods=['POST'])
@provisioned
def calibrate(mod_id, mod):
    """Measure the steps in one revolution and store them."""
    steps = calibrate_module(mod_id)
    if steps is None:
        return error('Calibration timed out', 504)
    mod['totalSteps'] = steps
    save_settings(settings)
    return jsonify(status='success', steps=steps)


@bp.route('/modules/<int:mod_id>/setting', methods=['POST'])
@provisioned
def set_module_setting(mod_id, mod):
    """Set one of the module's on/off settings (see TOGGLE_COMMANDS)."""
    data = json_body()
    key = data.get('setting')
    value = data.get('value')
    if not isinstance(key, str) or key not in TOGGLE_COMMANDS:
        return error(f'Unknown setting: {key}', 400)
    # Strict: bool("false") is True, so a stringly-typed value must not slip through.
    if not isinstance(value, bool):
        return error('value must be true or false', 400)
    send_raw(toggle_command(mod_id, key, value))
    mod[key] = value
    save_settings(settings)
    return jsonify(status='success', setting=key, value=value)


@bp.route('/modules/<int:mod_id>/total_steps', methods=['POST'])
@provisioned
def set_total_steps(mod_id, mod):
    steps = json_body().get('steps')
    if not is_int(steps) or not 1 <= steps <= MAX_TOTAL_STEPS:
        return error(f'steps must be an integer from 1 to {MAX_TOTAL_STEPS}', 400)
    send_raw(message(mod_id, Cmd.SET_TOTAL_STEPS, steps))
    mod['totalSteps'] = steps
    save_settings(settings)
    return jsonify(status='success', steps=steps)


@bp.route('/modules/<int:mod_id>/display', methods=['POST'])
@provisioned
def display_on_module(mod_id, mod):
    """Show one flap, given either {"char": "A"} or {"index": 7}."""
    data = json_body()
    if ('char' in data) == ('index' in data):
        return error('Provide exactly one of char or index', 400)

    if 'index' in data:
        index = data['index']
        if not is_int(index) or not 0 <= index < NUM_FLAPS:
            return error(f'index must be an integer from 0 to {NUM_FLAPS - 1}', 400)
        char = FLAP_CHARS[index]
        command = message(mod_id, Cmd.DISPLAY_INDEX, index)
    else:
        char = to_flap_char(data['char'])
        if char is None:
            return error('char must be a single character that has a flap', 400)
        command = message(mod_id, Cmd.DISPLAY_CHAR, char)

    send_raw(command)
    state.mark_module_char(mod_id, char)
    return jsonify(status='success', char=char, index=FLAP_CHARS.index(char))


@bp.route('/modules/<int:mod_id>/goto_step', methods=['POST'])
@provisioned
def goto_step(mod_id, mod):
    """Move to a raw step position. Only ever moves forward."""
    step = json_body().get('step')
    if not is_int(step) or step < 0:
        return error('step must be a non-negative integer', 400)
    total = mod.get('totalSteps')
    if is_int(total) and step >= total:
        return error(f'step must be less than total steps ({total})', 400)
    send_raw(message(mod_id, Cmd.MOVE_TO_STEP, step))
    return jsonify(status='success', step=step)
