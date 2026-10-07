// The Control page: compose a page of text, build a playlist of pages, and
// save, load or run playlists.

// What a page uses for anything it doesn't set itself.
const PAGE_DEFAULTS = {delay: 5, style: 'ltr', speed: 15};
const ADD_PAGE_LABEL = '+ Add to Playlist';

let editingIndex = null;   // the playlist page being edited, if any
let playlist = [];         // [{text, delay, style, speed}]

// --- Composing a page: typing straight into the grid -------------------------
//
// The page is one character per flap, row after row, as it's shown (letters
// uppercased, colours as their emoji). Typing overwrites the flap under the
// cursor and moves on, like the display itself. Keys arrive through a hidden
// textarea, which also brings up a phone's keyboard; it always holds just
// COMPOSE_SENTINEL, so even a phone keyboard's Backspace (which sends no
// usable key code) shows up as the sentinel being deleted.

const COMPOSE_SENTINEL = '_';
const composeCells = () => GRID_ROWS * GRID_COLS;
let composed = [];         // one character per flap
let composeCursor = 0;     // 0..composeCells(); composeCells() is past the end
let composeFlaps = [];     // the grid's cell elements
let composing = false;     // in the middle of an IME composition

// Every character a flap shows, as it's shown on screen.
const COMPOSE_CHARS = new Set(Array.from(CHAR_MAP, ch => displayChar(ch) || ' '));

// Characters phone keyboards type in place of one a flap shows.
const COMPOSE_SUBSTITUTES = {'\u201c': '"', '\u201d': '"', '\u201e': '"', '\u2764': '\u2665'};

// `ch` as it goes in a flap, or null if no flap shows it.
function composeChar(ch) {
  ch = COMPOSE_SUBSTITUTES[ch] || ch;
  const upper = ch.toUpperCase();
  return COMPOSE_CHARS.has(upper) ? upper : COMPOSE_CHARS.has(ch) ? ch : null;
}

function buildComposer() {
  composed = Array(composeCells()).fill(' ');
  const grid = byId('preview');
  grid.style.gridTemplateColumns = `repeat(${GRID_COLS}, 1fr)`;
  composeFlaps = composed.map((_, i) => el('div', {class: 'flap-unit', dataset: {cell: i}}));
  grid.replaceChildren(...composeFlaps);

  const input = byId('composeInput');
  const wrapper = byId('composeWrapper');
  // A click on a flap puts the cursor there; anywhere else in the grid keeps it.
  wrapper.addEventListener('mousedown', e => e.preventDefault());   // keep focus in the textarea
  wrapper.addEventListener('click', e => {
    const cell = e.target.closest('[data-cell]');
    if (cell) moveComposeCursor(Number(cell.dataset.cell));
    focusComposer();
  });
  input.addEventListener('focus', () => wrapper.classList.add('focused'));
  input.addEventListener('blur', () => wrapper.classList.remove('focused'));
  input.addEventListener('keydown', composeKeydown);
  input.addEventListener('compositionstart', () => { composing = true; });
  input.addEventListener('compositionend', () => { composing = false; composeTextareaInput(); });
  input.addEventListener('input', () => { if (!composing) composeTextareaInput(); });
  input.addEventListener('paste', e => {
    e.preventDefault();
    typeText(e.clipboardData.getData('text'));
  });
  resetComposeTextarea();
  renderComposer();
}

function focusComposer() {
  const input = byId('composeInput');
  if (document.activeElement !== input) input.focus({preventScroll: true});
}

function resetComposeTextarea() {
  const input = byId('composeInput');
  input.value = COMPOSE_SENTINEL;
  input.setSelectionRange(COMPOSE_SENTINEL.length, COMPOSE_SENTINEL.length);
}

// Whatever the textarea gained or lost since it was reset.
function composeTextareaInput() {
  const value = byId('composeInput').value;
  if (value.startsWith(COMPOSE_SENTINEL)) typeText(value.slice(COMPOSE_SENTINEL.length));
  else composeBackspace();   // the sentinel was deleted
  resetComposeTextarea();
}

function composeKeydown(e) {
  if (e.ctrlKey || e.metaKey || e.altKey || composing) return;
  const row = Math.floor(composeCursor / GRID_COLS);
  const actions = {
    ArrowLeft: () => moveComposeCursor(composeCursor - 1),
    ArrowRight: () => moveComposeCursor(composeCursor + 1),
    ArrowUp: () => moveComposeCursor(composeCursor - GRID_COLS),
    ArrowDown: () => moveComposeCursor(composeCursor + GRID_COLS),
    Home: () => moveComposeCursor(row * GRID_COLS),
    End: () => moveComposeCursor(lineEnd(row)),
    Enter: () => moveComposeCursor((row + 1) * GRID_COLS),
    Backspace: composeBackspace,
    Delete: () => setComposeCell(composeCursor, ' '),
    Escape: () => byId('composeInput').blur(),
  };
  if (!actions[e.key]) return;
  e.preventDefault();
  actions[e.key]();
}

