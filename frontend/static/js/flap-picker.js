// The flap in the inspector's actions: turn it to a character by scrolling
// over it, dragging it, tapping its top or bottom half, or with the arrow
// keys, and once it has stood still for a moment the selected module shows
// that character (through flapTuner.show(), in flap-tuner.js).

const flapPicker = {
  index: 0,               // the flap showing, as an index into CHAR_MAP
  delayMs: 3000,          // how long it has to stand still before it's sent
  timer: null,
  wheelDelta: 0,          // scrolling not yet turned into a step
  drag: null,             // {y, moved} while a pointer is down on it

  // A trackpad's small scrolls add up to a flap every WHEEL_STEP pixels; a
  // mouse wheel's notch (a scroll of NOTCH or more) is one flap. Dragging
  // DRAG_STEP pixels is one flap.
  WHEEL_STEP: 40,
  NOTCH: 50,
  DRAG_STEP: 24,

  init() {
    const flap = byId('flapPicker');
    flap.addEventListener('wheel', e => this.onWheel(e), {passive: false});
    flap.addEventListener('pointerdown', e => this.onPointerDown(e));
    flap.addEventListener('pointermove', e => this.onPointerMove(e));
    flap.addEventListener('pointerup', e => this.onPointerUp(e));
    flap.addEventListener('pointercancel', () => { this.drag = null; });
    flap.addEventListener('keydown', e => this.onKey(e));
    this.show(this.index);
  },

  enabled() {
    return !byId('manualControls').classList.contains('disabled');
  },

  // Called when the inspector shows a module: starts from what it's showing
  // (from the live display), and drops anything waiting to be sent.
  moduleSelected(id) {
    this.cancel();
    const shown = (liveState.state || '')[id];
    const index = CHAR_MAP.indexOf(shown === undefined ? ' ' : shown);
    this.show(index >= 0 ? index : 0);
    byId('flapPicker').setAttribute('aria-disabled', String(!this.enabled()));
  },

  // ── Input ──

  onWheel(e) {
    if (!this.enabled()) return;
    e.preventDefault();   // turn the flap, not the page
    if (!e.deltaY) return;
    // deltaMode 1 counts lines: Firefox's mouse wheel.
    if (e.deltaMode === 1 || Math.abs(e.deltaY) >= this.NOTCH) {
      this.wheelDelta = 0;
      this.turn(Math.sign(e.deltaY));
      return;
    }
    this.wheelDelta += e.deltaY;
    while (Math.abs(this.wheelDelta) >= this.WHEEL_STEP) {
      const step = Math.sign(this.wheelDelta);
      this.wheelDelta -= step * this.WHEEL_STEP;
      this.turn(step);
    }
  },

  onPointerDown(e) {
    if (!this.enabled()) return;
    this.drag = {y: e.clientY, moved: false};
    byId('flapPicker').setPointerCapture?.(e.pointerId);
  },

  onPointerMove(e) {
    if (!this.drag) return;
    // Dragging down turns it forward, as scrolling down does.
    const distance = e.clientY - this.drag.y;
    if (Math.abs(distance) < this.DRAG_STEP) return;
    const step = Math.sign(distance);
    this.drag.y += step * this.DRAG_STEP;
    this.drag.moved = true;
    this.turn(step);
  },

  onPointerUp(e) {
    const drag = this.drag;
    this.drag = null;
    if (!drag || drag.moved) return;
    // A tap: the top half goes back a flap, the bottom half on one.
    const box = byId('flapPicker').getBoundingClientRect();
    this.turn(e.clientY < box.top + box.height / 2 ? -1 : 1);
  },

  onKey(e) {
    if (!this.enabled()) return;
    const steps = {ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1, PageDown: 8, PageUp: -8};
    if (e.key in steps) {
      e.preventDefault();
      this.turn(steps[e.key]);
    } else if (e.key === 'Home' || e.key === 'End') {
      e.preventDefault();
      this.turnTo(e.key === 'Home' ? 0 : CHAR_MAP.length - 1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (this.timer) this.send();
    } else if (e.key === 'Escape') {
      this.cancel();
    }
  },

  // ── Turning and sending ──

  // Turns `step` flaps forward (or back, if negative), wrapping round.
  turn(step) {
    const n = CHAR_MAP.length;
    this.turnTo(((this.index + step) % n + n) % n, step > 0 ? 1 : -1);
  },

  turnTo(index, direction = 1) {
    if (index === this.index) return;
    this.flip(CHAR_MAP[this.index], CHAR_MAP[index], direction);
    this.show(index);
    this.schedule();
  },

  // (Re)starts the wait before sending, with the bar running down.
  schedule() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.send(), this.delayMs);
    const bar = byId('pickerProgress');
    bar.style.transition = 'none';
    bar.style.width = '100%';
    void bar.offsetWidth;   // so the transition starts from full
    bar.style.transition = `width ${this.delayMs}ms linear`;
    bar.style.width = '0';
    this.setStatus('Sending…');
  },

  cancel() {
    if (!this.timer) return;
    clearTimeout(this.timer);
    this.timer = null;
    this.stopBar();
    this.setStatus('');
  },

  send() {
    clearTimeout(this.timer);
    this.timer = null;
    this.stopBar();
    this.setStatus('');
    // Through the flap offset row, which reads the flap's offset once the
    // module is there.
    flapTuner.show(this.index);
  },

  stopBar() {
    const bar = byId('pickerProgress');
    bar.style.transition = 'none';
    bar.style.width = '0';
  },

  setStatus(text) {
    byId('pickerStatus').textContent = text;
  },

  // ── Drawing ──

  show(index) {
    this.index = index;
    const ch = CHAR_MAP[index];
    const flap = byId('flapPicker');
    flap.querySelector('.ft .fc').textContent = displayChar(ch);
    flap.querySelector('.fb .fc').textContent = displayChar(ch);
    flap.setAttribute('aria-valuenow', index);
    flap.setAttribute('aria-valuetext', flapLabel(ch));
    byId('pickerName').textContent = `${flapLabel(ch)} · flap ${index}`;
  },

  // One flip from `from` to `to`, as on the live display (live-flap.js):
  // forward, the top half falls and the bottom swings down; back, the other
  // way round.
  flip(from, to, direction) {
    if (reducedMotion.matches) return;
    const flap = byId('flapPicker');
    flap.querySelectorAll('.ff').forEach(e => e.remove());
    const forward = direction > 0;
    const first = el('div', {class: `ff ${forward ? 'ffd' : 'ffu-back'}`}, el('span', {class: 'fc'}, displayChar(from)));
    const second = el('div', {class: `ff ${forward ? 'ffu' : 'ffd-back'}`}, el('span', {class: 'fc'}, displayChar(to)));
    flap.append(first, second);
    // Until the second half lands, the half it lands on still shows the
    // old character.
    flap.querySelector(forward ? '.fb .fc' : '.ft .fc').textContent = displayChar(from);
    setTimeout(() => {
      first.remove();
      second.remove();
      this.show(this.index);   // whatever it has turned to by now
    }, 90);
  },
};
