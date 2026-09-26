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

## Frontend architecture notes

Inline `onclick="..."` / `onchange="..."` attributes were removed in favor of
a small delegated-event system (`static/js/actions.js`): elements declare
*what* to do via `data-onclick="actionName"` (reading any parameters off
`data-*` attributes) instead of embedding JS directly in HTML. Each page's
JS file calls `registerActions({...})` once to wire its handlers into the
shared dispatcher. This means:

- Dynamically-rendered rows (playlist items, saved playlists, app cards)
  never string-interpolate values into HTML attribute strings — values pass
  through `el.dataset` instead, which is safe regardless of what characters
  they contain (playlist names, for instance, no longer need manual
  `encodeURIComponent`/`decodeURIComponent` round-tripping).
- There's one listener per event type for the whole page, not one per
  button — re-rendering a list via `innerHTML = ''` never leaves stale
  listeners behind or needs them rewired.

Rendering that echoes user-supplied text (playlist names, flap content) uses
`textContent`/`createElement` rather than `innerHTML` string-building, so it
can't be reinterpreted as markup no matter what's typed in.

Every `api.*` call (`static/js/api.js`) resolves to `null` on failure — network
error or non-2xx response — after logging details to the console and showing
a toast (using the backend's error message when one is provided). Callers
only need `if (!result) return;`; nothing needs its own try/catch or silently
swallows a failed request. The one exception is `api.currentState()`, which
passes a `null` error message to suppress toast spam on its once-per-second
poll — failures there are logged but not surfaced as a popup.

## Testing

`tests/` contains a headless DOM test (via jsdom) that loads the real
`templates/index.html` and `static/js/*.js` files — the same way a browser
would — with `fetch` mocked, then exercises the actual click/change event
pipeline: tab switching, running an app, opening/saving app settings,
playlist add/edit/delete, and several failure-path checks (a dropped
network request, a simulated HTTP 500, optimistic UI reverting correctly).

```
cd tests
npm install
npm test
```



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
- No backend automated tests yet (a frontend suite now exists — see
  Testing above). The backend hardware dependency would mean mocking
  `display/serial_link.py`; the module boundary is drawn to make that
  straightforward, but nothing calls it yet.
