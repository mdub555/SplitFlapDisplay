from flask import Blueprint, jsonify, request

from display.pages import clean_playlist
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
    try:
        pages, delay = clean_playlist(data)
    except ValueError as e:
        return error(str(e), 400)
    playlist = {'pages': pages, 'delay': delay}
    settings.setdefault('saved_playlists', {})[name] = playlist
    save_settings(settings)
    # Editing the playlist that's playing changes what's on the display too.
    if state.current_target() == f'playlist:{name}':
        state.run_playlist(playlist['pages'], playlist['delay'], name)
    return jsonify(status='saved', name=name)


@bp.route('/playlists/<path:name>', methods=['DELETE'])
def delete_playlist(name):
    """Deletes a saved playlist, and answers with it, so the page can offer
    to undo (by saving it again)."""
    plists = settings.get('saved_playlists', {})
    deleted = plists.pop(name, None)
    if deleted is not None:
        save_settings(settings)
    return jsonify(status='deleted', playlist=deleted)


@bp.route('/playlists/<path:name>/rename', methods=['POST'])
def rename_playlist(name):
    """Renames a saved playlist, keeping its place in the list, and
    everything that refers to it: the schedule's slots and default, and the
    playlist that's playing."""
    plists = settings.get('saved_playlists', {})
    if name not in plists:
        return error('No such playlist', 404)
    new = (json_body().get('name') or '').strip()
    if not new:
        return error('Name required', 400)
    if new == name:
        return jsonify(status='renamed', name=new, schedule_updated=0)
    if new in plists:
        return error(f'There is already a playlist called "{new}"', 409)
    settings['saved_playlists'] = {(new if key == name else key): value for key, value in plists.items()}

    old_target, new_target = f'playlist:{name}', f'playlist:{new}'
    updated = 0
    schedule = settings.get('schedule')
    if schedule:
        for entry in schedule.get('entries', []):
            if entry.get('target') == old_target:
                entry['target'] = new_target
                updated += 1
        if schedule.get('default') == old_target:
            schedule['default'] = new_target
            updated += 1
    save_settings(settings)
    state.rename_playlist(name, new)
    return jsonify(status='renamed', name=new, schedule_updated=updated)


@bp.route('/playlists/<path:name>/run', methods=['POST'])
def run_playlist(name):
    """Plays a saved playlist, under its name so the page can show it."""
    playlist = settings.get('saved_playlists', {}).get(name)
    if playlist is None:
        return error('No such playlist', 404)
    state.run_playlist(playlist.get('pages', []), playlist.get('delay'), name)
    return jsonify(status='running', name=name)
