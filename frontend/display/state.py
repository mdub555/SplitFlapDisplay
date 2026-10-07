import queue
import threading

from config import NUM_MODULES


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
