from flask import Blueprint, request, jsonify

from settings.store import settings, save_settings

bp = Blueprint('playlist_routes', __name__)


@bp.route('/playlists', methods=['GET', 'POST'])
def playlists():
    if request.method == 'GET':
        return jsonify(settings.get('saved_playlists', {}))
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify(status='error', message='Name required'), 400
    settings.setdefault('saved_playlists', {})[name] = {
        'pages': data.get('pages', []),
        'delay': data.get('delay', 5),
    }
    save_settings(settings)
    return jsonify(status='saved', name=name)


@bp.route('/playlists/<path:name>', methods=['DELETE'])
def delete_playlist(name):
    plists = settings.get('saved_playlists', {})
    if name in plists:
        del plists[name]
        save_settings(settings)
    return jsonify(status='deleted')
