import time

from flask import Blueprint, jsonify

from config import GRID_ROWS, GRID_COLS, NUM_MODULES
from settings.store import settings, save_settings
from settings.schema import GLOBAL_FIELDS
from display.module_protocol import BROADCAST, UNPROVISIONED_ID, Cmd, message
from display.serial_link import is_connected, read_dump, send_raw
from routes.common import error, json_body

bp = Blueprint('settings_routes', __name__)


@bp.route('/config')
def get_config():
    """Static config the frontend needs at load time — grid size drives all
    dynamic grid rendering client-side instead of hardcoding 45/15/3."""
    return jsonify(
        grid_rows=GRID_ROWS,
        grid_cols=GRID_COLS,
        num_modules=NUM_MODULES,
        hardware_connected=is_connected(),
    )


@bp.route('/global_fields')
def global_fields():
    return jsonify([f.to_json() for f in GLOBAL_FIELDS])


@bp.route('/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = json_body()
        global_keys = {f.key for f in GLOBAL_FIELDS}
        settings.update({k: v for k, v in data.items() if k in global_keys})
        save_settings(settings)
        return jsonify(status='Saved')
    return jsonify(settings)


@bp.route('/toggle_autohome', methods=['POST'])
def toggle_autohome():
    enabled = json_body().get('enabled', True)
    settings['auto_home'] = enabled

    # Sync with per-module autoHome
    for mod_id in settings['modules']:
        settings['modules'][mod_id]['autoHome'] = enabled

    save_settings(settings)
    send_raw(message(BROADCAST, Cmd.SET_AUTO_HOME, 1 if enabled else 0))
    return jsonify(status='Auto-home updated')


@bp.route('/provision_module', methods=['POST'])
def provision_module():
    """Give the unprovisioned module on the bus an ID: the one in the request,
    or the first free one."""
    if not is_connected():
        return error('Hardware not connected', 503)

    target_id = json_body().get('id')
    if target_id is not None:
        new_id = int(target_id)
        if str(new_id) in settings['modules']:
            return error('Module already provisioned', 400)
    else:
        existing = {int(k) for k in settings['modules']}
        new_id = next((i for i in range(NUM_MODULES) if i not in existing), None)
        if new_id is None:
            return error('All module slots are already filled', 400)

    # 1. Confirm an unprovisioned module is present
    dump = read_dump(UNPROVISIONED_ID, timeout=2.0)
    if dump is None:
        return error('No unprovisioned module found on bus', 404)

    # 2. Assign it the target ID
    send_raw(message(UNPROVISIONED_ID, Cmd.SET_MODULE_ID, new_id))
    time.sleep(0.2)

    # 3. Use its current settings from hardware
    settings['modules'][str(new_id)] = dump
    save_settings(settings)

    return jsonify(status='success', assigned_id=new_id)
