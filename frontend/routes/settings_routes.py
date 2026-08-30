from flask import Blueprint, request, jsonify

from config import GRID_ROWS, GRID_COLS, NUM_MODULES
from settings.store import settings, save_settings
from settings.schema import GLOBAL_FIELDS
from display.serial_link import send_raw, is_connected

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
    return jsonify([
        {'key': f.key, 'label': f.label, 'type': f.type, 'opts': f.opts,
         'placeholder': f.placeholder, 'default': f.default}
        for f in GLOBAL_FIELDS
    ])


@bp.route('/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.json or {}
        global_keys = {f.key for f in GLOBAL_FIELDS}
        settings.update({k: v for k, v in data.items() if k in global_keys})
        save_settings(settings)
        return jsonify(status='Saved')
    return jsonify(settings)


@bp.route('/toggle_autohome', methods=['POST'])
def toggle_autohome():
    enabled = (request.json or {}).get('enabled', True)
    settings['auto_home'] = enabled
    save_settings(settings)
    send_raw(f"m**a{1 if enabled else 0}")
    return jsonify(status='Auto-home updated')
