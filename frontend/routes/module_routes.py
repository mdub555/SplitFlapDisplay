from flask import Blueprint, request, jsonify

from config import NUM_MODULES
from settings.store import settings, save_settings
from display.serial_link import send_raw, read_dump, calibrate_module
from display.state import state

bp = Blueprint('module_routes', __name__)


@bp.route('/modules/<int:mod_id>/adjust', methods=['POST'])
def adjust_offset(mod_id):
    delta = int((request.json or {}).get('delta', 0))
    mod_id_str = str(mod_id)

    if mod_id_str not in settings['modules']:
        return jsonify(status='failed', settings=settings)

    new_offset = int(settings['modules'][mod_id_str]['homeOffset']) + delta
    settings['modules'][mod_id_str]['homeOffset'] = new_offset
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
    for i in range(NUM_MODULES):
        dump = read_dump(i)
        if dump:
            mod_id_str = str(i)
            settings['modules'][mod_id_str] = dump
    save_settings(settings)
    return jsonify(status='success', settings=settings)


@bp.route('/assign_id', methods=['POST'])
def assign_id():
    send_raw(f"m**i{int((request.json or {}).get('id', 0)):02d}")
    return jsonify(status='ID Assigned')
