const { JSDOM } = require('jsdom');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');

// Strip Jinja url_for(...) calls AND the original <script src="..."> tags —
// we'll inject equivalent inline <script> elements ourselves so jsdom
// executes them as real Script elements (sharing top-level let/const across
// files, exactly like a browser), rather than needing a network/file resource
// loader for the src= URLs.
let html = fs.readFileSync(path.join(ROOT, 'templates/index.html'), 'utf8');
html = html.replace(/\{\{\s*url_for\([^}]*filename='([^']+)'\)\s*\}\}/g, '/static/$1');
html = html.replace(/<script src="[^"]*"><\/script>\s*/g, '');

const dom = new JSDOM(html, { runScripts: 'dangerously', url: 'http://localhost/' });
const { window } = dom;

// jsdom doesn't implement requestAnimationFrame — polyfill for toast.js.
window.requestAnimationFrame = (cb) => setTimeout(cb, 0);

// --- Mock fetch: log every call, return canned responses per-route ---
const calls = [];
let failNextCurrentState = false;

window.fetch = async (url, options = {}) => {
  calls.push({ url, method: options.method || 'GET', body: options.body });

  const ok = (data, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  });

  if (url === '/config') {
    return ok({ grid_rows: 4, grid_cols: 16, num_modules: 64, hardware_connected: false });
  }
  if (url === '/current_state') {
    if (failNextCurrentState) { failNextCurrentState = false; throw new Error('simulated network drop'); }
    return ok({ is_homed: true, state: ' '.repeat(64), active_app: null });
  }
  if (url === '/apps') {
    return ok([
      { key: 'weather', name: 'Weather', icon: '🌤️', desc: 'Current conditions',
        settings_fields: [{ key: 'zip_code', label: 'Zip Code', type: 'text', opts: [], placeholder: '02118' }] },
      { key: 'time', name: 'Time', icon: '⏱️', desc: 'Live clock', settings_fields: [] },
    ]);
  }
  if (url === '/run_app') {
    return ok({ status: 'App weather started' });
  }
  if (url === '/stop_app') {
    return ok({ status: 'stopped' });
  }
  if (url === '/global_fields') {
    return ok([{ key: 'timezone', label: 'Timezone', type: 'text', opts: [], placeholder: 'US/Eastern', default: 'US/Eastern' }]);
  }
  if (url === '/settings') {
    if (options.method === 'POST') return ok({ status: 'Saved' });
    return ok({ timezone: 'US/Eastern', zip_code: '02118', offsets: {'0': 2832}, calibrations: {'0': 4096}, auto_home: true });
  }
  if (url === '/playlists') {
    if (options.method === 'POST') return ok({ status: 'saved', name: 'Test' });
    return ok({});
  }
  if (url.startsWith('/apps/') && url.endsWith('/settings')) {
    return ok({ status: 'saved' });
  }
  if (url.match(/^\/modules\/\d+\/adjust$/)) {
    return ok({ new_offset: 2900 });
  }
  if (url.match(/^\/modules\/\d+\/calibrate$/)) {
    // Simulate the real backend's timeout shape: HTTP 500 + message body.
    return ok({ status: 'error', message: 'Timeout' }, 500);
  }
  if (url === '/toggle_autohome') {
    return ok({ status: 'Auto-home updated' });
  }
  if (url === '/home_all') {
    return ok({ status: 'Homing All' });
  }

  throw new Error(`Unmocked fetch: ${url}`);
};

// Load every JS file as a real <script> element, in the same order as
// index.html, so top-level const/let declarations are shared across files
// exactly the way real browser <script> tags share one global lexical
// environment (unlike window.eval(), which scopes let/const per call).
const files = [
  'static/js/actions.js', 'static/js/constants.js', 'static/js/toast.js',
  'static/js/api.js', 'static/js/live-flap.js', 'static/js/tabs.js',
  'static/js/control.js', 'static/js/apps.js', 'static/js/app-settings-modal.js',
  'static/js/tuning.js', 'static/js/main.js',
];
for (const f of files) {
  const scriptEl = window.document.createElement('script');
  scriptEl.textContent = fs.readFileSync(path.join(ROOT, f), 'utf8');
  window.document.head.appendChild(scriptEl);
}

module.exports = { dom, window, calls, setFailNextCurrentState: v => (failNextCurrentState = v) };
