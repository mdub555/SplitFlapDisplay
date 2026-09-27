import queue
import threading

from config import NUM_MODULES


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

        self.last_sent_page = None

        # Cooperative-cancellation flag: routes set this after changing
        # active_app/current_playlist so the playlist loop abandons whatever
        # wait it's currently in and re-reads state on its next iteration,
        # rather than finishing the current page's full delay first.
        self.stop_event = threading.Event()

        # SSE subscribers for state updates. Each is a Queue(maxsize=1) holding only the latest
        # snapshot — a client that hasn't drained the previous update yet
        # gets it overwritten rather than queued, since nobody needs a
        # backlog of intermediate flap states, only the most current one.
        # Kept as a set (not a list) so unsubscribe on disconnect is O(1).
        self._subscribers = set()
        self._subscribers_lock = threading.Lock()

        # SSE subscribers for serial logs. Each is a Queue holding log entries.
        # Unlike state updates, we want to deliver every log entry.
        self._serial_subscribers = set()
        self._serial_subscribers_lock = threading.Lock()

    def request_stop(self):
        self.stop_event.set()

    def clear_stop(self):
        self.stop_event.clear()

    def snapshot(self):
        """Read-only dict shared by the plain GET /current_state endpoint
        and every value pushed over the SSE stream."""
        with self.lock:
            return {
                'is_homed': self.is_homed,
                'state': self.current_display_string,
                'active_app': self.active_app,
            }

    def set_active_app(self, app_key):
        with self.lock:
            self.active_app = app_key
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
        """Register a new SSE client. Returns a Queue that receives a fresh
        snapshot every time the display state changes. The caller (the
        stream route's generator) must call unsubscribe() with the same
        queue once the client disconnects, or this subscriber leaks."""
        q = queue.Queue(maxsize=1)
        q.put_nowait(self.snapshot())  # so a new client draws immediately, not on the next change
        with self._subscribers_lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q):
        with self._subscribers_lock:
            self._subscribers.discard(q)

    def _broadcast(self):
        data = self.snapshot()
        with self._subscribers_lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(data)
            except queue.Full:
                # Slow/stalled client — drop its stale pending update in
                # favor of this newer one rather than blocking the thread
                # that's publishing (often the playlist loop itself).
                try:
                    q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    q.put_nowait(data)
                except queue.Full:
                    pass

    def subscribe_serial(self):
        """Register a new SSE client for serial logs. Returns a Queue that
        receives every log entry. The caller must call unsubscribe_serial()
        once the client disconnects."""
        q = queue.Queue()
        with self._serial_subscribers_lock:
            self._serial_subscribers.add(q)
        return q

    def unsubscribe_serial(self, q):
        with self._serial_subscribers_lock:
            self._serial_subscribers.discard(q)

    def _broadcast_serial(self, msg):
        """Broadcast a single serial log message to all subscribers."""
        with self._serial_subscribers_lock:
            subs = list(self._serial_subscribers)
        for q in subs:
            q.put(msg)


# Single shared instance — imported by player.py and every route module.
state = DisplayState()
