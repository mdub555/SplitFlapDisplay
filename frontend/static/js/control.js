// The Control page: compose a page of text, build a playlist of pages, and
// save, load or run playlists.

// What a page uses for anything it doesn't set itself.
const PAGE_DEFAULTS = {delay: 5, style: 'ltr', speed: 15};
const ADD_PAGE_LABEL = '+ Add to Playlist';

let editingIndex = null;   // the playlist page being edited, if any
let playlist = [];         // [{text, delay, style, speed}]
let loadedPlaylist = null; // the saved playlist being edited, if any (its name)
let savedPlaylists = {};   // GET /playlists, as last shown

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
  saveDraft();
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

function startEditing(idx) {
  editingIndex = idx;
  byId('saveMsgBtn').textContent = `Save Changes to Page ${idx + 1}`;
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
  saveDraft();
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
  const button = (text, action, title, cls = 'btn btn-secondary btn-sm', dir) =>
    el('button', {class: cls, title, dataset: {onclick: action, ...(dir !== undefined && {dir})}}, text);

  const header = el('div', {class: 'playlist-item-header'},
    el('span', {class: 'drag-handle', title: 'Drag to reorder'}, '⠿'),
    el('span', {class: 'playlist-item-title'}, `Page ${idx + 1}`),
    el('div', {class: 'row row-tight'},
      button('▲', 'movePlaylist', 'Move up', undefined, -1),
      button('▼', 'movePlaylist', 'Move down', undefined, 1),
      button('▶', 'pushPlaylistPage', 'Show just this page now'),
      button('⧉', 'duplicatePlaylistPage', 'Duplicate'),
      button('EDIT', 'editPlaylist', 'Edit in the grid'),
      button('DEL', 'removeFromPlaylist', 'Remove', 'btn btn-danger btn-sm')));

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
  list.replaceChildren(...(playlist.length
    ? playlist.map(buildPlaylistRow)
    : [el('div', {class: 'empty-note'}, 'Queue is empty')]));
  saveDraft();
}

// The playlist index of the row that `control` is in.
const rowIndex = control => parseInt(control.closest('[data-idx]').dataset.idx, 10);

// A page's delay, style or speed changed in its row. A number outside the
// input's range (or not a number) is refused and put back.
function updatePlaylistItemFromInput(control) {
  const item = playlist[rowIndex(control)];
  if (!item) return;
  const field = control.dataset.field;
  if (field === 'style') {
    item.style = control.value;
  } else {
    const n = Number(control.value);
    const min = Number(control.min), max = Number(control.max);
    const whole = field === 'speed';
    if (control.value.trim() === '' || !Number.isFinite(n) || n < min || n > max || (whole && !Number.isInteger(n))) {
      showToast(`${field === 'delay' ? 'Delay' : 'Speed'} must be ${whole ? 'a whole number ' : ''}from ${min} to ${max}`, 'warn');
      control.value = item[field];
      return;
    }
    item[field] = n;
  }
  saveDraft();
}

function editPlaylist(button) {
  const idx = rowIndex(button);
  const item = playlist[idx];
  startEditing(idx);
  setComposedText(item.text);
  byId('delayInput').value = item.delay || PAGE_DEFAULTS.delay;
  byId('styleInput').value = item.style || PAGE_DEFAULTS.style;
  byId('speedInput').value = item.speed || PAGE_DEFAULTS.speed;
  saveDraft();
}

// Changes the playlist with `change(playlist)`, keeping the page being
// edited (if it's still there) as the one being edited, wherever it ends up.
function changePlaylist(change) {
  const editing = editingIndex !== null ? playlist[editingIndex] : null;
  change(playlist);
  const at = editing ? playlist.indexOf(editing) : -1;
  if (at >= 0) startEditing(at);
  else if (editing) clearDisplay();   // its page was removed
  renderPlaylist();
}

function movePage(from, to) {
  if (from === to || to < 0 || to >= playlist.length) return;
  changePlaylist(pages => pages.splice(to, 0, ...pages.splice(from, 1)));
}

function movePlaylist(button) {
  const idx = rowIndex(button);
  movePage(idx, idx + parseInt(button.dataset.dir, 10));
}

function removeFromPlaylist(button) {
  const idx = rowIndex(button);
  changePlaylist(pages => pages.splice(idx, 1));
}

function duplicatePlaylistPage(button) {
  const idx = rowIndex(button);
  changePlaylist(pages => pages.splice(idx + 1, 0, {...pages[idx]}));
}

// Shows one page of the playlist on the display now, on its own.
function pushPlaylistPage(button) {
  const page = pageForDisplay(playlist[rowIndex(button)]);
  api.updatePlaylist([page], page.delay).then(result => {
    if (result) showToast(`Showing page ${rowIndex(button) + 1}`);
  });
}

