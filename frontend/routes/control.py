from flask import Blueprint, jsonify

from config import NUM_MODULES
from display.state import state
from display.pages import clean_playlist
from display.module_protocol import BROADCAST, Cmd, message
from display.serial_link import send_raw
from routes.common import error, json_body, sse_response

bp = Blueprint('control', __name__)


@bp.route('/current_state')
def current_state():
    """One-off snapshot — handy for a quick curl/debug check. The live UI
    uses /current_state/stream instead so it doesn't have to poll this."""
    return jsonify(**state.snapshot())


@bp.route('/current_state/stream')
def current_state_stream():
    """Pushes a fresh snapshot every time the display actually changes (see
    DisplayState in display/state.py), instead of the frontend polling
    /current_state on a timer."""
    return sse_response(state.subscribe, state.unsubscribe)


@bp.route('/serial_log/stream')
def serial_log_stream():
    """Pushes every serial message, sent or received."""
    return sse_response(state.subscribe_serial, state.unsubscribe_serial, lambda msg: {'msg': msg})


@bp.route('/serial/send', methods=['POST'])
def serial_send():
    """Accepts a command string and sends it over the serial link."""
    cmd = json_body().get('cmd')
    if not cmd:
        return error('No command provided', 400)
    send_raw(cmd)
    return jsonify(status='success')


@bp.route('/update_playlist', methods=['POST'])
def update_playlist():
    try:
        pages, delay = clean_playlist(json_body())
    except ValueError as e:
        return error(str(e), 400)
    state.run_playlist(pages, delay)
    return jsonify(status='success')


@bp.route('/run_app', methods=['POST'])
def run_app():
    state.run_app(json_body().get('app'))
    return jsonify(status=f"App {state.active_app} started")


@bp.route('/stop_app', methods=['POST'])
def stop_app():
    """Stops whatever's running, an app or a playlist."""
    state.stop()
    return jsonify(status='stopped')


@bp.route('/home_all', methods=['POST'])
def home_all():
    send_raw(message(BROADCAST, Cmd.HOME))
    state.set_display(' ' * NUM_MODULES, [0] * NUM_MODULES)
    return jsonify(status='Homing All')
