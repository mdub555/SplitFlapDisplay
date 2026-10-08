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
    batch of frames."""

    key: str = ''
    name: str = ''
    icon: str = ''
    desc: str = ''
    settings_fields: list = []   # list[SettingField], app-scoped fields only

    def setting(self, settings: dict, key: str):
        """settings[key], falling back to the default of this app's field
        for it."""
        default = next(f.default for f in self.settings_fields if f.key == key)
        return settings.get(key, default)

    def get_pages(self, settings: dict, cache: dict) -> list:
        """Return a list of Frame objects representing everything this app
        wants displayed right now. Called repeatedly by the playlist loop;
        apps that fetch from the network should time-box their fetches using
        `cache` (a plain dict that persists across calls for as long as this
        app stays active) rather than hitting the network every call."""
        raise NotImplementedError
