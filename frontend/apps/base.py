import textwrap
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class SettingField:
    """One configurable field. `scope='app'` fields render in that app's
    per-app ⚙️ settings modal; `scope='global'` fields (only used from
    settings/schema.py) render once in the Global Settings tab and are
    shared by whichever apps need them (e.g. timezone, YouTube API key) —
    this is what keeps the same value from being edited in five different
    places."""
    key: str
    label: str
    type: str = 'text'          # text | password | number | checkbox | select | textarea | datetime-local
    scope: str = 'app'
    default: str = ''
    opts: list = field(default_factory=list)
    placeholder: str = ''
    min: Optional[str] = None   # number fields only
    max: Optional[str] = None
    step: Optional[str] = None

    def to_json(self) -> dict:
        """What the frontend needs to render the field (scope is only used
        server-side)."""
        data = asdict(self)
        del data['scope']
        return data

    def clean(self, value):
        """`value` (as the page sent it) as this field's type: a number for a
        number field, True/False for a checkbox, one of `opts` for a select,
        otherwise a string. Raises ValueError, naming the field, if it isn't
        one. A blank number goes back to the default."""
        if self.type == 'number':
            if value is None or (isinstance(value, str) and not value.strip()):
                value = self.default
            if isinstance(value, bool):
                raise ValueError(f'{self.label} must be a number')
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError(f'{self.label} must be a number') from None
            if number != number or number in (float('inf'), float('-inf')):
                raise ValueError(f'{self.label} must be a number')
            if self.min is not None and number < float(self.min):
                raise ValueError(f'{self.label} must be at least {self.min}')
            if self.max is not None and number > float(self.max):
                raise ValueError(f'{self.label} must be at most {self.max}')
            return int(number) if number.is_integer() else number
        if self.type == 'checkbox':
            if isinstance(value, bool):
                return value
            if value in ('true', 'false'):
                return value == 'true'
            raise ValueError(f'{self.label} must be on or off')
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise ValueError(f'{self.label} must be text')
        value = str(value)
        if self.type == 'select' and self.opts and value not in self.opts:
            # A short list is worth spelling out; a long one (timezones) isn't.
            if len(self.opts) <= 10:
                raise ValueError(f'{self.label} must be one of: {", ".join(self.opts)}')
            raise ValueError(f'{self.label}: "{value}" isn\'t one of the choices')
        return value


def clean_settings(fields, data):
    """The values in `data` for `fields` (other keys are dropped), each
    cleaned by its field. Raises ValueError for the first that's wrong."""
    return {f.key: f.clean(data[f.key]) for f in fields if f.key in data}


@dataclass(frozen=True)
class Grid:
    """The display's size, which every app is given rather than assuming
    one: 4x16 and 3x15 displays both exist. Builds pages to fit it."""
    rows: int
    cols: int

    @property
    def size(self):
        """The number of modules: the length of every page."""
        return self.rows * self.cols

    def page(self, *rows):
        """A page of up to `rows` lines of text, each centred across the
        display, the lines centred top to bottom. Lines past the last row are
        dropped and text past the last column is cut off."""
        rows = list(rows)[:self.rows]
        top = (self.rows - len(rows)) // 2
        rows = [''] * top + rows + [''] * (self.rows - len(rows) - top)
        return ''.join(str(r).center(self.cols)[:self.cols] for r in rows)

    def banner(self, text, fill='='):
        """`text` centred across a row as page() centres it, with `fill`
        running out to both edges (a space either side of the text), to
        mark it as a heading: '== ETIQUETTE ==='. Text too wide for that
        is left as it is."""
        text = str(text)
        if len(text) + 4 > self.cols:
            return text
        left = len(text.center(self.cols)) - len(text.center(self.cols).lstrip())
        right = self.cols - left - len(text)
        return f"{fill * (left - 1)} {text} {fill * (right - 1)}"

    def cells(self, char_at):
        """A page with `char_at(row, col)` in each module, for patterns."""
        return ''.join(char_at(r, c) for r in range(self.rows) for c in range(self.cols))

    def wrap(self, text, max_lines=None):
        """`text` split into lines that fit across the display, breaking
        between words where it can, at most `max_lines` of them (all the
        display's rows by default)."""
        lines = textwrap.wrap(str(text), self.cols) or ['']
        return lines[:self.rows if max_lines is None else max_lines]

    def chunks(self, items, per_page=None):
        """`items` split into groups of `per_page`, by default one per row."""
        n = max(1, per_page or self.rows)
        return [items[i:i + n] for i in range(0, len(items), n)]


