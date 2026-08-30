from flask import Blueprint, request, jsonify

from config import NUM_MODULES
from display.state import state
from display.serial_link import send_raw

bp = Blueprint('control', __name__)


@bp.route('/current_state')
def current_state():
    return jsonify(**state.snapshot())


@bp.route('/update_playlist', methods=['POST'])
def update_playlist():
    data = request.json or {}
    state.current_playlist = data.get('pages', [])
    state.loop_delay = data.get('delay', 5)
    state.last_sent_page = None
    state.active_app = None
    state.request_stop()
    return jsonify(status='success')


@bp.route('/run_app', methods=['POST'])
def run_app():
    state.active_app = (request.json or {}).get('app')
    state.request_stop()
    return jsonify(status=f"App {state.active_app} started")


@bp.route('/stop_app', methods=['POST'])
def stop_app():
    state.active_app = None
    state.request_stop()
    return jsonify(status='stopped')


@bp.route('/home_all')
def home_all():
    send_raw('m**h')
    state.set_display(' ' * NUM_MODULES, [0] * NUM_MODULES)
    return jsonify(status='Homing All')
