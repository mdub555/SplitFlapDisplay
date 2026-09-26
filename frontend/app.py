import logging
import threading

from flask import Flask, render_template

from routes import BLUEPRINTS
from display.player import playlist_loop

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

app = Flask(__name__)
for bp in BLUEPRINTS:
    app.register_blueprint(bp)


@app.route('/')
def index():
    return render_template('index.html')


threading.Thread(target=playlist_loop, daemon=True).start()

if __name__ == '__main__':
    logging.info('Web UI running on 0.0.0.0:80')
    # threaded=True is required, not optional: each open SSE connection
    # (see /current_state/stream) holds its request thread open for as long
    # as a browser tab stays on the page. Without this, the single-worker
    # dev server would serve exactly one client and every other request —
    # including the initial page load for a second tab — would hang behind it.
    app.run(host='0.0.0.0', port=80, threaded=True)
