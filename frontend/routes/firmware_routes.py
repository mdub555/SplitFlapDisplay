from flask import Blueprint, request, jsonify

from settings.store import settings, save_settings
from settings.shared import current_firmware_values
from display.serial_link import send_raw
from display.module_protocol import GLOBAL_SETTINGS, global_command, global_setting_problem
from routes.common import error

bp = Blueprint('firmware_routes', __name__)


def _limits():
    return {
        key: {'type': spec['type'], 'min': spec.get('min'), 'max': spec.get('max')}
        for key, spec in GLOBAL_SETTINGS.items()
    }


@bp.route('/firmware_config', methods=['GET', 'POST'])
def firmware_config():
    """GET: current values plus their limits (the UI builds its validation from
    these). POST: {key: value, ...} for any subset of the global settings —
    validated as a whole, saved, then broadcast to every module."""
    if request.method == 'GET':
        return jsonify(values=current_firmware_values(settings), limits=_limits())

    data = request.json
    if not isinstance(data, dict) or not data:
        return error('No settings provided', 400)
    for key, value in data.items():
        problem = global_setting_problem(key, value)
        if problem:
            return error(problem, 400)

    settings['firmware'] = {**current_firmware_values(settings), **data}
    save_settings(settings)
    for key, value in data.items():
        send_raw(global_command(key, value))
    return jsonify(status='success', values=settings['firmware'])
