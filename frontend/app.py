import logging
import threading

# Before anything else is imported: importing the serial link logs (an error,
# when the port won't open), and the first log call sets logging up with
# Python's defaults, after which this would do nothing and every info
# message would be lost.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

from flask import Flask

from config import PORT
from routes import (
    apps_routes, backup_routes, control, firmware_routes, module_routes, pages, playlist_routes,
    schedule_routes, settings_routes,
)
from display.player import playlist_loop
from display.scheduler import get_scheduler
from display.serial_link import keep_connected


app = Flask(__name__)
for routes in (pages, control, settings_routes, apps_routes, module_routes, backup_routes,
               playlist_routes, firmware_routes, schedule_routes):
    app.register_blueprint(routes.bp)


threading.Thread(target=playlist_loop, daemon=True).start()
threading.Thread(target=get_scheduler().run_forever, daemon=True).start()
# Reopens the serial port if it goes (an unplugged USB adapter) or wasn't there at startup.
threading.Thread(target=keep_connected, daemon=True).start()

if __name__ == '__main__':
    logging.info(f'Web UI running on 0.0.0.0:{PORT}')
    # threaded=True is required, not optional: each open SSE connection
    # (see /current_state/stream) holds its request thread open for as long
    # as a browser tab stays on the page. Without this, the single-worker
    # dev server would serve exactly one client and every other request —
    # including the initial page load for a second tab — would hang behind it.
    app.run(host='0.0.0.0', port=PORT, threaded=True)
