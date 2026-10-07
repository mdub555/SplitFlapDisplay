// The Control page: compose a page of text, build a playlist of pages, and
// save, load or run playlists.

// What a page uses for anything it doesn't set itself.
const PAGE_DEFAULTS = {delay: 5, style: 'ltr', speed: 15};
const ADD_PAGE_LABEL = '+ Add to Playlist';

let editingIndex = null;   // the playlist page being edited, if any
let playlist = [];         // [{text, raw, centered, delay, style, speed}]
let lastFocusedInput = null;
let lastCursorPos = 0;

function lineInputIds() {
  return Array.from({length: GRID_ROWS}, (_, i) => `L${i}`);
}

function buildLineInputs() {
  const inputs = lineInputIds().map((id, i) => {
    const input = el('input', {type: 'text', id, class: 'line-input', placeholder: `LINE ${i + 1}`});
    input.addEventListener('input', updatePreview);
    // Remember where to insert a colour tile from the palette.
    ['focus', 'keyup', 'click'].forEach(ev => input.addEventListener(ev, e => {
      lastFocusedInput = e.target;
      lastCursorPos = e.target.selectionStart || 0;
    }));
    return input;
  });
  byId('lineInputs').replaceChildren(...inputs);
}

function buildColorPalette() {
  byId('colorPalette').replaceChildren(...CONFIG.color_tiles.map(tile => {
    const btn = el('button', {class: 'color-btn', title: tile.name}, tile.emoji);
    btn.addEventListener('click', () => insertColor(tile.emoji));
    return btn;
  }));
}

// Draws the composed page in the preview grid and returns it as one string
// of GRID_ROWS x GRID_COLS characters.
function updatePreview() {
  const centered = byId('centerToggle').checked;
  let full = '';
  lineInputIds().forEach(id => {
    const input = byId(id);
    let chars = Array.from(input.value);   // so a colour tile is one character
    if (chars.length > GRID_COLS) {
      const cursor = input.selectionStart;
      chars = chars.slice(0, GRID_COLS);
      input.value = chars.join('');
      input.setSelectionRange(cursor, cursor);
    }
    const cells = chars.map(c => c.toUpperCase());
    if (centered) cells.unshift(...Array(Math.floor((GRID_COLS - cells.length) / 2)).fill(' '));
    while (cells.length < GRID_COLS) cells.push(' ');
    full += cells.join('');
  });
  const grid = byId('preview');
  grid.style.gridTemplateColumns = `repeat(${GRID_COLS}, 1fr)`;
  grid.replaceChildren(...Array.from(full).map(ch => el('div', {class: 'flap-unit'}, ch === ' ' ? '' : ch)));
  return full;
}

function insertColor(emoji) {
  const target = lastFocusedInput || byId('L0');
  if (Array.from(target.value).length >= GRID_COLS) return;
  target.value = target.value.substring(0, lastCursorPos) + emoji + target.value.substring(lastCursorPos);
  lastCursorPos += emoji.length;
  target.focus();
  target.setSelectionRange(lastCursorPos, lastCursorPos);
  updatePreview();
}

function stopEditing() {
  editingIndex = null;
  byId('saveMsgBtn').textContent = ADD_PAGE_LABEL;
}

function clearDisplay() {
  lineInputIds().forEach(id => { byId(id).value = ''; });
  if (editingIndex !== null) stopEditing();
  updatePreview();
}

function toggleMultiMode() {
  byId('multiControls').hidden = !byId('modeToggle').checked;
}

// The delay, style and speed chosen under the playlist.
function defaultTiming() {
  return {
    delay: parseFloat(byId('delayInput').value) || PAGE_DEFAULTS.delay,
    style: byId('styleInput').value || PAGE_DEFAULTS.style,
    speed: parseInt(byId('speedInput').value, 10) || PAGE_DEFAULTS.speed,
  };
}

// A page as the backend takes it, with defaults for anything missing. A page
// saved by an older version can be a plain string.
function pageForDisplay(page) {
  if (typeof page !== 'object') return {text: page, ...PAGE_DEFAULTS};
  return {
    text: page.text,
    delay: page.delay || PAGE_DEFAULTS.delay,
    style: page.style || PAGE_DEFAULTS.style,
    speed: page.speed || PAGE_DEFAULTS.speed,
  };
}

