from flask import Blueprint, request, jsonify

from config import NUM_MODULES
from settings.store import settings, save_settings
from display.serial_link import send_raw, read_dump, calibrate_module
from display.state import state

bp = Blueprint('module_routes', __name__)


@bp.route('/modules/<int:mod_id>/adjust', methods=['POST'])
def adjust_offset(mod_id):
    delta = int((request.json or {}).get('delta', 0))
    new_offset = int(settings['offsets'].get(str(mod_id), 2832)) + delta
    settings['offsets'][str(mod_id)] = new_offset
    save_settings(settings)
    send_raw(f"m{mod_id:02d}o{new_offset}")
    return jsonify(new_offset=new_offset)


@bp.route('/modules/<int:mod_id>/home', methods=['POST'])
def home_one(mod_id):
    send_raw(f"m{mod_id:02d}h")
    state.mark_module_char(mod_id, ' ')
    return jsonify(status='Homing')


@bp.route('/modules/<int:mod_id>/calibrate', methods=['POST'])
def calibrate(mod_id):
    steps = calibrate_module(mod_id)
    if steps is None:
        return jsonify(status='error', message='Timeout'), 500
    settings['calibrations'][str(mod_id)] = steps
    save_settings(settings)
    return jsonify(status='success', steps=steps)


@bp.route('/modules/<int:mod_id>/sync', methods=['POST'])
def sync_one(mod_id):
    dump = read_dump(mod_id)
    if not dump:
        return jsonify(status='failed', settings=settings)
    settings['offsets'][str(mod_id)] = dump['home_offset']
    settings['calibrations'][str(mod_id)] = dump['total_steps']
    save_settings(settings)
    return jsonify(status='success', settings=settings)


@bp.route('/modules/sync_all', methods=['POST'])
def sync_all():
    for i in range(NUM_MODULES):
        dump = read_dump(i)
        if dump:
            settings['offsets'][str(i)] = dump['home_offset']
            settings['calibrations'][str(i)] = dump['total_steps']
    save_settings(settings)
    return jsonify(status='success', settings=settings)


@bp.route('/assign_id', methods=['POST'])
def assign_id():
    send_raw(f"m**i{int((request.json or {}).get('id', 0)):02d}")
    return jsonify(status='ID Assigned')
