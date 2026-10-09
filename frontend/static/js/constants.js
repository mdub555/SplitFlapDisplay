// What the backend knows about the display, rendered into the page as
// CONFIG (see client_config() in routes/pages.py), so nothing here is a
// hand-kept copy of the backend's tables.
const GRID_ROWS = CONFIG.grid_rows;
const GRID_COLS = CONFIG.grid_cols;
const NUM_MODULES = CONFIG.num_modules;
// For the stylesheets, which size the display boxes from it (control.css).
document.documentElement.style.setProperty('--grid-cols', GRID_COLS);

// Every character the reels can show, in flap order (index 0 is blank).
const CHAR_MAP = CONFIG.flap_chars;

// How a flap character is shown on screen: colour codes as their tile,
// the quote's stand-in as a quote, and a blank as nothing.
function displayChar(ch) {
  const shown = CONFIG.display_chars[ch] || ch;
  return shown === ' ' ? '' : shown;
}

// A flap character as a person reads it: the blank flap as "blank", and a
// code shown as something else with both, e.g. "🟥 (r)".
function flapLabel(ch) {
  if (ch === undefined) return '?';
  if (ch === ' ') return 'blank';
  const shown = displayChar(ch);
  return shown === ch ? ch : `${shown} (${ch})`;
}

// Each colour tile's flap code ({emoji: code}). The black tile is the blank
// flap (' '): no flap is shown as it, so it's the one tile display_chars
// doesn't name. Worked out here rather than only trusting `code` in the
// config, so the tiles still work if the page is newer than the server that
// rendered it (the app hasn't been restarted since an update, say).
const SHOWN_AS_CODE = Object.fromEntries(Object.entries(CONFIG.display_chars).map(([code, shown]) => [shown, code]));
const TILE_CODES = Object.fromEntries(CONFIG.color_tiles.map(tile =>
  [tile.emoji, tile.code ?? SHOWN_AS_CODE[tile.emoji] ?? ' ']));

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
