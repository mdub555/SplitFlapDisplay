from flask import Blueprint, request, jsonify

from settings.store import settings, save_settings
from display.serial_link import send_raw
from display.module_protocol import GLOBAL_SETTINGS, global_command
from routes.common import error, is_int

bp = Blueprint('firmware_routes', __name__)


def _current_values():
    """Stored global firmware settings, with defaults for anything missing
    (a settings.json from before these existed, or a partial dict)."""
    stored = settings.get('firmware') or {}
    return {key: stored.get(key, spec['default']) for key, spec in GLOBAL_SETTINGS.items()}


def _limits():
    return {
        key: {'type': spec['type'], 'min': spec.get('min'), 'max': spec.get('max')}
        for key, spec in GLOBAL_SETTINGS.items()
    }


def _validate(key, value):
    """Returns an error message, or None if `value` is acceptable for `key`."""
    spec = GLOBAL_SETTINGS.get(key)
    if spec is None:
        return f'Unknown setting: {key}'
    if spec['type'] == 'bool':
        # Strict: bool("false") is True, so stringly-typed values must not slip through.
        return None if isinstance(value, bool) else f'{key} must be true or false'
    if not is_int(value) or not spec['min'] <= value <= spec['max']:
        return f"{key} must be an integer from {spec['min']} to {spec['max']}"
    return None


@bp.route('/firmware_config', methods=['GET', 'POST'])
def firmware_config():
    """GET: current values plus their limits (the UI builds its validation from
    these). POST: {key: value, ...} for any subset of the global settings —
    validated as a whole, saved, then broadcast to every module."""
    if request.method == 'GET':
        return jsonify(values=_current_values(), limits=_limits())

    data = request.json
    if not isinstance(data, dict) or not data:
        return error('No settings provided', 400)
    for key, value in data.items():
        problem = _validate(key, value)
        if problem:
            return error(problem, 400)

    settings['firmware'] = {**_current_values(), **data}
    save_settings(settings)
    for key, value in data.items():
        send_raw(global_command(key, value))
    return jsonify(status='success', values=settings['firmware'])
