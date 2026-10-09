// The flap offset row in the inspector's settings: the offset of the flap
// the selected module is showing, shifted a few steps either way. The flap
// picker (flap-picker.js) moves the module through show(), which answers
// once the module has stopped there with every flap's offset (see the
// show_flap and flap_offset routes), so the row always shows what the
// module has saved.

const flapTuner = {
  moduleId: null,    // the module the flap and offsets below are for
  flap: null,        // the flap it's showing, once the picker has moved it
  offsets: null,     // every flap's offset, in steps, as it last reported
  busy: false,
  queuedFlap: null,  // a flap picked while a request was still running

  init() {
    byId('tunerOffset').addEventListener('keydown', e => { if (e.key === 'Enter') this.apply(); });
    this.render();
  },

  // Called when the inspector shows a module. Another module's flap and
  // offsets aren't known until it moves.
  moduleSelected(id) {
    if (id === this.moduleId) return this.render();
    this.moduleId = id;
    this.flap = null;
    this.offsets = null;
    this.queuedFlap = null;
    this.setStatus('');
    this.render();
  },

  // Shows `flap` on the selected module, and reads every flap's offset once
  // it's there. The flap picker calls this.
  show(flap) {
    if (this.busy) {
      this.queuedFlap = flap;
      return;
    }
    this.request(`Moving to ${flapLabel(CHAR_MAP[flap])}…`, id => api.showFlap(id, flap), flap);
  },

  // Sets the showing flap's offset to the value typed, or to its current
  // offset plus `delta`.
  apply(delta) {
    if (!this.editable()) return;
    const {min, max} = CONFIG.flap_offsets;
    const typed = byId('tunerOffset').value.trim();
    const offset = delta !== undefined ? this.offsets[this.flap] + delta : typed === '' ? NaN : Number(typed);
    if (!Number.isInteger(offset) || offset < min || offset > max) {
      showToast(`The offset must be a whole number from ${min} to ${max}`, 'error');
      return;
    }
    if (offset === this.offsets[this.flap]) return;
    const note = offset < this.offsets[this.flap] ? ' (nearly a full revolution)' : '';
    const flap = this.flap;
    this.request(`Moving ${flapLabel(CHAR_MAP[flap])} to ${signed(offset)}${note}…`,
                 id => api.setFlapOffset(id, flap, offset));
  },

  // Runs one request for the selected module, keeping the row disabled
  // until it answers. `flap`, for a move, is the flap it was sent to.
  async request(status, call, flap) {
    const id = this.moduleId;
    this.busy = true;
    this.setStatus(status);
    this.render();
    const result = await call(id);
    this.busy = false;
    // Another module may have been picked while this one moved.
    if (id === this.moduleId) {
      if (result) {
        this.flap = result.flap;
        this.offsets = result.offsets;
      } else if (flap !== undefined) {
        this.flap = flap;   // it was sent, but its offsets weren't read
        this.offsets = null;
      }
    }
    this.setStatus(!result && flap !== undefined && id === this.moduleId
      ? "The module didn't report back, so its offsets can't be shown." : '');
    this.render();
    if (this.queuedFlap !== null) {
      const next = this.queuedFlap;
      this.queuedFlap = null;
      this.show(next);
    }
  },

  setStatus(text) {
    byId('tunerStatus').textContent = text;
  },

  // Flap 0 is where homing ends: the home offset places it.
  editable() {
    return !this.busy && this.usable() && this.flap !== null && this.flap !== 0 && this.offsets !== null;
  },

  // Like the inspector's other settings, only for a provisioned module.
  usable() {
    return this.moduleId !== null && !!moduleSettings(this.moduleId);
  },

  render() {
    const editable = this.editable();
    byId('tunerFlapName').textContent = this.flap === null ? '—' : flapLabel(CHAR_MAP[this.flap]);
    const input = byId('tunerOffset');
    input.value = editable ? this.offsets[this.flap] : '';
    input.placeholder = this.flap === 0 && this.usable() ? 'home offset' : '';
    input.disabled = !editable;
    byId('flapTuner').querySelectorAll('button:not(.info-btn)').forEach(button => { button.disabled = !editable; });

    let summary = '';
    if (this.offsets && this.usable()) {
      const shifted = this.offsets.flatMap((offset, flap) =>
        offset ? [`${flapLabel(CHAR_MAP[flap])} ${signed(offset)}`] : []);
      summary = shifted.length ? `Flaps with an offset: ${shifted.join(' · ')}` : 'No flap has an offset.';
    }
    byId('tunerSummary').textContent = summary;
  },
};

// An offset with its sign, e.g. +3, -2 or 0.
const signed = n => n > 0 ? `+${n}` : String(n);

registerActions({
  tunerNudge: button => flapTuner.apply(Number(button.dataset.delta)),
  tunerApply: () => flapTuner.apply(),
});
