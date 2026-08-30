import threading

from config import NUM_MODULES


class DisplayState:
    """Central, lock-aware home for everything the playlist loop and the
    Flask routes both need to read or write. Replaces the ~10 loose
    module-level globals (current_indices, active_app, stop_event, ...)
    that used to live directly in app.py."""

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

    def request_stop(self):
        self.stop_event.set()

    def clear_stop(self):
        self.stop_event.clear()

    def snapshot(self):
        """Read-only dict for the /current_state polling endpoint."""
        with self.lock:
            return {
                'is_homed': self.is_homed,
                'state': self.current_display_string,
                'active_app': self.active_app,
            }

    def mark_module_char(self, module_id, char):
        """Optimistically update one module's displayed char in local state
        (used right after firing a single-module command, ahead of the next
        full frame render)."""
        with self.lock:
            sl = list(self.current_display_string.ljust(NUM_MODULES))
            if 0 <= module_id < NUM_MODULES:
                sl[module_id] = char
            self.current_display_string = ''.join(sl)

    def set_display(self, text, indices):
        with self.lock:
            self.current_display_string = text
            self.current_indices = indices
            self.is_homed = True


# Single shared instance — imported by player.py and every route module.
state = DisplayState()
