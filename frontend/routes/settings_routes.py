import time

from flask import Blueprint, jsonify, request

from apps.base import clean_settings
from config import NUM_MODULES
from settings.store import settings, save_settings
from settings.schema import GLOBAL_FIELDS
from display.module_protocol import UNPROVISIONED_ID, Cmd, message
from display.serial_link import is_connected, read_dump, send_raw
from routes.common import error, json_body
from routes.pages import client_config

bp = Blueprint('settings_routes', __name__)


@bp.route('/config')
def get_config():
    """The page's configuration (see routes/pages.py), plus whether the serial
    link is up. The page itself gets the configuration when it's rendered;
    this is for checking it from outside."""
    return jsonify(**client_config(), hardware_connected=is_connected())


@bp.route('/global_fields')
def global_fields():
    return jsonify([f.to_json() for f in GLOBAL_FIELDS])


@bp.route('/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        try:
            values = clean_settings(GLOBAL_FIELDS, json_body())
        except ValueError as e:
            return error(str(e), 400)
        settings.update(values)
        save_settings(settings)
        return jsonify(status='Saved')
    return jsonify(settings)


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
