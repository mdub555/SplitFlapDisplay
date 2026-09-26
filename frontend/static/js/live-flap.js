const liveFlaps = {control: [], apps: []};

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
    const d = STATE_DISPLAY[ch] || ch;
    const v = d === ' ' ? '' : d;
    this.el.querySelector('.ft .fc').textContent = v;
    this.el.querySelector('.fb .fc').textContent = v;
  }
  _flip(from, to, done) {
    const fd = STATE_DISPLAY[from] || from;
    const td = STATE_DISPLAY[to] || to;
    const fv = fd === ' ' ? '' : fd;
    const tv = td === ' ' ? '' : td;
    this.el.querySelectorAll('.ff').forEach(e => e.remove());
    const dn = document.createElement('div'); dn.className = 'ff ffd';
    const dnc = document.createElement('span'); dnc.className = 'fc'; dnc.textContent = fv; dn.appendChild(dnc);
    const up = document.createElement('div'); up.className = 'ff ffu';
    const upc = document.createElement('span'); upc.className = 'fc'; upc.textContent = tv; up.appendChild(upc);
    this.el.querySelector('.fb .fc').textContent = tv;
    this.el.appendChild(dn); this.el.appendChild(up);
    setTimeout(() => { dn.remove(); up.remove(); this.el.querySelector('.ft .fc').textContent = tv; done(); }, 90);
  }
}

function initLiveGrids() {
  ['control', 'apps'].forEach(tab => {
    const grid = document.querySelector(`.live-grid-${tab}`);
    if (!grid) return;
    grid.style.gridTemplateColumns = `repeat(${GRID_COLS}, 1fr)`;
    grid.innerHTML = '';
    liveFlaps[tab] = [];
    for (let i = 0; i < NUM_MODULES; i++) {
      const el = document.createElement('div');
      el.className = 'live-flap';
      el.innerHTML = '<div class="fh ft"><span class="fc"></span></div><div class="fh fb"><span class="fc"></span></div><div class="fd"></div>';
      grid.appendChild(el);
      liveFlaps[tab].push(new LiveFlap(el));
    }
  });
}

function startLivePolling() {
  setInterval(()=>{
    api.currentState().then(data=>{
      if (!data) return; // failed tick — no toast (see api.js), just skip this update

      ['control','apps'].forEach(tab=>{
        const el = document.getElementById(`homing-${tab}`);
        if(el) el.style.display = data.is_homed ? 'none' : 'flex';
      });

      const s = data.state || '';
      ['control','apps'].forEach(tab=>{
        const fa = liveFlaps[tab];
        for(let i=0; i<fa.length; i++){
          const ch = s[i] || ' ';
          const idx = CHAR_MAP.indexOf(ch);
          fa[i].setTarget(idx >= 0 ? idx : 0, i * 5);
        }
      });

      const app = data.active_app;
      const appInfo = app ? (window.appsByKey[app] || {name: app}) : null;
      ['control','apps'].forEach(tab=>{
        const banner = document.getElementById(`${tab}-banner`);
        const nameEl = document.getElementById(`${tab}-app-name`);
        if(banner){
          banner.classList.toggle('visible', !!app);
          if(app && nameEl) nameEl.textContent = appInfo.name;
        }
      });

      document.querySelectorAll('.app-card').forEach(c=>{
        c.classList.toggle('running', c.dataset.app === app);
      });
    });
  }, 1000);
}
