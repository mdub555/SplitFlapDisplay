from flask import Blueprint, request, jsonify

from apps.registry import registry
from settings.store import settings, save_settings

bp = Blueprint('apps_routes', __name__)


def _field_to_json(f):
    return {
        'key': f.key, 'label': f.label, 'type': f.type, 'opts': f.opts,
        'placeholder': f.placeholder, 'min': f.min, 'max': f.max, 'step': f.step,
    }


@bp.route('/apps')
def list_apps():
    """Drives the frontend app grid AND the per-app settings modal — the
    frontend never hardcodes an app list or field config, it just renders
    whatever this returns."""
    return jsonify([
        {
            'key': a.key, 'name': a.name, 'icon': a.icon, 'desc': a.desc,
            'settings_fields': [_field_to_json(f) for f in a.settings_fields],
        }
        for a in registry.list_all()
    ])


@bp.route('/apps/<app_key>/settings', methods=['POST'])
def save_app_settings(app_key):
    app = registry.get(app_key)
    if not app:
        return jsonify(status='error', message='Unknown app'), 404
    data = request.json or {}
    valid_keys = {f.key for f in app.settings_fields}
    settings.update({k: v for k, v in data.items() if k in valid_keys})
    save_settings(settings)
    return jsonify(status='saved')