@dataclass
class Frame:
    """One page of content to show on the display."""
    text: str
    delay: float = None     # seconds to hold; None lets the caller pick a default
    style: str = 'ltr'      # animation order name, see display.layout.get_animation_order
    speed: int = 15         # ms delay between individual module sends
    raw: bool = False       # True = skip uppercasing/color-mapping (animation frames)


class App:
    """Every app — data-driven (weather, stocks) or self-driven (demo,
    matrix cascade) — implements this same interface. The playlist loop
    doesn't know or care which kind it's running; it just asks for the next
    batch of frames.

    A subclass with a `key` anywhere under apps/builtin/ is found and
    registered on its own (see apps/registry.py); one without a key (like
    AnimationApp) is a base for other apps and isn't."""

    key: str = ''
    name: str = ''
    icon: str = ''
    desc: str = ''
    order: int = 1000            # place in the Apps grid, lowest first; ties go by name
    enabled: bool = True         # False leaves it out of the registry
    settings_fields: list = []   # list[SettingField], app-scoped fields only
    # Keys of the Global Settings fields (settings/schema.py) that must be
    # filled in for this app to work, like an API key, so its settings modal
    # can say where to set them. (Not the timezone: it always has a value.)
    global_settings: list = []
    # An apps.oauth.OAuthProvider, for an app that signs in to a service
    # (Spotify): its settings modal gets a Connect button, and get_pages()
    # gets a token from self.access_token(settings).
    oauth = None

    def setting(self, settings: dict, key: str):
        """settings[key], falling back to the default of the field for it:
        one of this app's fields, or one of the global fields it uses."""
        from settings.schema import GLOBAL_FIELDS   # deferred: it imports this module
        for f in [*self.settings_fields, *GLOBAL_FIELDS]:
            if f.key == key:
                return settings.get(key, f.default)
        raise KeyError(f"{type(self).__name__} has no setting {key!r}; add a SettingField for it")

    def access_token(self, settings: dict):
        """A current OAuth access token for the app's service, or None if it
        isn't connected (see apps/oauth.py)."""
        from apps import oauth   # deferred: it reads config, which base needn't
        return oauth.access_token(self, settings)

    def get_items(self, settings: dict, cache: dict, grid: Grid) -> list:
        """The app's content as separate items, each a list of Frames: one
        historical event, one game's score. In a playlist, each time round
        the app shows its next item rather than everything. An app whose
        content doesn't split up (a clock) leaves this as it is: all of
        get_pages() as one item. An app implements one or the other."""
        return [self.get_pages(settings, cache, grid)]

    def get_pages(self, settings: dict, cache: dict, grid: Grid) -> list:
        """Return a list of Frame objects representing everything this app
        wants displayed right now, each page fitting `grid` (the display's
        size: build pages with grid.page() rather than assuming one). Called repeatedly by the playlist loop;
        apps that fetch from the network should time-box their fetches using
        `cache` (a plain dict that persists across calls; it's this app's
        own, and emptied when settings are saved) rather than hitting
        the network every call.

        If it raises, the player logs the error and shows an error page for
        a while before trying again, so an app needn't catch everything
        itself; catching an error is only worth it to say something more
        useful on the display.

        An app that implements get_items() instead gets this for free: all
        its items, one after another."""
        if type(self).get_items is App.get_items:
            raise NotImplementedError(f'{type(self).__name__} implements neither get_pages() nor get_items()')
        return [frame for item in self.get_items(settings, cache, grid) for frame in item]
