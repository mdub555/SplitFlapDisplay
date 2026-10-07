// The Tuning & Settings page: the hardware inspector for one module at a
// time, the firmware settings shared by every module, global settings, and
// backup/restore.

let selectedModule = 0;
let currentSettings = null;   // GET /settings, kept up to date as things change

function loadTuningData() {
  byId('modMatrix').replaceChildren(el('div', {class: 'loading-note'}, 'Loading…'));
  loadFirmwareConfig(); // independent of the settings load below, so one failing doesn't block the other
  Promise.all([api.getSettings(), api.globalFields()]).then(([settings, fields]) => {
    if (!settings || !fields) return; // error toast already shown by the api layer
    currentSettings = settings;
    byId('globalSettingsGrid').replaceChildren(...fields.map(f => buildField(f, settings[f.key], 'gsf_')));
    byId('autoHomeToggle').checked = settings.auto_home;
    selectModule(selectedModule);
  });
}

function saveGlobal() {
  api.globalFields().then(fields => {
    if (!fields) return;
    api.saveGlobalSettings(readFieldValues(fields, 'gsf_')).then(result => {
      if (result) showToast('Settings saved');
    });
  });
}

// --- The hardware inspector -----------------------------------------------

// The stored settings of module `id` (the selected one by default), or null
// if it isn't provisioned.
function moduleSettings(id = selectedModule) {
  return (currentSettings && currentSettings.modules && currentSettings.modules[id.toString()]) || null;
}

function renderModuleGrid() {
  const grid = byId('modMatrix');
  // Laid out like the display; phones get at most 8 columns (see tuning.css).
  grid.style.setProperty('--cols', GRID_COLS);
  grid.style.setProperty('--phone-cols', Math.min(GRID_COLS, 8));
  grid.replaceChildren(...Array.from({length: NUM_MODULES}, (_, i) => el('div', {
    class: `mod-cell${i === selectedModule ? ' active' : ''}${moduleSettings(i) ? '' : ' unprovisioned'}`,
    dataset: {onclick: 'selectModuleAction', id: i},
  }, formatModuleId(i))));
}

// A number from the module's stored settings for the stats row, or ---.
function statText(mod, key) {
  return mod && mod[key] !== undefined ? mod[key].toLocaleString('en-US') : '---';
}

function selectModule(id) {
  selectedModule = id;
  renderModuleGrid();
  byId('inspectorPanel').hidden = false;
  byId('inspectTitle').textContent = `MODULE ${formatModuleId(id)}`;
  const mod = moduleSettings();
  // Offset and steps are plain numbers to tune by; no thousands separator.
  byId('inspectOffset').textContent = mod && mod.homeOffset !== undefined ? mod.homeOffset : '---';
  byId('inspectCalib').textContent = mod && mod.totalSteps !== undefined ? mod.totalSteps : '---';
  byId('inspectRevolutions').textContent = statText(mod, 'revolutions');
  byId('inspectDrift').textContent = statText(mod, 'drift');
  refreshModuleTiming();
  refreshModuleToggles();
  refreshManualControls();
}

function selectModuleAction(cell) {
  selectModule(parseInt(cell.dataset.id, 10));
}

// The shared firmware settings as the selected module reported them in its
// last sync (the dump), so you can check that what was sent actually took.
// Values that differ from the saved shared settings are highlighted.
function refreshModuleTiming() {
  const box = byId('inspectTiming');
  const mod = moduleSettings();
  if (!mod) { box.replaceChildren(); return; }
  // A module last synced by older firmware is missing some of the fields.
  if (CONFIG.timing_fields.some(f => mod[f.key] === undefined)) {
    box.textContent = 'Sync this module to read its timing settings.';
    return;
  }
  const shared = currentSettings.firmware || {};
  const parts = [];
  let mismatches = 0;
  CONFIG.timing_fields.forEach(({key, name, unit}, i) => {
    const differs = shared[key] !== undefined && shared[key] !== mod[key];
    if (differs) mismatches++;
    if (i) parts.push(' · ');
    parts.push(el('span', {
      dataset: {key},
      class: differs ? 'mismatch' : '',
      title: differs ? `Shared setting is ${shared[key]} ${unit}` : '',
    }, `${name} ${mod[key]} ${unit}`));
  });
  box.replaceChildren('From last sync: ', ...parts,
    mismatches ? ' — highlighted values differ from the shared settings; Apply to All Modules resends them.' : '');
}

