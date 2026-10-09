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

That's Flask's development server, which is fine for working on the app
(it warns that it isn't meant for production). To serve it properly, use
gunicorn, which the Docker image does:

```
gunicorn app:app
```

Run it from `frontend/`; it reads `gunicorn.conf.py` from there. That file
keeps the app to **one worker process with threads**: the serial port, the
display state and the background threads live in the app's process, so a
second worker would fight over the port and run its own playlist. Don't
raise `workers`, and don't turn on `preload_app` or `max_requests` (the
file says why). It serves on port 80, or `SPLITFLAP_PORT`.

Set `SPLITFLAP_ROWS` / `SPLITFLAP_COLS` env vars (or edit `config.py`) to
match your hardware — everything (module count, animation layout, frontend
grid rendering) derives from those two numbers. Defaults are 4x16. The UI is
laid out for displays up to 4x16; bigger ones work but may not look as good.

If `SPLITFLAP_SERIAL_PORT` can't be opened, the app logs a warning and runs
in simulation mode — the UI works, but nothing physically moves. The page
says so with a SIMULATION badge next to LIVE DISPLAY (from
`hardware_connected` in the live state; `/config` reports it too).

The port can come and go while the app runs. If the USB adapter is unplugged,
the next write or read fails, or a background check every 5 s notices; the
badge appears, and the app carries on in simulation mode. Once the port is
back it's reopened within 5 s, the badge goes, and the current page is sent
again. (A re-plugged adapter can come back under a new name, ttyUSB1 instead
of ttyUSB0; a `/dev/serial/by-id/...` path for `SPLITFLAP_SERIAL_PORT` stays
the same.) Nothing that goes wrong while playing stops the playlist loop:
errors are logged and it carries on.

The web page is served on port 80, or `SPLITFLAP_PORT`. settings.json is
written atomically (to a temporary file, then moved into place), so a power
cut mid-save can't leave it half-written.

### Docker

`compose.yaml` builds the image and maps `APP_PORT` (from `.env`) to the
container's port 5000. The container keeps settings.json on the
`splitflap-settings` volume (`SPLITFLAP_CONFIG_PATH=/code/data/settings.json`
in the Dockerfile), so rebuilding or updating keeps your calibrations,
playlists and schedule. It serves with gunicorn (see above), not Flask's
development server.

Containers built before this change kept settings.json inside the container
itself, where a rebuild loses it: download a backup (Modules → Backup &
Restore) before updating, and restore it afterwards.

### Deploying to the Pi

Two ways to update the Pi automatically when a PR is merged to `main`
(changes under `frontend/`). They're both set up so you can try each; run
only one at a time, since they share the container name, port 5000 mapping
and `/dev/ttyUSB0`. Both keep the `splitflap-settings` volume, so switching
doesn't lose your settings. Both need a `.env` with `APP_PORT` on the Pi.

**A. Self-hosted runner** (`.github/workflows/deploy-frontend-runner.yml`,
uses `compose.yaml`). The Pi builds the image itself.

1. Repo Settings → Actions → Runners → New self-hosted runner. Choose Linux
   and ARM64 (or ARM for a 32-bit OS) and run the commands it shows on the Pi.
2. Install it as a service: `sudo ./svc.sh install && sudo ./svc.sh start`.
3. Add the runner's user to the docker group: `sudo usermod -aG docker <user>`
   (then restart the service).
4. Keep your `.env` at `~/splitflap/.env` on the Pi, or set the repository
   variable `SPLITFLAP_ENV_FILE` to wherever it lives.

A merge now runs `docker compose up -d --build` on the Pi. The workflow is
only triggered by pushes to `main`, never pull requests, so fork code can't
run on your Pi; still, only use a self-hosted runner on a repo whose
contributors you trust.

**B. Watchtower** (`.github/workflows/publish-frontend-image.yml`, uses
`compose.watchtower.yaml`). GitHub builds the image and the Pi pulls it.

1. Merge once (or run the "Publish frontend image" workflow manually) so the
   image exists at `ghcr.io/mdub555/splitflapdisplay-frontend`.
