"""Helpers shared by the route modules. Kept free of settings and serial
imports so the route tests can load any route file with those faked."""
import json
import queue

from flask import Response, jsonify, request, stream_with_context


def json_body():
    """The request's JSON body, or {} if it has none."""
    return request.json or {}


def error(message, status):
    """The standard error response: {"status": "error", "message": ...}."""
    return jsonify(status='error', message=message), status


def is_int(value):
    """True for a real integer. bool is a subclass of int, so true/false must
    not pass as 1/0."""
    return isinstance(value, int) and not isinstance(value, bool)


def sse_response(subscribe, unsubscribe, to_payload=lambda item: item):
    """A Server-Sent Events stream of whatever arrives on the queue that
    `subscribe()` returns, each passed through `to_payload` and sent as JSON.
    A heartbeat comment goes out every 15 s so idle proxies and browsers
    don't treat the connection as dead.

    Requires the Flask dev server to run with threaded=True (see app.py):
    each open stream holds its thread for as long as the browser tab stays
    on the page, so a single-worker server would serve exactly one client
    before every other request starts blocking behind it. The same applies
    to a production WSGI server: it needs enough threads or workers to cover
    the open streams."""
    def gen():
        q = subscribe()
        try:
            while True:
                try:
                    yield f"data: {json.dumps(to_payload(q.get(timeout=15)))}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            unsubscribe(q)

    return Response(
        stream_with_context(gen()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )
