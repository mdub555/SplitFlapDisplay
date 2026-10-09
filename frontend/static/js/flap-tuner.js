// The flap offset tuner in the Modules page's inspector (a section that
// opens and closes): step the selected
// module through its flaps, and shift the one showing a few steps either
// way. Every request answers once the module has stopped moving, with every
// flap's offset (see the show_flap and flap_offset routes), so the tuner
// always shows what the module has saved.

const flapTuner = {
  moduleId: null,  // the module the flap and offsets below are for
  flap: null,      // the flap it's showing, once the tuner has moved it
  offsets: null,   // every flap's offset, in steps, as it last reported
  busy: false,

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
    this.setStatus('');
    this.render();
  },

  // Moves to the next (step 1) or previous (step -1) flap, wrapping round.
  step(step) {
    const flap = this.flap === null ? (step > 0 ? 1 : CHAR_MAP.length - 1)
                                    : (this.flap + step + CHAR_MAP.length) % CHAR_MAP.length;
    this.request(`Moving to flap ${flap}…`, id => api.showFlap(id, flap));
  },

  // Sets the showing flap's offset to the value typed, or to its current
  // offset plus `delta`.
  apply(delta) {
    if (this.flap === null || this.flap === 0) return;
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
    this.request(`Moving flap ${flap} to ${signed(offset)}${note}…`, id => api.setFlapOffset(id, flap, offset));
  },

  // Runs one request for the selected module, keeping the controls disabled
  // until it answers.
  async request(status, call) {
    if (this.busy) return;
    const id = this.moduleId;
    this.busy = true;
    this.setStatus(status);
    this.render();
    const result = await call(id);
    this.busy = false;
    // Another module may have been picked while this one moved.
    if (result && id === this.moduleId) {
      this.flap = result.flap;
      this.offsets = result.offsets;
    }
    this.setStatus('');
    this.render();
  },

  setStatus(text) {
    byId('tunerStatus').textContent = text;
  },

  render() {
    // Like the inspector's other controls, only for a provisioned module.
    const usable = this.moduleId !== null && !!moduleSettings(this.moduleId);
    const known = this.flap !== null;
    // Flap 0 is where homing ends: the home offset places it.
    const editable = usable && known && this.flap !== 0;
    byId('flapTuner').classList.toggle('disabled', !usable);
    byId('tunerFlap').textContent = known ? this.flap : '—';
    byId('tunerChar').textContent = known ? flapLabel(CHAR_MAP[this.flap])
                                          : usable ? 'Step to a flap to start' : '';
    byId('tunerOffset').value = editable ? this.offsets[this.flap] : '';
    byId('tunerOffset').placeholder = known && !editable ? 'home offset' : '';
    byId('tunerOffset').disabled = this.busy || !editable;
    byId('flapTuner').querySelectorAll('.tuner-body button').forEach(button => {
      button.disabled = this.busy || !usable || (!editable && !button.dataset.step);
    });

    let summary = '';
    if (this.offsets) {
      const shifted = this.offsets.flatMap((offset, flap) =>
        offset ? [`${flap} ${flapLabel(CHAR_MAP[flap])} ${signed(offset)}`] : []);
      summary = shifted.length ? `Flaps with an offset: ${shifted.join(' · ')}` : 'No flap has an offset.';
    }
    byId('tunerSummary').textContent = summary;
  },
};

// An offset with its sign, e.g. +3, -2 or 0.
const signed = n => n > 0 ? `+${n}` : String(n);

registerActions({
  tunerStep: button => flapTuner.step(Number(button.dataset.step)),
  tunerNudge: button => flapTuner.apply(Number(button.dataset.delta)),
  tunerApply: () => flapTuner.apply(),
});