// The pages to send or save: the playlist in multi-page mode, otherwise the
// page being composed.
function currentPages() {
  if (byId('modeToggle').checked) return playlist.map(pageForDisplay);
  return [{text: updatePreview(), ...defaultTiming()}];
}

// --- The playlist being built ----------------------------------------------

function saveMessage() {
  const raw = {};
  lineInputIds().forEach((id, i) => { raw[`raw${i}`] = byId(id).value; });
  const item = {text: updatePreview(), raw, centered: byId('centerToggle').checked, ...defaultTiming()};
  if (editingIndex !== null) {
    playlist[editingIndex] = item;
    stopEditing();
    clearDisplay();
  } else {
    playlist.push(item);
  }
  renderPlaylist();
}

// A small labelled control in a playlist row, bound to `field` of its page.
function pageControl(icon, control, field, unit) {
  control.dataset.onchange = 'updatePlaylistItemFromInput';
  control.dataset.field = field;
  return el('label', {class: 'inline-field inline-field-sm'}, `${icon} `, control, unit ? ` ${unit}` : '');
}

function buildPlaylistRow(item, idx) {
  const button = (text, action, cls = 'btn btn-secondary btn-sm', dir) =>
    el('button', {class: cls, dataset: {onclick: action, ...(dir !== undefined && {dir})}}, text);

  const header = el('div', {class: 'playlist-item-header'},
    el('span', {class: 'playlist-item-title'}, `Page ${idx + 1}`),
    el('div', {class: 'row row-tight'},
      button('▲', 'movePlaylist', undefined, -1),
      button('▼', 'movePlaylist', undefined, 1),
      button('EDIT', 'editPlaylist'),
      button('DEL', 'removeFromPlaylist', 'btn btn-danger btn-sm')));

  // One line per display row. Spaces become non-breaking so a run of them
  // keeps its width.
  const preview = el('div', {class: 'playlist-preview'});
  const chars = Array.from(item.text);
  for (let r = 0; r < GRID_ROWS; r++) {
    if (r) preview.appendChild(el('br'));
    preview.append(chars.slice(r * GRID_COLS, (r + 1) * GRID_COLS).join('').replace(/ /g, ' '));
  }

  const numberInput = (value, min, max, step) =>
    el('input', {type: 'number', class: 'input input-num input-sm', value, min, max, step});
  const styleSelect = el('select', {class: 'input input-sm'}, ...styleOptions(item.style || PAGE_DEFAULTS.style));
  const controls = el('div', {class: 'playlist-item-controls'},
    pageControl('⏱', numberInput(item.delay || PAGE_DEFAULTS.delay, '0.5', '60', '0.5'), 'delay', 's'),
    pageControl('↔', styleSelect, 'style'),
    pageControl('⚡', numberInput(item.speed || PAGE_DEFAULTS.speed, '0', '500', '5'), 'speed', 'ms'));

  return el('div', {class: 'playlist-item', dataset: {idx}}, header, preview, controls);
}

function renderPlaylist() {
  const list = byId('playlistList');
  if (!playlist.length) {
    list.replaceChildren(el('div', {class: 'empty-note'}, 'Queue is empty'));
    return;
  }
  list.replaceChildren(...playlist.map(buildPlaylistRow));
}

// The playlist index of the row that `control` is in.
const rowIndex = control => parseInt(control.closest('[data-idx]').dataset.idx, 10);

function updatePlaylistItemFromInput(control) {
  const item = playlist[rowIndex(control)];
  if (!item) return;
  const field = control.dataset.field;
  item[field] = field === 'style' ? control.value : (parseFloat(control.value) || 0);
}

function editPlaylist(button) {
  const idx = rowIndex(button);
  const item = playlist[idx];
  editingIndex = idx;
  lineInputIds().forEach((id, i) => { byId(id).value = (item.raw && item.raw[`raw${i}`]) || ''; });
  byId('centerToggle').checked = item.centered;
  byId('delayInput').value = item.delay || PAGE_DEFAULTS.delay;
  byId('styleInput').value = item.style || PAGE_DEFAULTS.style;
  byId('speedInput').value = item.speed || PAGE_DEFAULTS.speed;
  byId('saveMsgBtn').textContent = `Save Changes to Page ${idx + 1}`;
  updatePreview();
}

function movePlaylist(button) {
  const idx = rowIndex(button);
  const to = idx + parseInt(button.dataset.dir, 10);
  if (to < 0 || to >= playlist.length) return;
  [playlist[idx], playlist[to]] = [playlist[to], playlist[idx]];
  if (editingIndex === idx) editingIndex = to;
  else if (editingIndex === to) editingIndex = idx;
  renderPlaylist();
}

