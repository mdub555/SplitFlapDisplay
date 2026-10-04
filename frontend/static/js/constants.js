// Grid size is populated at load time by main.js from GET /config — these
// placeholders are overwritten before anything else runs. Nothing else in
// the frontend should hardcode 45 / 15 / 3.
let GRID_ROWS = 3;
let GRID_COLS = 15;
let NUM_MODULES = 45;

// Must match display/charset.py FLAP_CHARS exactly.
const CHAR_MAP = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.q:@#$&()+-*/=%dhwroygbp";

const STATE_DISPLAY = {
  'r':'🟥','o':'🟧','y':'🟨','g':'🟩','b':'🟦','p':'🟪','w':'⬜','q':'"',
  'd':'°','h':'♥'
};

const COLOR_PALETTE = ['🟥','🟧','🟨','🟩','🟦','🟪','⬜','⬛'];
const COLOR_TITLES = {'🟥':'Red','🟧':'Orange','🟨':'Yellow','🟩':'Green','🟦':'Blue','🟪':'Purple','⬜':'White','⬛':'Black'};

const TRANSITION_STYLES = [
  {v:'ltr',          l:'Left → Right'},
  {v:'rtl',          l:'Right → Left'},
  {v:'diagonal',     l:'Diagonal ↘'},
  {v:'anti_diagonal',l:'Diagonal ↙'},
  {v:'center_out',   l:'Center Out'},
  {v:'outside_in',   l:'Outside In'},
  {v:'random',       l:'Random'},
  {v:'rain',         l:'Rain (Top→Bot)'},
  {v:'reverse_rain', l:'Rain (Bot→Top)'},
  {v:'spiral',       l:'Spiral'},
  {v:'columns',      l:'Columns'},
  {v:'alternating',  l:'Alt (↔↔↔)'},
];

function buildStyleOptions(selected='ltr'){
  return TRANSITION_STYLES.map(s=>
    `<option value="${s.v}"${s.v===selected?' selected':''}>${s.l}</option>`
  ).join('');
}

function setGridConfig(cfg){
  GRID_ROWS = cfg.grid_rows;
  GRID_COLS = cfg.grid_cols;
  NUM_MODULES = cfg.num_modules;
}

// Module IDs are shown to the user in hex (easier to scan at a glance than
// decimal once you get past a handful of modules) everywhere in the UI —
// the module grid, the inspector title, and any toast/confirm message that
// names a module. This is purely cosmetic: every network request and the
// wire protocol itself still use the plain decimal id (see api.js and
// tranceiver.h) — only text the user reads goes through this.
function formatModuleId(id){
  return id.toString(16).toUpperCase().padStart(2, '0');
}
