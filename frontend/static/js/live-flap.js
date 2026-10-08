// The animated copy of the display above the tabs, kept in step with the
// real one over /current_state/stream.

let liveFlaps = [];

// Whether the system asks for less movement. Then a flap jumps straight to
// its character instead of flipping through every one on the way.
const reducedMotion = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : {matches: false};

// One flap on screen. Like a real module it only turns forwards, one
// character at a time, until it reaches its target.

class LiveFlap {
  constructor(el) {
    this.el = el;
    this.curIdx = 0;
    this.tgtIdx = 0;
    this.busy = false;
    this.queued = null;
  }
  setTarget(idx, delay) {
    this.tgtIdx = idx;
    if (this.curIdx === this.tgtIdx) return;
    if (reducedMotion.matches) {
      this.curIdx = idx;
      this.queued = null;
      this._render(CHAR_MAP[idx]);
      return;
    }
    if (this.busy) { this.queued = idx; return; }
    setTimeout(() => this._step(), delay);
  }
  _step() {
    if (this.curIdx === this.tgtIdx) {
      this.busy = false;
      if (this.queued !== null) { this.tgtIdx = this.queued; this.queued = null; if (this.curIdx !== this.tgtIdx) this._step(); }
      return;
    }
    this.busy = true;
    const next = (this.curIdx + 1) % CHAR_MAP.length;
    this._flip(CHAR_MAP[this.curIdx], CHAR_MAP[next], () => { this.curIdx = next; this._render(CHAR_MAP[next]); this._step(); });
  }
  _render(ch) {
    const shown = displayChar(ch);
    this.el.querySelector('.ft .fc').textContent = shown;
    this.el.querySelector('.fb .fc').textContent = shown;
  }
  _flip(from, to, done) {
    const next = displayChar(to);
    this.el.querySelectorAll('.ff').forEach(e => e.remove());
    // The top half falls away showing the old character, then the bottom
    // half swings down showing the new one.
    const down = el('div', {class: 'ff ffd'}, el('span', {class: 'fc'}, displayChar(from)));
    const up = el('div', {class: 'ff ffu'}, el('span', {class: 'fc'}, next));
    this.el.querySelector('.fb .fc').textContent = next;
    this.el.append(down, up);
    setTimeout(() => {
      down.remove();
      up.remove();
      this.el.querySelector('.ft .fc').textContent = next;
      done();
    }, 90);
  }
}

function initLiveGrids() {
  const grid = byId('liveGrid');
  grid.style.gridTemplateColumns = `repeat(${GRID_COLS}, 1fr)`;
  const flaps = Array.from({length: NUM_MODULES}, () => el('div', {class: 'live-flap'},
    el('div', {class: 'fh ft'}, el('span', {class: 'fc'})),
    el('div', {class: 'fh fb'}, el('span', {class: 'fc'})),
    el('div', {class: 'fd'})));
  grid.replaceChildren(...flaps);
  liveFlaps = flaps.map(flap => new LiveFlap(flap));
}

// The latest snapshot, for anything drawn after it arrived (the saved
// playlist rows mark the one that's playing).
let liveState = {};

// What the banner says is playing, or '' when nothing is worth a banner: a
// single unsaved page just sits on the display, with nothing to stop.
function nowPlayingText(data) {
  let text = '';
  const playing = data.playlist;
  if (data.active_app) {
    text = `▶ ${appName(data.active_app)} is running`;
  } else if (playing && (playing.name || playing.pages > 1)) {
    const what = playing.name ? `Playlist "${playing.name}"` : 'Playlist';
    text = `▶ ${what} · page ${playing.page + 1} of ${playing.pages}`;
  }
  return text && data.scheduled ? `${text} (scheduled)` : text;
}