// The cell after the last non-blank one in `row`.
function lineEnd(row) {
  const start = row * GRID_COLS;
  let end = start + GRID_COLS;
  while (end > start && composed[end - 1] === ' ') end--;
  return Math.min(end, start + GRID_COLS - 1);
}

function moveComposeCursor(to) {
  // Up from the first row or down from the last stays put.
  if (to < 0 || to > composeCells()) return;
  composeCursor = to;
  renderComposer();
}

function setComposeCell(i, ch) {
  if (i < 0 || i >= composeCells()) return;
  composed[i] = ch;
  renderComposer();
}

// Types `text` at the cursor: each character overwrites a flap and moves on,
// a newline moves to the start of the next line, and characters no flap shows
// are skipped.
function typeText(text) {
  for (const ch of Array.from(text.replace(/\r\n?/g, '\n'))) {
    if (ch === '\n') {
      composeCursor = Math.min(composeCells(), (Math.floor(composeCursor / GRID_COLS) + 1) * GRID_COLS);
      continue;
    }
    const flap = composeChar(ch);
    if (flap === null || composeCursor >= composeCells()) continue;
    composed[composeCursor++] = flap;
  }
  renderComposer();
}

function composeBackspace() {
  if (composeCursor === 0) return;
  composed[--composeCursor] = ' ';
  renderComposer();
}

function renderComposer() {
  composeFlaps.forEach((flap, i) => {
    flap.textContent = composed[i] === ' ' ? '' : composed[i];
    flap.classList.toggle('cursor', i === Math.min(composeCursor, composeCells() - 1));
  });
}

// The composed page as one string of GRID_ROWS x GRID_COLS characters.
function composedText() {
  return composed.join('');
}

// Puts `text` (a page as stored: possibly with flap codes) in the grid.
function setComposedText(text) {
  const chars = Array.from(text || '');
  composed = Array.from({length: composeCells()}, (_, i) => {
    const ch = chars[i] || ' ';
    return CONFIG.display_chars[ch] || ch.toUpperCase();
  });
  composeCursor = 0;
  renderComposer();
}

// Centers each line's text within its row.
function centerLines() {
  for (let row = 0; row < GRID_ROWS; row++) {
    const start = row * GRID_COLS;
    const line = composed.slice(start, start + GRID_COLS);
    const first = line.findIndex(ch => ch !== ' ');
    if (first < 0) continue;
    const text = line.slice(first, GRID_COLS - [...line].reverse().findIndex(ch => ch !== ' '));
    const pad = Math.floor((GRID_COLS - text.length) / 2);
    line.fill(' ').splice(pad, text.length, ...text);
    composed.splice(start, GRID_COLS, ...line);
  }
  renderComposer();
}

// The colour tiles, then the symbol flaps no keyboard has (° and ♥). Each
// goes in at the cursor.
function buildColorPalette() {
  const tileButton = (text, name, cls) => {
    const btn = el('button', {class: cls, title: name}, text);
    btn.addEventListener('mousedown', e => e.preventDefault());   // keep the grid focused
    btn.addEventListener('click', () => { typeText(text); focusComposer(); });
    return btn;
  };
  byId('colorPalette').replaceChildren(
    ...CONFIG.color_tiles.map(tile => tileButton(tile.emoji, tile.name, 'color-btn')),
    el('span', {class: 'palette-divider'}),
    ...CONFIG.symbol_tiles.map(tile => tileButton(tile.char, tile.name, 'color-btn symbol-btn')));
}

function stopEditing() {
  editingIndex = null;
  byId('saveMsgBtn').textContent = ADD_PAGE_LABEL;
}

function clearDisplay() {
  setComposedText('');
  if (editingIndex !== null) stopEditing();
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
  return [{text: composedText(), ...defaultTiming()}];
}

// --- The playlist being built ----------------------------------------------

function saveMessage() {
  const item = {text: composedText(), ...defaultTiming()};
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
  setComposedText(item.text);
  byId('delayInput').value = item.delay || PAGE_DEFAULTS.delay;
  byId('styleInput').value = item.style || PAGE_DEFAULTS.style;
  byId('speedInput').value = item.speed || PAGE_DEFAULTS.speed;
  byId('saveMsgBtn').textContent = `Save Changes to Page ${idx + 1}`;
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
    playlist = item.pages.map(pageForDisplay);
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
  buildComposer();
  buildColorPalette();
  byId('styleInput').replaceChildren(...styleOptions(PAGE_DEFAULTS.style));
  loadSavedPlaylists();
}

registerActions({
  clearDisplay, saveMessage, sync, saveCurrentPlaylist, stopApp,
  toggleMultiMode, centerLines, updatePlaylistItemFromInput,
  movePlaylist, editPlaylist, removeFromPlaylist,
  loadSavedPlaylist, runSavedPlaylist, deleteSavedPlaylist,
});
