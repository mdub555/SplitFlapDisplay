from flask import Blueprint, jsonify, request

from display.state import state
from settings.store import settings, save_settings
from routes.common import error, json_body

bp = Blueprint('playlist_routes', __name__)


@bp.route('/playlists', methods=['GET', 'POST'])
def playlists():
    if request.method == 'GET':
        return jsonify(settings.get('saved_playlists', {}))
    data = json_body()
    name = (data.get('name') or '').strip()
    if not name:
        return error('Name required', 400)
    playlist = {
        'pages': data.get('pages', []),
        'delay': data.get('delay', 5),
    }
    settings.setdefault('saved_playlists', {})[name] = playlist
    save_settings(settings)
    # Editing the playlist that's playing changes what's on the display too.
    if state.current_target() == f'playlist:{name}':
        state.run_playlist(playlist['pages'], playlist['delay'], name)
    return jsonify(status='saved', name=name)


@bp.route('/playlists/<path:name>', methods=['DELETE'])
def delete_playlist(name):
    plists = settings.get('saved_playlists', {})
    if name in plists:
        del plists[name]
        save_settings(settings)
    return jsonify(status='deleted')


@bp.route('/playlists/<path:name>/run', methods=['POST'])
def run_playlist(name):
    """Plays a saved playlist, under its name so the page can show it."""
    playlist = settings.get('saved_playlists', {}).get(name)
    if playlist is None:
        return error('No such playlist', 404)
    state.run_playlist(playlist.get('pages', []), playlist.get('delay'), name)
    return jsonify(status='running', name=name)
