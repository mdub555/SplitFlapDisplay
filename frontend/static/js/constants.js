// What the backend knows about the display, rendered into the page as
// CONFIG (see client_config() in routes/pages.py), so nothing here is a
// hand-kept copy of the backend's tables.
const GRID_ROWS = CONFIG.grid_rows;
const GRID_COLS = CONFIG.grid_cols;
const NUM_MODULES = CONFIG.num_modules;

// Every character the reels can show, in flap order (index 0 is blank).
const CHAR_MAP = CONFIG.flap_chars;

// How a flap character is shown on screen: colour codes as their tile,
// the quote's stand-in as a quote, and a blank as nothing.
function displayChar(ch) {
  const shown = CONFIG.display_chars[ch] || ch;
  return shown === ' ' ? '' : shown;
}

// The options of an animation style <select>, with `selected` chosen.
function styleOptions(selected = 'ltr') {
  return CONFIG.styles.map(s => el('option', {value: s.value, selected: s.value === selected}, s.label));
}

// Module IDs are shown to the user in hex (easier to scan at a glance than
// decimal once you get past a handful of modules) everywhere in the UI —
// the module grid, the inspector title, and any toast/confirm message that
// names a module. This is purely cosmetic: every network request and the
// wire protocol itself still use the plain decimal id — only text the user
// reads goes through this.
function formatModuleId(id) {
  return id.toString(16).toUpperCase().padStart(2, '0');
}
