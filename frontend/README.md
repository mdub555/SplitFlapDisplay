# Split-Flap OS

Flask backend + vanilla-JS frontend for controlling an RS-485 split-flap
display. Refactored from a single-file app.py / index.html into modular
pieces:

```
config.py              Grid size (GRID_ROWS/GRID_COLS), serial port, settings path
display/                Serial transport, layout math, shared DisplayState, playlist loop
apps/                   One file per app, all implementing the same App interface
settings/               Global settings schema, load/save, backup/restore
routes/                 Flask blueprints, one per concern
templates/index.html    Markup only
static/css/*.css        Styles, split by page/concern
static/js/*.js          Frontend logic, split by page/concern
```

## Running

```
pip install -r requirements.txt
python app.py
```

Set `SPLITFLAP_ROWS` / `SPLITFLAP_COLS` env vars (or edit `config.py`) to
match your hardware — everything (module count, animation layout, frontend
grid rendering) derives from those two numbers. Defaults are 4x16.

If `SPLITFLAP_SERIAL_PORT` can't be opened, the app logs a warning and runs
in simulation mode — the UI works, but nothing physically moves. `/config`
reports `hardware_connected` if you want to surface that in a future UI
tweak.

## Adding a new app

1. Create `apps/builtin/your_app.py`:

```python
from apps.base import App, Frame, SettingField

class YourApp(App):
    key = 'your_app'
    name = 'Your App'
    icon = '🔥'
    desc = 'One-line description'
    settings_fields = [
        SettingField('your_app_thing', 'Some Setting', default='foo'),
    ]

    def get_pages(self, settings, cache):
        return [Frame(text='HELLO', delay=5)]
```

2. Register it in `apps/registry.py` (import the class, add it to the list).

That's it — it'll appear in the Apps tab, its settings_fields render
automatically in its ⚙️ settings modal, and the playlist loop runs it
through the exact same Frame-based path as every other app. No changes
needed anywhere else.

`get_pages()` is called repeatedly by the playlist loop each time it needs
more content; apps that hit the network should use the `cache` dict (persists
for as long as the app stays active) with `apps.builtin._shared.cache_get_or_fetch`
to avoid re-fetching every call.

## Known follow-ups (not yet done)

- **Firmware charset mismatch**: `display/charset.py`'s `FLAP_CHARS` matches
  the v7 firmware's character order but NOT `firmware/splitflapfirmwarev8/splitflap.cpp`'s
  `FLAP_CHARS`, which uses a different order. If v8 is what's deployed,
  index-based commands will show the wrong character until one side is
  updated to match the other.
- Per-character EEPROM fine-tuning (`w<idx>:<pos>`, the old Auto Fine-Tune
  wizard) has been removed from both the backend and frontend per the
  "modules don't need fine tuning" decision — only home offset and total
  steps/revolution remain configurable. If any modules DO need per-character
  correction later, that functionality no longer exists and would need to be
  rebuilt.
- No automated tests. Given the hardware dependency this would mean mocking
  `display/serial_link.py`; the module boundary is drawn to make that
  straightforward, but nothing calls it yet.
