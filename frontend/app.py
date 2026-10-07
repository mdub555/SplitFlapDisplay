import logging
import threading

from flask import Flask, render_template

from routes import (
    apps_routes, backup_routes, control, firmware_routes, module_routes, playlist_routes,
    settings_routes,
)
from display.module_protocol import BROADCAST, Cmd, message
from display.player import playlist_loop

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

app = Flask(__name__)
for routes in (control, settings_routes, apps_routes, module_routes, backup_routes,
               playlist_routes, firmware_routes):
    app.register_blueprint(routes.bp)


# The serial debug panel's quick commands: (message, label).
DEBUG_COMMANDS = [
    (message(BROADCAST, Cmd.HOME), 'Home All'),
    (message(1, Cmd.DUMP_STATE), 'Dump Mod 01'),
    (message(1, Cmd.CALIBRATE), 'Calib Mod 01'),
]


@app.route('/')
def index():
    return render_template('index.html', debug_commands=DEBUG_COMMANDS)


threading.Thread(target=playlist_loop, daemon=True).start()

if __name__ == '__main__':
    logging.info('Web UI running on 0.0.0.0:80')
    # threaded=True is required, not optional: each open SSE connection
    # (see /current_state/stream) holds its request thread open for as long
    # as a browser tab stays on the page. Without this, the single-worker
    # dev server would serve exactly one client and every other request —
    # including the initial page load for a second tab — would hang behind it.
    app.run(host='0.0.0.0', port=80, threaded=True)
