# Split-Flap OS

Flask backend + vanilla-JS frontend for controlling an RS-485 split-flap
display. Refactored from a single-file app.py / index.html into modular
pieces:

```
config.py              Grid size (GRID_ROWS/GRID_COLS), serial port, settings path
display/                Serial transport, layout math, shared DisplayState, playlist loop
apps/                   One file per app, all implementing the same App interface
settings/               Global settings schema, load/save, backup/restore
routes/                 Flask blueprints, one per concern (routes/pages.py serves the page)
templates/index.html    Markup, with Jinja macros for the repeated blocks
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
grid rendering) derives from those two numbers. Defaults are 4x16, which is
also the largest size supported (1-4 rows, 1-16 columns).

If `SPLITFLAP_SERIAL_PORT` can't be opened, the app logs a warning and runs
in simulation mode — the UI works, but nothing physically moves. `/config`
reports `hardware_connected` if you want to surface that in a future UI
tweak.

The page gets everything the backend already knows (grid size, character
set, animation styles, the firmware settings and module toggles with their
labels) when it's rendered, as `CONFIG` (see `routes/pages.py`), so the
frontend never keeps its own copy of those tables.

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

Read a setting with `self.setting(settings, key)`, which falls back to the
field's default. `apps/builtin/_shared.py` has helpers for the common parts
(`center_page`, `row_frames`, `clock`, `split_list`). A colour animation can
subclass `AnimationApp` (`apps/builtin/animations/base.py`) and only
implement `frames()`; the update-order and speed settings are built for it.

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
swallows a failed request.

## Live state: Server-Sent Events, not polling

The flap grid, homing overlay, and active-app banner used to refresh via
`setInterval(..., 1000)` hitting `GET /current_state` once a second, whether
or not anything had actually changed. That's gone — `static/js/live-flap.js`
now opens one `EventSource('/current_state/stream')` connection instead, and
`display/state.py`'s `DisplayState` doubles as the broadcast hub: every
`set_display()`, `mark_module_char()`, or `set_active_app()` call pushes a
fresh snapshot to every subscribed client immediately, so updates land as
soon as they happen instead of up to a second late, and there's no request
firing at all while the display is idle.

A few things that come with that:

- **`app.run(..., threaded=True)`** in `app.py` is required, not optional.
  Each open SSE connection holds its request thread for as long as a browser
  tab stays on the page; a single-worker dev server would serve exactly one
  client and every other request — including a second tab's initial page
  load — would hang behind it. A production WSGI server needs the same
  consideration: enough sync workers/threads to cover concurrent SSE
  clients, or an async worker class (gevent/eventlet) that isn't limited by
  thread count.
- **`GET /current_state`** (the old polling endpoint) still exists as a
  one-off snapshot — handy for a quick `curl` check — it's just not what the
  live UI uses anymore.
- **Reconnection is mostly free**: `EventSource` retries automatically on
  its own per spec. `#streamStatus` (a small banner, see `base.css`) shows
  up on `onerror` and clears on `onopen` so a dropped connection is visibly
  different from "genuinely nothing is happening," instead of failing silently.
- The stream sends a `: keep-alive` comment every 15s while idle so proxies
  and browsers don't time out or reap the connection.

## Testing

`tests/` contains a headless DOM test (via jsdom) that loads the page as
Flask renders it and the `static/js/*.js` files it lists — the same way a
browser would — with `fetch` **and `EventSource`** mocked, then exercises the actual
click/change event pipeline: tab switching, running an app, opening/saving
app settings, playlist add/edit/delete, the live SSE stream driving the flap
grid and banners, a malformed-payload guard, the reconnect status banner,
and several failure-path checks (a dropped network request, a simulated
HTTP 500, optimistic UI reverting correctly).

```
cd tests
npm install
npm test
```



- **Charset**: `display/charset.py`'s `FLAP_CHARS` must match
  `firmware/splitflapfirmwarev8/splitflap.cpp`'s `FLAP_CHARS` exactly (same
  characters, same order); change both together. The page gets it from the
  backend. Characters with no flap (e.g. `;` and `'`) are sent as a
  blank. On the v8 reels `d` and `h` are the degree sign and heart, which the
  compose UI accepts as `°` and `♥`.
- Per-character EEPROM fine-tuning (`w<idx>:<pos>`, the old Auto Fine-Tune
  wizard) has been removed from both the backend and frontend per the
  "modules don't need fine tuning" decision — only home offset and total
  steps/revolution remain configurable. If any modules DO need per-character
  correction later, that functionality no longer exists and would need to be
  rebuilt.
- Backend tests: run `python -m unittest discover -s tests` from `frontend/`
  (the route tests need Flask). They cover the dump parser and protocol
  (checked against the firmware source), the module, settings, playlist and
  firmware routes, backup restore, the page and its configuration, the
  animation orders, the SSE subscriber queues and the app base classes. The
  route tests load each route file with the settings store and serial link
  faked, so nothing touches a serial port or settings.json.
