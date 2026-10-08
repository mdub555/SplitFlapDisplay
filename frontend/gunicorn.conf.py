"""Gunicorn settings for serving the app in production:

    gunicorn app:app

(run from frontend/; gunicorn reads this file from the folder it starts in).
`python app.py` still works for development. Read the notes before changing
anything here: the app has a few needs most Flask apps don't.
"""
import os

# Exactly ONE worker process. The serial port, what's on the display and
# the background threads (the playlist player, the scheduler and the serial
# watchdog) all live inside the app's process. A second worker would try to
# open the port again, run its own playlist loop, and keep its own idea of
# what the display shows. So: one process, with threads for concurrency.
workers = 1
worker_class = 'gthread'

# Every open browser tab holds two live streams (the display state and the
# serial log), each keeping a thread busy for as long as the tab is open, so
# leave plenty of threads for everything else.
threads = 16

bind = f"0.0.0.0:{os.environ.get('SPLITFLAP_PORT', '80')}"

# Not preload_app: the app starts its background threads when it's loaded,
# and threads started in gunicorn's main process don't carry over into the
# worker it then starts.
preload_app = False

# No max_requests: restarting the worker every so often would reset what's
# playing, the sync status and the serial connection.
max_requests = 0

# Some requests take a while (Sync All up to ~12 s, Measure Reel up to 45 s).
timeout = 120

# The live streams never finish on their own, so on shutdown or restart
# don't wait the default 30 s for them: the pages reconnect by themselves.
graceful_timeout = 5

# Logs to the console (docker logs, or the terminal).
accesslog = '-'
errorlog = '-'
loglevel = 'info'