// The per-module on/off settings, one checkbox per setting (data-setting).
const moduleToggleInputs = () => byId('moduleToggles').querySelectorAll('[data-setting]');

// Redraws the toggles from stored settings for the selected module. Also the
// way a failed save gets undone: redraw from what we actually know.
function refreshModuleToggles() {
  const mod = moduleSettings();
  byId('moduleToggles').classList.toggle('disabled', !mod);
  moduleToggleInputs().forEach(input => {
    input.checked = !!(mod && mod[input.dataset.setting]);
    input.disabled = !mod; // an unprovisioned module has nothing to configure
  });
}

function toggleModuleSetting(input) {
  const key = input.dataset.setting;
  const enabled = input.checked;
  const modId = selectedModule; // the user may pick another module before the reply arrives
  // Flipping the direction makes every move run backwards until it's flipped
  // back, so make it deliberate. Nothing has been sent yet, so backing out
  // only has to restore the checkbox.
  if (key === 'motorClockwise' &&
      !confirm(`Make module ${formatModuleId(modId)} turn ${enabled ? 'clockwise' : 'counter-clockwise'}? ` +
               `Only do this if the reel is turning the wrong way. Re-home the module afterwards.`)) {
    input.checked = !enabled;
    return;
  }
  input.disabled = true;           // no overlapping toggles while a command is in flight
  api.setModuleSetting(modId, key, enabled).then(result => {
    if (result) storeModuleValue(modId, key, enabled);
    // On failure the api layer already showed a toast; either way redrawing
    // from stored state re-enables the toggle and reverts a failed change.
    refreshModuleToggles();
  });
}

// Manual controls under the toggles: set total steps, show a character or
// flap index, jump to a raw step. Disabled for an unprovisioned module, like
// the toggles (the backend answers those with a 404 anyway).
const MAX_TOTAL_STEPS = 32767;

function refreshManualControls() {
  const mod = moduleSettings();
  const box = byId('manualControls');
  box.classList.toggle('disabled', !mod);
  box.querySelectorAll('input, button').forEach(control => { control.disabled = !mod; });
  byId('totalStepsInput').value = mod && mod.totalSteps !== undefined ? mod.totalSteps : '';
}

// Whole number from a number input, or null (after a warning toast) if it's
// blank, fractional or outside [min, max].
function readIntInput(id, label, min, max) {
  const raw = byId(id).value.trim();
  const n = Number(raw);
  if (raw === '' || !Number.isInteger(n) || n < min || n > max) {
    showToast(`${label} must be a whole number from ${min} to ${max}`, 'warn');
    return null;
  }
  return n;
}

// Sets `key` in module `id`'s stored settings, if we have them.
function storeModuleValue(id, key, value) {
  const mod = moduleSettings(id);
  if (mod) mod[key] = value;
}

// Sends one command to the selected module with `call(modId)`, and on
// success shows `message(modId, result)` and runs `onSuccess`, if given.
function moduleCommand(call, message, onSuccess) {
  const modId = selectedModule; // the user may pick another module before the reply arrives
  return call(modId).then(result => {
    if (!result) return;
    if (onSuccess) onSuccess(modId, result);
    if (message) showToast(message(modId, result));
  });
}

const moduleName = id => `Module ${formatModuleId(id)}`;

function setTotalSteps() {
  const steps = readIntInput('totalStepsInput', 'Total steps', 1, MAX_TOTAL_STEPS);
  if (steps === null) return;
  moduleCommand(id => api.setTotalSteps(id, steps),
    id => `${moduleName(id)}: total steps set to ${steps}`,
    id => {
      storeModuleValue(id, 'totalSteps', steps);
      if (id === selectedModule) byId('inspectCalib').textContent = steps;
    });
}

function showOnModule(payload) {
  moduleCommand(id => api.showOnModule(id, payload), (id, d) => `${moduleName(id)} showing flap ${d.index}`);
}