2. If the package is private (GitHub's default), either make it public
   (Packages → the package → Package settings → Change visibility) or run
   `docker login ghcr.io` on the Pi with a token that has `read:packages` and
   uncomment the `config.json` mount in `compose.watchtower.yaml`.
3. On the Pi, stop any container from option A
   (`docker compose down`), then
   `docker compose -f compose.watchtower.yaml up -d`.

Watchtower checks every 5 minutes (`WATCHTOWER_POLL_INTERVAL`), so a deploy
takes a few minutes after the image is published, and restarts only
containers labelled for it.

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

## Playlists, the schedule and the draft

- **What's playing** is in every live-state snapshot: `active_app`, or
  `playlist` (`{name, page, pages}`, `name` being null for one that was
  pushed rather than saved), plus `scheduled` when the schedule started it.
  The banner above the tabs shows it with a STOP button; `POST /stop_app`
  stops an app or a playlist alike. `POST /playlists/<name>/run` plays a
  saved playlist under its name, and saving the playlist that's playing
  updates the display straight away.
- **Saved playlists are edited in place**: Edit loads one and keeps its name
  in the box, so Save updates it. Saving under a name that's already taken
  by a different playlist asks first. **Rename** edits the name in its row
  (`POST /playlists/<name>/rename`); the schedule's slots and default that
  pointed at it, the playlist that's playing and the one being edited all
  follow the new name. A name that's taken is refused.
- **Undo**: deleting a saved playlist, removing a playlist page or a
  schedule slot, and Clear each show a toast with Undo (8 s), and Ctrl+Z /
  ⌘Z does the same while it's up, unless you're typing in a field. Deleting
  a saved playlist no longer asks "are you sure?": `DELETE /playlists/<name>`
  answers with the playlist, and Undo saves it again. A removed schedule
  slot only stays removed once the schedule is saved.
- **Preview** (▷ Preview, next to Center Lines) plays the page, or with
  Multi-Page Playlist on the whole playlist, in the compose grid the way the
  display will: starting from what's on the display now, each flap starts
  at its turn in the transition (its rank × the page's speed, plus bus
  time) and turns forward through the reel at the reel's speed, then the
  page holds for its delay. Nothing is sent. Typing or clicking in the grid
  ends it. The page config carries each transition's order for this
  (Random's is one random order; the display picks a new one each time).
- **The schedule** (Apps page; `display/scheduler.py`, `GET/POST /schedule`,
  stored as `settings['schedule']`) picks an app or saved playlist by time
  of day and weekday, in the timezone from the global settings. Time slots
  are checked in order and the first that covers the time wins; outside
  them the default runs, or nothing changes. A slot (or the default) can
  also **blank the display**, for quiet hours: it shows a blank page and
  keeps it blank (the banner says so) until something else starts. The
  scheduler only acts when
  what the schedule calls for changes (checked every 20 s, and straight
  away on startup or when the schedule is saved), so starting or stopping
  something by hand lasts until the next scheduled change.
- **Playlist pages** can be dragged by their ⠿ handle (mouse or finger),
  duplicated (⧉), or shown on their own (▶). The backend checks every page
  it's sent (`display/pages.py`): delays, speeds and transitions must be
  real values, and they're stored as numbers.
- **Settings are typed**: `SettingField.clean()` (apps/base.py) turns what
  the page sends into the field's type (number, checkbox, select option or
  text) and refuses anything else with the field's name, for app and global
  settings alike. A blank number field means its default.
- **Pages stay current**: every save of settings.json bumps
  `settings_version` in the live state, so an open Modules page reloads its
  module data when another device (or a sync or restore) changes it, and the
  saved playlist list refreshes. Shared firmware settings someone is
  part-way through editing aren't overwritten.
- **Sync progress**: Sync All reports each module's result over the live
  state as it arrives (`sync` in the snapshot), so the module grid flashes a
  module green when it answers and turns it orange if it doesn't (after one
  individual retry). A failed module stays orange, and its inspector says
  "Sync failed", until it next syncs; a single module's Sync EEPROM counts
  too. The status is kept by the server, so every open page shows it.
- **Backups hold everything**: Download Backup (version 4) has the modules,
  the settings for all modules, saved playlists, the schedule, and every app
  and global setting. Restoring checks each part the way saving it from the
  page would; anything that doesn't check out is skipped and listed, and
  the rest is still restored. Saved playlists are merged in by name. An
  older (version 3) backup restores just the modules, as before.
- **Timezone** is a list of real timezones, so a typo can't break every
  clock. An unknown name already in settings.json is shown as "not
  recognised" until it's changed, and the apps use US/Eastern meanwhile.
- **Phone install**: the page has a web app manifest
  (`/manifest.webmanifest`) and icons (`static/icons/`, drawn by
  `tools/make_icons.py`), so Add to Home Screen gives it an icon and opens
  it full screen. Browsers that offer to install it get an Install button
  at the bottom of the page.
- **The Control page's draft** (the grid, the playlist being built, its
  defaults and name) is kept in the browser's localStorage, so a reload
  doesn't lose it. It's per browser and best-effort; nothing depends on it.

## Themes and accessibility

- **Light and dark** follow the system setting (`prefers-color-scheme`).
  Every colour is a variable at the top of `static/css/base.css`; light mode
  overrides them in one block. The display boxes (live display, compose
  grid, symbol tiles) keep their own fixed colours and stay dark in both,
  like the real hardware. Text and controls meet WCAG AA contrast in both
  themes; if you change a colour, check it still does.
- **Keyboard**: everything works without a mouse. The tabs and the module
  grid each take one Tab stop and are moved round with the arrow keys
  (plus Home/End); the settings dialog keeps focus inside it and closes with
  Escape; reordering playlist pages or schedule slots keeps focus in place.
  Dragging a page is for pointers; its ▲ ▼ buttons do the same by keyboard.
- **Screen readers**: the live display is read as its text, row by row,
  rather than as 64 flaps; the compose grid says where the cursor is and
  what that row says; buttons that are only a symbol (▲, ⧉, ✕, ⚙️, module
  cells) have names that say what they act on; toasts are read out, and
  errors interrupt. Pages are an ARIA tab list.
- **Reduced motion** (`prefers-reduced-motion`): no flipping, pulsing or
  sliding. The live display jumps straight to each character. The green
  sync flash still fades, since it's a colour change, not movement.

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
- Per-flap fine-tuning (the old `w<idx>:<pos>` and its Auto Fine-Tune wizard)
  is now the firmware's flap offsets: `J<n>` sets the offset of the flap
  showing (steps + 128) and `%` dumps them all. Modules aren't expected
  to need it, so it's only on the Debug page, not the Modules page.
- Backend tests: run `python -m unittest discover -s tests` from `frontend/`
  (the route tests need Flask). They cover the dump parser and protocol
  (checked against the firmware source), the module, settings, playlist and
  firmware routes, backup restore, the page and its configuration, the
  animation orders, the SSE subscriber queues and the app base classes. The
  route tests load each route file with the settings store and serial link
  faked, so nothing touches a serial port or settings.json.
