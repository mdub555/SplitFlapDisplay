// The animated copy of the display on the Control and Apps pages, kept in
// step with the real one over /current_state/stream.

// The pages that show the live display (see live_display() in index.html).
const LIVE_PAGES = ['control', 'apps'];
const liveFlaps = Object.fromEntries(LIVE_PAGES.map(page => [page, []]));

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
  LIVE_PAGES.forEach(page => {
    const grid = document.querySelector(`.live-grid-${page}`);
    grid.style.gridTemplateColumns = `repeat(${GRID_COLS}, 1fr)`;
    const flaps = Array.from({length: NUM_MODULES}, () => el('div', {class: 'live-flap'},
      el('div', {class: 'fh ft'}, el('span', {class: 'fc'})),
      el('div', {class: 'fh fb'}, el('span', {class: 'fc'})),
      el('div', {class: 'fd'})));
    grid.replaceChildren(...flaps);
    liveFlaps[page] = flaps.map(flap => new LiveFlap(flap));
  });
}

// Pulled out from the SSE wiring below so it can be exercised directly in
// tests (and reused for anything else that ever wants to push a snapshot
// into the UI) without needing a real or mocked EventSource in the loop.
function applyLiveState(data) {
  if (!data) return;

  const text = data.state || '';
  const app = data.active_app;
  LIVE_PAGES.forEach(page => {
    byId(`homing-${page}`).style.display = data.is_homed ? 'none' : 'flex';
    liveFlaps[page].forEach((flap, i) => {
      const idx = CHAR_MAP.indexOf(text[i] || ' ');
      flap.setTarget(idx >= 0 ? idx : 0, i * 5);   // a slight ripple across the grid
    });
    byId(`${page}-banner`).classList.toggle('visible', !!app);
    if (app) byId(`${page}-app-name`).textContent = appName(app);
  });

  document.querySelectorAll('.app-card').forEach(card => {
    card.classList.toggle('running', card.dataset.app === app);
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