function showChar() {
  // Array.from so a colour-tile emoji counts as one character, not two.
  const chars = Array.from(byId('showCharInput').value);
  if (chars.length !== 1) { showToast('Enter exactly one character', 'warn'); return; }
  showOnModule({char: chars[0]});
}

function showIndex() {
  const index = readIntInput('showIndexInput', 'Flap index', 0, CHAR_MAP.length - 1);
  if (index !== null) showOnModule({index});
}

function gotoStep() {
  const mod = moduleSettings();
  const total = mod && Number.isInteger(mod.totalSteps) ? mod.totalSteps : MAX_TOTAL_STEPS + 1;
  const step = readIntInput('gotoStepInput', 'Step', 0, total - 1);
  if (step === null) return;
  moduleCommand(id => api.gotoStep(id, step), id => `${moduleName(id)} moved to step ${step}`);
}

function exerciseSelected() {
  const cycles = readIntInput('exerciseInput', 'Exercise cycles', 1, 255);
  if (cycles === null) return;
  moduleCommand(id => api.exerciseModule(id, cycles),
    id => `${moduleName(id)}: exercising ${cycles} cycle${cycles === 1 ? '' : 's'}`);
}

function stopSelected() {
  moduleCommand(api.stopModule, id => `${moduleName(id)} stopped`);
}

function adjustOffset(button) {
  const delta = parseInt(button.dataset.delta, 10);
  moduleCommand(id => api.adjustOffset(id, delta), null, (id, d) => {
    storeModuleValue(id, 'homeOffset', d.new_offset);
    if (id === selectedModule) byId('inspectOffset').textContent = d.new_offset;
  });
}

function homeSelected() {
  moduleCommand(api.homeModule, id => `Homing module ${formatModuleId(id)}`);
}

function identifySelected() {
  moduleCommand(api.identifyModule, id => `${moduleName(id)}: status LED blinking for 10 s`);
}

function rebootSelected() {
  if (!confirm(`Reboot module ${formatModuleId(selectedModule)}?`)) return;
  moduleCommand(api.rebootModule, id => `${moduleName(id)} rebooting`);
}

// Replaces the stored settings with what a sync or reset returned.
function useSettings(id, result) {
  currentSettings = result.settings;
  selectModule(selectedModule);
}

function resetSettingsSelected() {
  if (!confirm(`Reset every setting on module ${formatModuleId(selectedModule)} to its firmware default? ` +
               `Its ID is kept, but its home offset and total steps are lost.`)) return;
  showToast('Resetting…', 'warn');
  moduleCommand(api.resetModuleSettings, id => `${moduleName(id)} reset to defaults`, useSettings);
}

function homeAll() {
  if (!confirm(`Re-home all ${NUM_MODULES} modules via broadcast?`)) return;
  api.homeAll().then(result => {
    if (result) showToast('Homing all modules', 'warn');
  });
}

// Shows `busyText` in the stat `statId` until `request` settles, then puts
// back what was there if it failed.
function withBusyStat(statId, busyText, request) {
  const stat = byId(statId);
  const before = stat.textContent;
  stat.textContent = busyText;
  return request.then(result => {
    if (!result) stat.textContent = before;
    return result;
  });
}

function calibrateSelected() {
  if (!confirm(`Calibrate Module ${formatModuleId(selectedModule)}? It will spin 360° to measure steps.`)) return;
  moduleCommand(id => withBusyStat('inspectCalib', 'Measuring…', api.calibrateModule(id)),
    (id, d) => `${moduleName(id)}: ${d.steps} steps`,
    (id, d) => {
      storeModuleValue(id, 'totalSteps', d.steps);
      if (id === selectedModule) {
        byId('inspectCalib').textContent = d.steps;
        refreshManualControls();
      }
    });
}

function syncOneFromHardware() {
  moduleCommand(id => withBusyStat('inspectOffset', 'Syncing…', api.syncModule(id)), () => 'Synced', useSettings);
}

