from dataclasses import dataclass, field


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
    type: str = 'text'          # text | password | number | select | textarea | datetime-local
    scope: str = 'app'
    default: str = ''
    opts: list = field(default_factory=list)
    placeholder: str = ''
    min: str = None
    max: str = None
    step: str = None


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

    def get_pages(self, settings: dict, cache: dict) -> list:
        """Return a list of Frame objects representing everything this app
        wants displayed right now. Called repeatedly by the playlist loop;
        apps that fetch from the network should time-box their fetches using
        `cache` (a plain dict that persists across calls for as long as this
        app stays active) rather than hitting the network every call."""
        raise NotImplementedError