function removeFromPlaylist(button) {
  const idx = rowIndex(button);
  playlist.splice(idx, 1);
  if (editingIndex === idx) clearDisplay();
  else if (editingIndex > idx) editingIndex--;
  renderPlaylist();
}

function sync() {
  api.updatePlaylist(currentPages(), byId('delayInput').value).then(result => {
    if (result) showToast('Pushed to display');
  });
}

function stopApp() {
  api.stopApp().then(result => {
    if (result) showToast('App stopped');
  });
}

// --- Saved playlists -----------------------------------------------------

function loadSavedPlaylists() {
  api.playlists().then(data => renderSavedPlaylists(data || {}));
}

function buildSavedPlaylistRow(name, item) {
  // The name travels in data-name and is shown with textContent, so any
  // characters are safe.
  return el('div', {class: 'saved-pl-item', dataset: {name}},
    el('span', {class: 'saved-pl-name'}, name),
    el('span', {class: 'saved-pl-meta'}, `${item.pages.length}p·${item.delay}s`),
    el('button', {class: 'btn btn-secondary btn-sm', dataset: {onclick: 'loadSavedPlaylist'}}, 'Load'),
    el('button', {class: 'btn btn-success btn-sm', dataset: {onclick: 'runSavedPlaylist'}}, 'Run'),
    el('button', {class: 'btn btn-danger btn-sm', dataset: {onclick: 'deleteSavedPlaylist'}}, '✕'));
}

function renderSavedPlaylists(data) {
  const names = Object.keys(data || {});
  byId('savedPlaylistList').replaceChildren(...(names.length
    ? names.map(name => buildSavedPlaylistRow(name, data[name]))
    : [el('div', {class: 'empty-note'}, 'No saved playlists yet.')]));
}

function saveCurrentPlaylist() {
  const nameInput = byId('savePlaylistName');
  const name = nameInput.value.trim();
  if (!name) { showToast('Enter a name first', 'warn'); return; }
  api.savePlaylist(name, currentPages(), byId('delayInput').value).then(result => {
    if (!result) return;
    showToast(`Saved "${name}"`);
    nameInput.value = '';
    loadSavedPlaylists();
  });
}

// The saved playlist named on `button`'s row, fetched fresh, passed to `use`.
function withSavedPlaylist(button, use) {
  const name = button.closest('[data-name]').dataset.name;
  api.playlists().then(data => {
    const item = data && data[name];
    if (item) use(name, item);
  });
}

function loadSavedPlaylist(button) {
  withSavedPlaylist(button, (name, item) => {
    playlist = item.pages.map(page => {
      const shown = pageForDisplay(page);
      const raw = {};
      lineInputIds().forEach((id, i) => {
        raw[`raw${i}`] = shown.text.slice(i * GRID_COLS, (i + 1) * GRID_COLS).trim();
      });
      return {...shown, raw, centered: false};
    });
    byId('delayInput').value = item.delay;
    byId('modeToggle').checked = true;
    toggleMultiMode();
    renderPlaylist();
    showToast(`Loaded "${name}"`);
  });
}

function runSavedPlaylist(button) {
  withSavedPlaylist(button, (name, item) => {
    api.updatePlaylist(item.pages, item.delay).then(result => {
      if (result) showToast(`Running "${name}"`);
    });
  });
}

function deleteSavedPlaylist(button) {
  const name = button.closest('[data-name]').dataset.name;
  if (!confirm(`Delete playlist "${name}"?`)) return;
  api.deletePlaylist(name).then(result => {
    if (!result) return;
    showToast(`Deleted "${name}"`, 'warn');
    loadSavedPlaylists();
  });
}

function initControlPage() {
  buildLineInputs();
  buildColorPalette();
  byId('styleInput').replaceChildren(...styleOptions(PAGE_DEFAULTS.style));
  updatePreview();
  loadSavedPlaylists();
}

registerActions({
  clearDisplay, saveMessage, sync, saveCurrentPlaylist, stopApp,
  toggleMultiMode, updatePreview, updatePlaylistItemFromInput,
  movePlaylist, editPlaylist, removeFromPlaylist,
  loadSavedPlaylist, runSavedPlaylist, deleteSavedPlaylist,
});