function syncAllFromHardware() {
  if (!confirm(`Poll all ${NUM_MODULES} modules to rebuild settings.json?`)) return;
  document.body.style.cursor = 'wait';
  api.syncAllModules().then(result => {
    document.body.style.cursor = '';
    if (!result) return;
    useSettings(null, result);
    showToast('All modules synced');
  });
}

function provisionModule() {
  const targetId = selectedModule; // provision as the selected module
  if (!confirm(`Assign ID ${formatModuleId(targetId)} to the unprovisioned module on the bus?`)) return;
  showToast('Provisioning…', 'warn');
  api.provisionModule(targetId).then(result => {
    if (!result) return;
    showToast(`Module assigned ID ${formatModuleId(result.assigned_id)}`);
    loadTuningData();
  });
}

// --- Global settings ------------------------------------------------------

function toggleAutoHome(input) {
  const enabled = input.checked;
  api.toggleAutoHome(enabled).then(result => {
    if (!result) { input.checked = !enabled; return; }
    // The backend applies this to every provisioned module; mirror that here
    // so the inspector's per-module auto-home toggle doesn't go stale.
    if (currentSettings) {
      currentSettings.auto_home = enabled;
      Object.values(currentSettings.modules || {}).forEach(mod => { mod.autoHome = enabled; });
      refreshModuleToggles();
    }
  });
}

// Firmware settings shared by every module (step delays, debounce, recalculate
// home). The inputs are rendered from the backend's definitions (fw-<key>);
// the values and their ranges come from GET /firmware_config.
let firmwareLimits = null;

function loadFirmwareConfig() {
  api.firmwareConfig().then(cfg => {
    if (!cfg) return; // error toast already shown by the api layer
    firmwareLimits = cfg.limits;
    Object.entries(cfg.limits).forEach(([key, lim]) => {
      const input = byId(`fw-${key}`);
      if (lim.type === 'bool') {
        input.checked = !!cfg.values[key];
      } else {
        input.min = lim.min;
        input.max = lim.max;
        input.value = cfg.values[key];
      }
    });
  });
}

function applyFirmwareConfig() {
  if (!firmwareLimits) { showToast('Firmware settings have not loaded yet', 'warn'); return; }
  const payload = {};
  for (const [key, lim] of Object.entries(firmwareLimits)) {
    const input = byId(`fw-${key}`);
    if (lim.type === 'bool') { payload[key] = input.checked; continue; }
    const n = readIntInput(`fw-${key}`, input.dataset.label, lim.min, lim.max);
    if (n === null) return; // nothing is sent unless every value is valid
    payload[key] = n;
  }
  api.saveFirmwareConfig(payload).then(result => {
    if (result) showToast('Settings sent to all modules');
  });
}

// --- Backup and restore ---------------------------------------------------

function downloadBackup() {
  api.backupSettings().then(data => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
    el('a', {href: URL.createObjectURL(blob),
             download: `splitflap_backup_${new Date().toISOString().slice(0, 10)}.json`}).click();
    showToast('Backup downloaded');
  });
}

function triggerBackupFileInput() {
  byId('backupFile').click();
}

function uploadBackup(input) {
  const file = input.files[0];
  input.value = '';   // so choosing the same file again still triggers a change
  if (!file) return;
  const status = byId('restoreStatus');
  file.text().then(text => {
    let data;
    try {
      data = JSON.parse(text);
    } catch (err) {
      showToast('Invalid JSON file', 'error');
      return;
    }
    if (!confirm('Restore calibration data and push to all modules?')) return;
    status.textContent = 'Restoring…';
    api.restoreSettings(data).then(result => {
      status.textContent = result ? '✓ Done' : '✗ Error';
      if (!result) return;
      showToast('Restore complete');
      loadTuningData();
    });
  });
}

registerActions({
  selectModuleAction, adjustOffset, homeSelected, homeAll, calibrateSelected, identifySelected,
  rebootSelected, resetSettingsSelected, exerciseSelected, stopSelected,
  syncOneFromHardware, syncAllFromHardware, toggleAutoHome, provisionModule,
  setTotalSteps, showChar, showIndex, gotoStep,
  applyFirmwareConfig,
  toggleModuleSetting,
  saveGlobal, downloadBackup, triggerBackupFileInput, uploadBackup,
});