// Dragging a page by its handle. Pointer events, so it works with a finger
// as well as a mouse: the row follows the pointer through the list, and
// the new order is kept when it's let go.
function startPageDrag(e) {
  const handle = e.target.closest('.drag-handle');
  if (!handle || e.button > 0) return;
  e.preventDefault();
  const list = byId('playlistList');
  const row = handle.closest('.playlist-item');
  const from = rowIndex(row);
  row.classList.add('dragging');

  const move = ev => {
    // Before the first other row whose middle is below the pointer.
    const before = [...list.querySelectorAll('.playlist-item:not(.dragging)')].find(other => {
      const box = other.getBoundingClientRect();
      return ev.clientY < box.top + box.height / 2;
    });
    if (before) {
      if (row.nextElementSibling !== before) list.insertBefore(row, before);
    } else if (list.lastElementChild !== row) {
      list.append(row);
    }
    // Near the top or bottom of the screen, scroll so a long list can be crossed.
    if (ev.clientY < 40) window.scrollBy(0, -12);
    else if (ev.clientY > window.innerHeight - 40) window.scrollBy(0, 12);
  };
  const end = () => {
    document.removeEventListener('pointermove', move);
    document.removeEventListener('pointerup', end);
    document.removeEventListener('pointercancel', end);
    row.classList.remove('dragging');
    const to = [...list.querySelectorAll('.playlist-item')].indexOf(row);
    if (to === from) renderPlaylist();
    else movePage(from, to);
  };
  document.addEventListener('pointermove', move);
  document.addEventListener('pointerup', end);
  document.addEventListener('pointercancel', end);
}

function sync() {
  const pages = currentPages();
  api.updatePlaylist(pages, defaultTiming().delay).then(result => {
    if (result) showToast('Pushed to display');
  });
}

// Stops whatever's running: an app or a playlist.
function stopApp() {
  api.stopApp().then(result => {
    if (result) showToast('Stopped');
  });
}

// --- Saved playlists -----------------------------------------------------

// Redraws the saved playlists; resolves to them, or null if they didn't load.
function loadSavedPlaylists() {
  return api.playlists().then(data => {
    renderSavedPlaylists(data || {});
    return data;
  });
}

function buildSavedPlaylistRow(name, item) {
  // The name travels in data-name and is shown with textContent, so any
  // characters are safe.
  return el('div', {class: `saved-pl-item${name === loadedPlaylist ? ' loaded' : ''}`, dataset: {name}},
    el('span', {class: 'saved-pl-name'}, name),
    el('span', {class: 'saved-pl-meta'}, playlistSummary(item)),
    el('button', {class: 'btn btn-secondary btn-sm', dataset: {onclick: 'loadSavedPlaylist'}}, 'Edit'),
    el('button', {class: 'btn btn-success btn-sm', dataset: {onclick: 'runSavedPlaylist'}}, 'Run'),
    el('button', {class: 'btn btn-danger btn-sm', dataset: {onclick: 'deleteSavedPlaylist'}}, '✕'));
}

// "3 pages · 5 s each", or "3 pages · 2–8 s" when the pages differ.
function playlistSummary(item) {
  const n = item.pages.length;
  const count = `${n} page${n === 1 ? '' : 's'}`;
  if (!n) return count;
  const delays = item.pages.map(page => Number((page && page.delay) || item.delay) || PAGE_DEFAULTS.delay);
  const low = Math.min(...delays), high = Math.max(...delays);
  if (low !== high) return `${count} · ${low}–${high} s`;
  return `${count} · ${low} s${n > 1 ? ' each' : ''}`;
}

function renderSavedPlaylists(data) {
  savedPlaylists = data || {};
  const names = Object.keys(savedPlaylists);
  byId('savedPlaylistList').replaceChildren(...(names.length
    ? names.map(name => buildSavedPlaylistRow(name, savedPlaylists[name]))
    : [el('div', {class: 'empty-note'}, 'No saved playlists yet.')]));
  markRunning();
}

// Which saved playlist the editor holds, shown above the list.
function setLoadedPlaylist(name) {
  loadedPlaylist = name;
  const note = byId('loadedPlaylistNote');
  note.hidden = !name;
  note.textContent = name ? `Editing "${name}". Save keeps the changes under that name; ` +
                            'type a new name to save a copy instead.' : '';
  document.querySelectorAll('.saved-pl-item').forEach(row => {
    row.classList.toggle('loaded', row.dataset.name === name);
  });
  saveDraft();
}

