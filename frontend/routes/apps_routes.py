from flask import Blueprint, jsonify

from apps.base import clean_settings
from apps.registry import registry
from settings.store import settings, save_settings
from routes.common import error, json_body

bp = Blueprint('apps_routes', __name__)


@bp.route('/apps')
def list_apps():
    """Drives the frontend app grid AND the per-app settings modal — the
    frontend never hardcodes an app list or field config, it just renders
    whatever this returns."""
    return jsonify([
        {
            'key': a.key, 'name': a.name, 'icon': a.icon, 'desc': a.desc,
            'settings_fields': [f.to_json() for f in a.settings_fields],
        }
        for a in registry.list_all()
    ])


@bp.route('/apps/<app_key>/settings', methods=['POST'])
def save_app_settings(app_key):
    app = registry.get(app_key)
    if not app:
        return error('Unknown app', 404)
    try:
        values = clean_settings(app.settings_fields, json_body())
    except ValueError as e:
        return error(str(e), 400)
    settings.update(values)
    save_settings(settings)
    return jsonify(status='saved')
