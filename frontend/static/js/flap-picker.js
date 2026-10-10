// The flap in the inspector's actions: turn it to a character by scrolling
// over it, dragging it, tapping its top or bottom half, or with the arrow
// keys, and once it has stood still for a moment the selected module shows
// that character (through flapTuner.show(), in flap-tuner.js). A drag turns
// the flap with the pointer, a flap for each flap's height dragged, and
// the wait only starts once it's let go.

const flapPicker = {
  index: 0,               // the flap showing, as an index into CHAR_MAP
  delayMs: 2000,          // how long it has to stand still before it's sent
  timer: null,
  wheelDelta: 0,          // scrolling not yet turned into a step
  drag: null,             // while a pointer is down on it: see onPointerDown()
  settling: null,         // the timer of a drag's flap finishing its turn
  settled: null,          // draws where it finishes

  // A trackpad's small scrolls add up to a flap every WHEEL_STEP pixels; a
  // mouse wheel's notch (a scroll of NOTCH or more) is one flap. A pointer
  // that moves less than TAP_SLOP pixels before it's let go is a tap.
  WHEEL_STEP: 40,
  NOTCH: 50,
  TAP_SLOP: 6,

  init() {
    const flap = byId('flapPicker');
    flap.addEventListener('wheel', e => this.onWheel(e), {passive: false});
    flap.addEventListener('pointerdown', e => this.onPointerDown(e));
    flap.addEventListener('pointermove', e => this.onPointerMove(e));
    flap.addEventListener('pointerup', e => this.onPointerUp(e));
    flap.addEventListener('pointercancel', () => this.endDrag(0));
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

  // A drag remembers where it started: the pointer's y, the flap showing,
  // and whether a wait to send was already running (it's held while the
  // flap is held).
  onPointerDown(e) {
    if (!this.enabled()) return;
    this.finishSettling();
    const flap = byId('flapPicker');
    this.drag = {
      y: e.clientY,
      index: this.index,
      height: flap.getBoundingClientRect().height || 126,
      pending: !!this.timer,
      moved: false,
      turns: 0,
    };
    this.pause();
    flap.setPointerCapture?.(e.pointerId);
  },

  // Dragging down turns it forward, as scrolling down does: the flap follows
  // the pointer, a flap for each flap's height.
  onPointerMove(e) {
    if (!this.drag) return;
    const distance = e.clientY - this.drag.y;
    if (!this.drag.moved && Math.abs(distance) < this.TAP_SLOP) return;
    this.drag.moved = true;
    this.drag.turns = distance / this.drag.height;
    this.drawTurn(this.drag.index, this.drag.turns);
  },

  onPointerUp(e) {
    const drag = this.drag;
    if (!drag) return;
    if (drag.moved) {
      // It settles on the nearest flap.
      this.endDrag(Math.round(drag.turns));
      return;
    }
    this.drag = null;
    // A tap: the top half goes back a flap, the bottom half on one.
    const box = byId('flapPicker').getBoundingClientRect();
    this.turn(e.clientY < box.top + box.height / 2 ? -1 : 1);
  },

  // Lets go of a drag `turns` flaps on from where it started: the flap
  // finishes turning (or turns back) to it, and the wait to send starts if
  // it's on a different flap, or a wait was running when the drag began.
  endDrag(turns) {
    const drag = this.drag;
    if (!drag) return;
    this.drag = null;
    const n = CHAR_MAP.length;
    const index = ((drag.index + turns) % n + n) % n;
    this.index = index;
    this.settle(drag.index, drag.turns, turns);
    if (index !== drag.index || drag.pending) this.schedule();
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

  // (Re)starts the wait before sending, with the bar running down. Not
  // while the flap is held: letting go starts it.
  schedule() {
    clearTimeout(this.timer);
    this.timer = null;
    if (this.drag) {
      this.drag.pending = true;
      return;
    }
    this.timer = setTimeout(() => this.send(), this.delayMs);
    const bar = byId('pickerProgress');
    bar.style.transition = 'none';
    bar.style.width = '100%';
    void bar.offsetWidth;   // so the transition starts from full
    bar.style.transition = `width ${this.delayMs}ms linear`;
    bar.style.width = '0';
  },

  // Stops the wait, leaving nothing to send.
  cancel() {
    if (this.drag) this.drag.pending = false;
    this.pause();
  },

  // Stops the wait (a drag may start it again).
  pause() {
    if (!this.timer) return;
    clearTimeout(this.timer);
    this.timer = null;
    this.stopBar();
  },

  send() {
    clearTimeout(this.timer);
    this.timer = null;
    this.stopBar();
    // Through the flap offset row, which reads the flap's offset once the
    // module is there.
    flapTuner.show(this.index);
  },

  stopBar() {
    const bar = byId('pickerProgress');
    bar.style.transition = 'none';
    bar.style.width = '0';
  },

  // ── Drawing ──

  show(index) {
    this.index = index;
    this.draw(index);
  },

  // Draws flap `index` (a drag draws the flaps it passes before it's let
  // go on one).
  draw(index) {
    const ch = CHAR_MAP[index];
    const flap = byId('flapPicker');
    flap.querySelector('.ft .fc').textContent = displayChar(ch);
    flap.querySelector('.fb .fc').textContent = displayChar(ch);
    flap.classList.toggle('tile', displayChar(ch) in TILE_CODES);   // drawn smaller, as in the compose grid
    flap.setAttribute('aria-valuenow', index);
    flap.setAttribute('aria-valuetext', flapLabel(ch));
    byId('pickerName').textContent = `${flapLabel(ch)} · flap ${index}`;
  },

  // A drag's flap part way through its turn, `turns` flaps on from flap
  // `start` (negative is back). Between flaps a and a+1, the turn is the
  // first half of the flip (a's top half falling, a+1's top showing behind
  // it) and then the second (a+1's bottom half swinging down over a's).
  drawTurn(start, turns) {
    const n = CHAR_MAP.length;
    const whole = Math.floor(turns);
    const part = turns - whole;
    const from = ((start + whole) % n + n) % n;
    const to = (from + 1) % n;
    this.draw(part < .5 ? from : to);
    const flap = byId('flapPicker');
    flap.querySelectorAll('.ff').forEach(e => e.remove());
    if (!part) return;
    flap.querySelector('.ft .fc').textContent = displayChar(CHAR_MAP[to]);
    flap.querySelector('.fb .fc').textContent = displayChar(CHAR_MAP[from]);
    // Each half is drawn only while it's on its way: past 90° it's edge on.
    const angle = deg => `transform: rotateX(${Math.round(deg * 10) / 10}deg)`;
    const piece = part < .5
      ? el('div', {class: 'ff ffd ff-held', style: angle(-180 * part)},
          el('span', {class: 'fc'}, displayChar(CHAR_MAP[from])))
      : el('div', {class: 'ff ffu ff-held', style: angle(180 * (1 - part))},
          el('span', {class: 'fc'}, displayChar(CHAR_MAP[to])));
    flap.append(piece);
  },

  // A let-go drag's flap finishing its turn from `turns` to `target` flaps
  // on from `start`, a few frames a flap.
  settle(start, turns, target) {
    this.finishSettling();
    if (reducedMotion.matches || turns === target) {
      this.drawTurn(start, target);
      return;
    }
    const frameMs = 16;
    const frames = Math.max(2, Math.round(Math.abs(target - turns) * 8));
    let frame = 0;
    const step = () => {
      frame += 1;
      if (frame >= frames) {
        this.finishSettling();
        return;
      }
      this.drawTurn(start, turns + (target - turns) * frame / frames);
      this.settling = setTimeout(step, frameMs);
    };
    this.settling = setTimeout(step, frameMs);
    this.settled = () => this.drawTurn(start, target);
  },

  // Ends a let-go drag's turn straight away, on its flap.
  finishSettling() {
    if (!this.settling) return;
    clearTimeout(this.settling);
    this.settling = null;
    this.settled();
  },

  // One flip from `from` to `to`, as on the live display (live-flap.js):
  // forward, the top half falls and the bottom swings down; back, the other
  // way round.
  flip(from, to, direction) {
    this.finishSettling();
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
