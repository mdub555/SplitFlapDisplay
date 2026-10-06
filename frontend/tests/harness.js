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

// jsdom has no EventSource implementation either. This mock behaves like the
// real thing closely enough for tests: one persistent instance per URL (a
// real EventSource doesn't get reconstructed on auto-retry, it just flips
// readyState and re-fires onerror/onopen on the SAME object), with test-only
// helper methods to simulate the server pushing a message, a connection
// drop, or the browser's automatic reconnect succeeding.
class MockEventSource {
  constructor(url) {
    this.url = url;
    this.readyState = 0; // CONNECTING
    this.onopen = null;
    this.onmessage = null;
    this.onerror = null;
    MockEventSource.instances.push(this);
    // Real EventSource connects asynchronously — mirror that so code relying
    // on "onopen hasn't fired yet" immediately after construction still works.
    setTimeout(() => {
      this.readyState = 1; // OPEN
      if (this.onopen) this.onopen(new window.Event('open'));
    }, 0);
  }
  emit(data) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(data) });
  }
  emitRaw(rawString) {
    if (this.onmessage) this.onmessage({ data: rawString });
  }
  simulateError() {
    this.readyState = 0; // CONNECTING — matches the real spec's auto-retry state
    if (this.onerror) this.onerror(new window.Event('error'));
  }
  simulateReconnect() {
    this.readyState = 1;
    if (this.onopen) this.onopen(new window.Event('open'));
  }
  close() {
    this.readyState = 2; // CLOSED
  }
}
MockEventSource.instances = [];
window.EventSource = MockEventSource;

// --- Mock fetch: log every call, return canned responses per-route ---
const calls = [];

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
    // Same shape the real backend returns: per-module config lives under `modules`
    // (only module 0 is provisioned here).
    return ok({ timezone: 'US/Eastern', zip_code: '02118', auto_home: true,
      modules: { '0': { homeOffset: 2832, totalSteps: 4096, autoHome: true, motorClockwise: true, motorRelease: false, drift: 3, revolutions: 12345,
                       stepDelayUs: 1000, homingStepDelayUs: 1800, debounceMs: 100, rampStartDelayUs: 3000, rampSteps: 0, settleMs: 0, staggerMs: 120 },
                '2': { homeOffset: 480, totalSteps: 4096, autoHome: true, motorClockwise: true, motorRelease: false },
                // Synced from firmware whose step delays were still in milliseconds.
                '3': { homeOffset: 480, totalSteps: 4096, autoHome: true, motorClockwise: true, motorRelease: false,
                       stepDelay: 1, homingStepDelay: 2, debounceMs: 100, rampStartDelay: 3, rampSteps: 0, settleMs: 0, staggerMs: 150 } },
      firmware: { stepDelayUs: 1000, homingStepDelayUs: 1800, debounceMs: 100, recalculateHome: true,
                  rampStartDelayUs: 3000, rampSteps: 0, settleMs: 0, staggerMs: 150 } });
  }
  if (url === '/playlists') {
    if (options.method === 'POST') return ok({ status: 'saved', name: 'Test' });
    return ok({});
  }
  if (url.startsWith('/apps/') && url.endsWith('/settings')) {
    return ok({ status: 'saved' });
  }
  if (url.match(/^\/modules\/\d+\/home$/)) {
    return ok({ status: 'Homing' });
  }
  if (url.match(/^\/modules\/\d+\/exercise$/)) {
    return ok({ status: 'success', cycles: JSON.parse(options.body).cycles });
  }
  if (url.match(/^\/modules\/\d+\/stop$/)) {
    return ok({ status: 'success' });
  }
  if (url.match(/^\/modules\/\d+\/reboot$/)) {
    return ok({ status: 'success' });
  }
  if (url.match(/^\/modules\/\d+\/reset_settings$/)) {
    return ok({ status: 'success', settings: { auto_home: true, modules: {
      '10': { homeOffset: 480, totalSteps: 4096, autoHome: false, motorClockwise: true, motorRelease: true } } } });
  }
  if (url.match(/^\/modules\/\d+\/identify$/)) {
    return ok({ status: 'success' });
  }
  if (url.match(/^\/modules\/\d+\/adjust$/)) {
    return ok({ new_offset: 2900 });
  }
  if (url.match(/^\/modules\/\d+\/calibrate$/)) {
    // Simulate the real backend's timeout shape: HTTP 500 + message body.
    return ok({ status: 'error', message: 'Timeout' }, 500);
  }
  if (url.match(/^\/modules\/\d+\/setting$/)) {
    const { setting, value } = JSON.parse(options.body);
    return ok({ status: 'success', setting, value });
  }
  if (url === '/toggle_autohome') {
    return ok({ status: 'Auto-home updated' });
  }
  if (url === '/firmware_config') {
    if (options.method === 'POST') return ok({ status: 'success', values: JSON.parse(options.body) });
    return ok({
      values: { stepDelayUs: 1000, homingStepDelayUs: 1800, debounceMs: 100, recalculateHome: true,
                rampStartDelayUs: 3000, rampSteps: 0, settleMs: 0, staggerMs: 150 },
      limits: {
        stepDelayUs:       { type: 'int',  min: 1, max: 65535 },
        homingStepDelayUs: { type: 'int',  min: 1, max: 65535 },
        debounceMs:      { type: 'int',  min: 0, max: 65535 },
        recalculateHome: { type: 'bool', min: null, max: null },
        rampStartDelayUs:  { type: 'int',  min: 1, max: 65535 },
        rampSteps:       { type: 'int',  min: 0, max: 255 },
        settleMs:        { type: 'int',  min: 0, max: 255 },
        staggerMs:       { type: 'int',  min: 0, max: 255 },
      },
    });
  }
  if (url === '/home_all') {
    return ok({ status: 'Homing All' });
  }
  if (url === '/provision_module') {
    return ok({ status: 'success', assigned_id: 10 });
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
  'static/js/tuning.js', 'static/js/main.js', 'static/js/debug.js',
];
for (const f of files) {
  const scriptEl = window.document.createElement('script');
  scriptEl.textContent = fs.readFileSync(path.join(ROOT, f), 'utf8');
  window.document.head.appendChild(scriptEl);
}

module.exports = { dom, window, calls, MockEventSource };