function saveCurrentPlaylist() {
  const name = byId('savePlaylistName').value.trim();
  if (!name) { showToast('Enter a name first', 'warn'); return; }
  // Fetched fresh, so a playlist saved from another device counts too.
  api.playlists().then(saved => {
    if (!saved) return;
    const replacing = name in saved;
    // Saving over the playlist being edited is the point; over another one,
    // check first.
    if (replacing && name !== loadedPlaylist && !confirm(`Replace the saved playlist "${name}"?`)) return;
    api.savePlaylist(name, currentPages(), defaultTiming().delay).then(result => {
      if (!result) return;
      showToast(replacing ? `Updated "${name}"` : `Saved "${name}"`);
      byId('savePlaylistName').value = name;
      setLoadedPlaylist(name);
      loadSavedPlaylists();
    });
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
    if (editingIndex !== null) stopEditing();
    playlist = item.pages.map(pageForDisplay);
    byId('delayInput').value = item.delay;
    byId('modeToggle').checked = true;
    byId('savePlaylistName').value = name;
    toggleMultiMode();
    renderPlaylist();
    setLoadedPlaylist(name);
    showToast(`Loaded "${name}"`);
  });
}

function runSavedPlaylist(button) {
  const name = button.closest('[data-name]').dataset.name;
  api.runPlaylist(name).then(result => {
    if (result) showToast(`Running "${name}"`);
  });
}

function deleteSavedPlaylist(button) {
  const name = button.closest('[data-name]').dataset.name;
  if (!confirm(`Delete playlist "${name}"?`)) return;
  api.deletePlaylist(name).then(result => {
    if (!result) return;
    showToast(`Deleted "${name}"`, 'warn');
    if (name === loadedPlaylist) setLoadedPlaylist(null);
    loadSavedPlaylists();
  });
}

// --- The draft: what's on this page survives a reload --------------------
//
// Kept in this browser's localStorage, so a refresh, or a phone dropping the
// tab, doesn't lose a playlist that's still being built. It's a convenience
// only: storage can be missing or full, and the page works without it.

const DRAFT_KEY = 'splitflap.controlDraft';
let draftReady = false;   // nothing is saved until the stored draft is restored

function saveDraft() {
  if (!draftReady) return;
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({
      text: composedText(),
      playlist,
      multi: byId('modeToggle').checked,
      editing: editingIndex,
      loaded: loadedPlaylist,
      name: byId('savePlaylistName').value,
      delay: byId('delayInput').value,
      style: byId('styleInput').value,
      speed: byId('speedInput').value,
    }));
  } catch (err) {
    // No storage (a private window, say): the draft just isn't kept.
  }
}

function restoreDraft() {
  let draft = null;
  try {
    draft = JSON.parse(localStorage.getItem(DRAFT_KEY));
  } catch (err) {
    // Nothing stored, or nothing readable: start empty.
  }
  if (draft && typeof draft === 'object') {
    if (typeof draft.text === 'string') setComposedText(draft.text);
    if (Array.isArray(draft.playlist)) {
      playlist = draft.playlist
        .filter(page => typeof page === 'string' || (page && typeof page.text === 'string'))
        .map(pageForDisplay);
    }
    byId('modeToggle').checked = !!draft.multi;
    for (const key of ['delay', 'style', 'speed']) {
      const input = byId(`${key}Input`);
      // A style that no longer exists would leave the select blank.
      if (typeof draft[key] === 'string' && draft[key] &&
          (input.tagName !== 'SELECT' || CONFIG.styles.some(st => st.value === draft[key]))) {
        input.value = draft[key];
      }
    }
    if (typeof draft.name === 'string') byId('savePlaylistName').value = draft.name;
    if (Number.isInteger(draft.editing) && draft.editing >= 0 && draft.editing < playlist.length) {
      startEditing(draft.editing);
    }
    if (typeof draft.loaded === 'string') setLoadedPlaylist(draft.loaded);
  }
  draftReady = true;
  toggleMultiMode();
  renderPlaylist();
}

function initControlPage() {
  buildComposer();
  buildColorPalette();
  byId('styleInput').replaceChildren(...styleOptions(PAGE_DEFAULTS.style));
  restoreDraft();
  // Typing a name or changing a default is part of the draft too.
  byId('page-control').addEventListener('input', saveDraft);
  byId('page-control').addEventListener('change', saveDraft);
  byId('playlistList').addEventListener('pointerdown', startPageDrag);
  // A playlist being edited that's since been deleted (elsewhere) isn't
  // being edited any more.
  loadSavedPlaylists().then(data => {
    if (data && loadedPlaylist && !(loadedPlaylist in data)) setLoadedPlaylist(null);
  });
}

registerActions({
  clearDisplay, saveMessage, sync, saveCurrentPlaylist, stopApp,
  toggleMultiMode, centerLines, updatePlaylistItemFromInput,
  movePlaylist, editPlaylist, removeFromPlaylist, duplicatePlaylistPage, pushPlaylistPage,
  loadSavedPlaylist, runSavedPlaylist, deleteSavedPlaylist,
});
