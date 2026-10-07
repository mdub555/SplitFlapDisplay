import queue
import threading

from config import NUM_MODULES


def _seconds(value, default):
    """`value` as a positive number of seconds, or `default`. The page sends
    the delay as typed, so it can be a string, blank or nonsense."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return default
    return seconds if seconds > 0 else default


class _Subscribers:
    """The queues of every open SSE stream for one kind of message.

    With `latest_only`, each queue holds just the newest message: a client
    that hasn't drained the previous one gets it replaced rather than a
    backlog, since only the current state matters. Otherwise every message
    is queued for every subscriber."""

    def __init__(self, latest_only):
        self._latest_only = latest_only
        self._queues = set()   # a set, so unsubscribing on disconnect is O(1)
        self._lock = threading.Lock()

    def subscribe(self, first=None):
        """A new queue for one client, starting with `first` if given. The
        caller must unsubscribe() it once the client disconnects, or it leaks."""
        q = queue.Queue(maxsize=1 if self._latest_only else 0)
        if first is not None:
            q.put_nowait(first)
        with self._lock:
            self._queues.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._queues.discard(q)

    def publish(self, item):
        with self._lock:
            queues = list(self._queues)
        for q in queues:
            if not self._latest_only:
                q.put(item)
                continue
            # Never block the publisher (often the playlist loop): drop a
            # stalled client's stale message in favour of this one.
            try:
                q.get_nowait()
            except queue.Empty:
                pass
            try:
                q.put_nowait(item)
            except queue.Full:
                pass


class DisplayState:
    """Central, lock-aware home for everything the playlist loop and the
    Flask routes both need to read or write. Replaces the ~10 loose
    module-level globals (current_indices, active_app, stop_event, ...)
    that used to live directly in app.py.

    Also doubles as the SSE broadcast hub: any change made through
    set_display(), mark_module_char(), or set_active_app() pushes a fresh
    snapshot to every subscribed client (see subscribe()/unsubscribe()),
    which is what /current_state/stream in routes/control.py streams out.
    """

    def __init__(self):
        self.lock = threading.Lock()

        self.current_indices = [-1] * NUM_MODULES
        self.current_display_string = ' ' * NUM_MODULES
        self.is_homed = False

        self.active_app = None       # key into the app registry, or None
        self.current_playlist = []   # manual pages when active_app is None
        self.loop_delay = 5          # default seconds/page for the manual playlist
        self.playlist_name = None    # the saved playlist being played, if it is one
        self.playlist_page = 0       # index of the playlist page on the display

        # Whether the serial port opened (display/serial_link.py sets it). When
        # it didn't, nothing physically moves and the page says so.
        self.hardware_connected = False

        # What the scheduler (display/scheduler.py) last started, as a target
        # string ('app:<key>' or 'playlist:<name>'), so the page can say a
        # running thing is scheduled. Set by the scheduler only.
        self.scheduled_target = None

        # Goes up by one every time settings.json is saved (settings/store.py),
        # so every open page hears that the settings changed, whoever changed
        # them, and can reload what it shows.
        self.settings_version = 0

        # Syncing modules (reading back their settings), for the Modules page:
        # whether a Sync All is under way, each module's latest success (by
        # a number that goes up with every one, so the page can flash the
        # module each time), and the modules whose last sync failed, until
        # they next sync.
        self.sync_running = False
        self.sync_count = 0
        self.sync_ok = {}        # module id -> sync_count at its latest success
        self.sync_failed = set()

        self.last_sent_page = None

        # Cooperative-cancellation flag: routes set this after changing
        # active_app/current_playlist so the playlist loop abandons whatever
        # wait it's currently in and re-reads state on its next iteration,
        # rather than finishing the current page's full delay first.
        self.stop_event = threading.Event()

        self._state_subscribers = _Subscribers(latest_only=True)
        self._serial_subscribers = _Subscribers(latest_only=False)

    def request_stop(self):
        self.stop_event.set()

    def clear_stop(self):
        self.stop_event.clear()

    def snapshot(self):
        """Read-only dict shared by the plain GET /current_state endpoint
        and every value pushed over the SSE stream."""
        with self.lock:
            playing = None
            if self.active_app is None and self.current_playlist:
                playing = {
                    'name': self.playlist_name,
                    'page': self.playlist_page,
                    'pages': len(self.current_playlist),
                }
            target = self._current_target()
            return {
                'is_homed': self.is_homed,
                'state': self.current_display_string,
                'active_app': self.active_app,
                'playlist': playing,
                'scheduled': target is not None and target == self.scheduled_target,
                'hardware_connected': self.hardware_connected,
                'settings_version': self.settings_version,
                'sync': {
                    'running': self.sync_running,
                    'ok': {str(i): n for i, n in self.sync_ok.items()},
                    'failed': sorted(self.sync_failed),
                },
            }

    def _current_target(self):
        """What's running as a scheduler target string, or None for nothing
        (or an unsaved playlist). Call with the lock held."""
        if self.active_app:
            return f'app:{self.active_app}'
        if self.current_playlist and self.playlist_name:
            return f'playlist:{self.playlist_name}'
        return None

    def current_target(self):
        with self.lock:
            return self._current_target()

    def set_active_app(self, app_key):
        with self.lock:
            self.active_app = app_key
        self._broadcast()

    # --- What runs: an app, a playlist, or nothing ----------------------
    #
    # Each of these makes the playlist loop (display/player.py) drop what
    # it's doing and pick up the new state straight away.

    def run_app(self, app_key):
        with self.lock:
            self.active_app = app_key
            self.current_playlist = []
            self.playlist_name = None
        self.request_stop()
        self._broadcast()

    def run_playlist(self, pages, delay=5, name=None):
        """Play `pages` in a loop, `delay` seconds each unless a page sets
        its own. `name` is the saved playlist they came from, if any."""
        with self.lock:
            self.active_app = None
            self.current_playlist = list(pages or [])
            self.loop_delay = _seconds(delay, 5)
            self.playlist_name = name
            self.playlist_page = 0
            self.last_sent_page = None
        self.request_stop()
        self._broadcast()

    def stop(self):
        """Stop whatever's running; the display keeps its last page."""
        with self.lock:
            self.active_app = None
            self.current_playlist = []
            self.playlist_name = None
        self.request_stop()
        self._broadcast()

    def set_playlist_page(self, index):
        with self.lock:
            if self.playlist_page == index:
                return
            self.playlist_page = index
        self._broadcast()

    def start_sync(self):
        with self.lock:
            self.sync_running = True
        self._broadcast()

    def sync_result(self, mod_id, ok):
        """Module `mod_id` answered a sync (`ok`) or didn't."""
        with self.lock:
            if ok:
                self.sync_count += 1
                self.sync_ok[mod_id] = self.sync_count
                self.sync_failed.discard(mod_id)
            else:
                self.sync_failed.add(mod_id)
        self._broadcast()

    def finish_sync(self):
        with self.lock:
            self.sync_running = False
        self._broadcast()

    def settings_changed(self):
        with self.lock:
            self.settings_version += 1
        self._broadcast()

    def set_scheduled_target(self, target):
        with self.lock:
            self.scheduled_target = target
        self._broadcast()

    def mark_module_char(self, module_id, char):
        """Optimistically update one module's displayed char in local state
        (used right after firing a single-module command, ahead of the next
        full frame render)."""
        with self.lock:
            sl = list(self.current_display_string.ljust(NUM_MODULES))
            if 0 <= module_id < NUM_MODULES:
                sl[module_id] = char
            self.current_display_string = ''.join(sl)
        self._broadcast()

    def set_display(self, text, indices):
        with self.lock:
            self.current_display_string = text
            self.current_indices = indices
            self.is_homed = True
        self._broadcast()

    # --- SSE pub/sub ---------------------------------------------------

    def subscribe(self):
        """A queue that receives a fresh snapshot every time the display
        changes, starting with the current one so a new client draws
        immediately. Pass it to unsubscribe() once the client disconnects."""
        return self._state_subscribers.subscribe(self.snapshot())

    def unsubscribe(self, q):
        self._state_subscribers.unsubscribe(q)

    def _broadcast(self):
        self._state_subscribers.publish(self.snapshot())

    def subscribe_serial(self):
        """A queue that receives every serial log message. Pass it to
        unsubscribe_serial() once the client disconnects."""
        return self._serial_subscribers.subscribe()

    def unsubscribe_serial(self, q):
        self._serial_subscribers.unsubscribe(q)

    def log_serial(self, msg):
        """Sends one serial log message to every subscriber."""
        self._serial_subscribers.publish(msg)


# Single shared instance — imported by player.py and every route module.
state = DisplayState()
