import json
import queue

from flask import Blueprint, Response, request, jsonify, stream_with_context

from config import NUM_MODULES
from display.state import state
from display.serial_link import send_raw

bp = Blueprint('control', __name__)


@bp.route('/current_state')
def current_state():
    """One-off snapshot — handy for a quick curl/debug check. The live UI
    uses /current_state/stream instead so it doesn't have to poll this."""
    return jsonify(**state.snapshot())


@bp.route('/current_state/stream')
def current_state_stream():
    """Server-Sent Events stream: pushes a fresh snapshot every time the
    display actually changes (see DisplayState._broadcast in display/state.py), instead of the
    frontend polling /current_state on a timer. A heartbeat comment goes out
    every 15s so idle proxies/browsers don't treat the connection as dead.

    Requires the Flask dev server to run with threaded=True (see app.py) —
    each open SSE connection holds its thread for as long as the browser tab
    stays on the page, so a single-worker server would serve exactly one
    client before every other request starts blocking behind it. The same
    caveat applies to a production WSGI server: a sync worker pool needs
    enough threads/workers to cover concurrent SSE clients, especially
    with many open tabs.
    """
    def gen():
        q = state.subscribe()
        try:
            while True:
                try:
                    data = q.get(timeout=15)
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            state.unsubscribe(q)

    return Response(
        stream_with_context(gen()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@bp.route('/serial_log/stream')
def serial_log_stream():
    """Server-Sent Events stream: pushes every serial message (sent/received)."""
    def gen():
        q = state.subscribe_serial()
        try:
            while True:
                try:
                    # We want to be responsive, so a short timeout is fine.
                    # The connection stays alive via keep-alives if needed,
                    # but here we just rely on the client's browser behavior.
                    data = q.get(timeout=15)
                    yield f"data: {json.dumps({'msg': data})}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            state.unsubscribe_serial(q)

    return Response(
        stream_with_context(gen()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@bp.route('/serial/send', methods=['POST'])
def serial_send():
    """Accepts a command string and sends it over the serial link."""
    cmd = (request.json or {}).get('cmd')
    if not cmd:
        return jsonify(status='error', message='No command provided'), 400
    send_raw(cmd)
    return jsonify(status='success')


@bp.route('/update_playlist', methods=['POST'])
def update_playlist():
    data = request.json or {}
    state.current_playlist = data.get('pages', [])
    state.loop_delay = data.get('delay', 5)
    state.last_sent_page = None
    state.set_active_app(None)
    state.request_stop()
    return jsonify(status='success')


@bp.route('/run_app', methods=['POST'])
def run_app():
    state.set_active_app((request.json or {}).get('app'))
    state.request_stop()
    return jsonify(status=f"App {state.active_app} started")


@bp.route('/stop_app', methods=['POST'])
def stop_app():
    state.set_active_app(None)
    state.request_stop()
    return jsonify(status='stopped')


@bp.route('/home_all')
def home_all():
    send_raw('m*h')
    state.set_display(' ' * NUM_MODULES, [0] * NUM_MODULES)
    return jsonify(status='Homing All')