// Pulled out from the SSE wiring below so it can be exercised directly in
// tests (and reused for anything else that ever wants to push a snapshot
// into the UI) without needing a real or mocked EventSource in the loop.
function applyLiveState(data) {
  if (!data) return;
  liveState = data;

  const text = data.state || '';
  byId('homingOverlay').style.display = data.is_homed ? 'none' : 'flex';
  byId('liveDisplay').setAttribute('aria-label', describeDisplay(text, data.is_homed));
  // Older backends don't send it; only say so when it's definitely false.
  byId('simBadge').hidden = data.hardware_connected !== false;
  liveFlaps.forEach((flap, i) => {
    const idx = CHAR_MAP.indexOf(text[i] || ' ');
    flap.setTarget(idx >= 0 ? idx : 0, i * 5);   // a slight ripple across the grid
  });
  renderBanner();
  markRunning();
  noticeSettingsVersion(data.settings_version);
  noticeSyncState(data.sync);
}

// The settings were saved (here or on another device) since this page last
// heard: reload what shows them, once a burst of saves has settled.
let seenSettingsVersion;
let settingsReloadTimer = null;
function noticeSettingsVersion(version) {
  if (version === undefined || version === seenSettingsVersion) return;
  const first = seenSettingsVersion === undefined;
  seenSettingsVersion = version;
  if (first) return;   // the page loaded everything itself just now
  clearTimeout(settingsReloadTimer);
  settingsReloadTimer = setTimeout(settingsChanged, 300);
}

function settingsChanged() {
  if (byId('page-modules').classList.contains('active')) refreshModulesPage();
  loadSavedPlaylists();
}

function renderBanner() {
  const playing = nowPlayingText(liveState);
  byId('live-banner').classList.toggle('visible', !!playing);
  byId('liveBannerText').textContent = playing;
}

// What the display shows, as screen readers hear it: each row that isn't
// blank, in order.
function describeDisplay(text, homed) {
  const chars = Array.from(text);
  const rows = [];
  for (let r = 0; r < GRID_ROWS; r++) {
    const row = chars.slice(r * GRID_COLS, (r + 1) * GRID_COLS).map(ch => displayChar(ch) || ' ').join('').trim();
    if (row) rows.push(row);
  }
  const shown = rows.length ? `The display shows: ${rows.join(' / ')}` : 'The display is blank';
  return homed === false ? `Homing required. ${shown}` : shown;
}

// Highlights the app card or saved playlist that's playing, if one is.
function markRunning() {
  const app = liveState.active_app;
  document.querySelectorAll('.app-card').forEach(card => {
    const running = !!app && card.dataset.app === app;
    card.classList.toggle('running', running);
    card.querySelector('.app-running').textContent = running ? ' (running)' : '';
  });
  const name = !app && liveState.playlist ? liveState.playlist.name : null;
  document.querySelectorAll('.saved-pl-item').forEach(row => {
    row.classList.toggle('running', name !== null && row.dataset.name === name);
  });
}

// Replaces the old setInterval(...)-based polling of /current_state with a
// persistent connection to /current_state/stream: the backend pushes a
// snapshot only when something actually changes (see DisplayState._broadcast
// in display/state.py), so updates are near-instant instead of up to 1s
// stale, and there's no request firing every second when nothing's moving.
function startLiveUpdates() {
  const source = new EventSource('/current_state/stream');
  const statusEl = document.getElementById('streamStatus');

  source.onopen = () => {
    // Fires on the initial connect AND every successful auto-reconnect —
    // either way, the stream is live again, so clear the "reconnecting" banner.
    if (statusEl) statusEl.classList.remove('visible');
  };

  source.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      console.error('Bad SSE payload:', event.data, err);
      return;
    }
    applyLiveState(data);
  };

  source.onerror = () => {
    // The browser retries the connection automatically (that's part of the
    // EventSource spec) — surface it in the UI too, not just the console,
    // so a dropped connection doesn't look identical to "nothing changed."
    console.warn('Live state stream disconnected — the browser will retry automatically.');
    if (statusEl) statusEl.classList.add('visible');
  };

  return source;
}
