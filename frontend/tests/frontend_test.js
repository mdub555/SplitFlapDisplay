const { dom, window, calls, MockEventSource } = require('./harness');

const document = window.document;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

let passed = 0, failed = 0;
function check(label, cond) {
  if (cond) { passed++; console.log(`  ok  - ${label}`); }
  else { failed++; console.log(`  FAIL - ${label}`); }
}

// Top-level let/const in a <script> tag don't become window.X properties
// (correct browser behavior — same reason ACTIONS/api/playlist etc. aren't
// window-scoped either). Read them the way another script tag would: via
// a shared lexical lookup, which window.eval() can do as long as it's only
// *reading* an existing binding, not declaring a new one.
const globalVar = (name) => window.eval(name);
const MODULE_TOGGLES_ALL = () => ['autoHome', 'motorClockwise', 'motorRelease'];

function click(el) {
  el.dispatchEvent(new window.Event('click', { bubbles: true }));
}
function change(el) {
  el.dispatchEvent(new window.Event('change', { bubbles: true }));
}

async function main() {
  // jsdom fires its own DOMContentLoaded once the document finishes parsing
  // (standard behavior for any full HTML document under runScripts:
  // 'dangerously', independent of whether <script> tags are present) — that
  // alone runs main.js's bootstrap. Dispatching a second one manually here
  // used to double-run it silently (every step of main.js's bootstrap
  // happens to be idempotent, so it went unnoticed — until now: a second
  // EventSource getting opened is exactly the kind of thing a duplicate
  // bootstrap run would cause in a real browser too, so this is worth
  // catching rather than masking with a redundant manual dispatch).
  await sleep(50); // let jsdom's native DOMContentLoaded + the config/apps fetches settle

  console.log('\n--- Boot ---');
  check('GRID_COLS picked up from /config (16)', globalVar('GRID_COLS') === 16);
  check('NUM_MODULES picked up from /config (64)', globalVar('NUM_MODULES') === 64);
  check('line inputs built for 4 rows', document.querySelectorAll('#lineInputs .line-input').length === 4);
  check('color palette built', document.querySelectorAll('#colorPalette .color-btn').length === 8);
  check('live flap grids built (control)', document.querySelectorAll('.live-grid-control .live-flap').length === 64);
  check('apps grid pre-populated by main.js', Object.keys(window.appsByKey).length === 2);

  console.log('\n--- Serial debug panel ---');
  const debugPanelEl = document.getElementById('debug-panel');
  click(document.getElementById('tab-debug'));
  check('SERIAL DEBUG tab opens the debug panel', debugPanelEl.classList.contains('visible'));
  click(debugPanelEl.querySelector('[data-onclick="toggleDebug"]'));
  check('CLOSE button hides the debug panel again', !debugPanelEl.classList.contains('visible'));

  console.log('\n--- Tab switching (data-onclick delegation) ---');
  const appsTab = document.getElementById('tab-apps');
  click(appsTab);
  await sleep(20);
  check('apps tab becomes active on click', document.getElementById('page-apps').classList.contains('active'));
  check('control tab becomes inactive', !document.getElementById('page-control').classList.contains('active'));
  check('apps grid rendered with 2 cards', document.querySelectorAll('#appsGrid .app-card').length === 2);

  const weatherCard = document.querySelector('#appsGrid .app-card[data-app="weather"]');
  check('weather card has a gear icon (has settings_fields)', !!weatherCard.querySelector('.app-gear'));
  const timeCard = document.querySelector('#appsGrid .app-card[data-app="time"]');
  check('time card has NO gear icon (no settings_fields)', !timeCard.querySelector('.app-gear'));

  console.log('\n--- Running an app via delegated click ---');
  calls.length = 0;
  click(weatherCard);
  await sleep(20);
  check('runApp posted to /run_app', calls.some(c => c.url === '/run_app' && c.method === 'POST'));
  check('run_app body carries the right app key', calls.some(c => c.url === '/run_app' && JSON.parse(c.body).app === 'weather'));

  console.log('\n--- Gear click opens settings, NOT runApp (event delegation stops at nearest match) ---');
  calls.length = 0;
  const gear = weatherCard.querySelector('.app-gear');
  click(gear);
  await sleep(20);
  check('clicking gear did NOT also trigger /run_app', !calls.some(c => c.url === '/run_app'));
  check('clicking gear fetched /settings for the modal', calls.some(c => c.url === '/settings' && c.method === 'GET'));
  check('modal is now visible', document.getElementById('appSettingsModal').style.display === 'flex');
  check('modal rendered the zip_code field', !!document.getElementById('asf_zip_code'));

  console.log('\n--- Saving app settings via delegated click ---');
  document.getElementById('asf_zip_code').value = '94103';
  calls.length = 0;
  click(document.querySelector('#appSettingsModal [data-onclick="saveAppSettings"]'));
  await sleep(20);
  check('save posted to the per-app settings endpoint', calls.some(c => c.url === '/apps/weather/settings'));
  check('save body carries the edited value', calls.some(c => c.url === '/apps/weather/settings' && JSON.parse(c.body).zip_code === '94103'));
  check('modal closes after save', document.getElementById('appSettingsModal').style.display === 'none');

  console.log('\n--- Back to control tab: playlist row rendering (no innerHTML injection of user data) ---');
  click(document.getElementById('tab-control'));
  await sleep(20);

  // Type something with HTML-special characters into line 1 and add it to the playlist —
  // this is exactly the case that would have been dangerous with old-style innerHTML +
  // string-interpolated onclick if it ever touched something less constrained than flap text.
  const l0 = document.getElementById('L0');
  l0.value = '<b>hi</b>';
  l0.dispatchEvent(new window.Event('input', { bubbles: true }));
  click(document.getElementById('saveMsgBtn'));
  await sleep(20);

  const row = document.querySelector('#playlistList .playlist-item');
  check('playlist row was created', !!row);
  check('row carries data-idx for delegation', row && row.dataset.idx === '0');
  check('no live <b> element was injected into the preview (textContent, not innerHTML)',
    row && row.querySelectorAll('b').length === 0);
  check('the literal text (uppercased) is present as text', row && row.textContent.includes('<B>HI</B>'));

  console.log('\n--- Playlist row buttons dispatch via delegation, not per-row listeners ---');
  calls.length = 0;
  const delBtn = row.querySelector('[data-onclick="removeFromPlaylist"]');
  check('delete button carries data-onclick, not onclick', delBtn.getAttribute('onclick') === null);
  click(delBtn);
  await sleep(20);
  check('row removed after delegated delete click', document.querySelectorAll('#playlistList .playlist-item').length === 0);

  console.log('\n--- Playlist name with quotes/special chars survives via dataset (no encode/decode needed) ---');
  // Rebuild a saved-playlist row directly to test the name round-trip through dataset.
  const trickyName = `weird "name" & <stuff>`;
  window.renderSavedPlaylists({ [trickyName]: { pages: [{text: 'X'.repeat(64)}], delay: 5 } });
  const savedRow = document.querySelector('#savedPlaylistList .saved-pl-item');
  check('saved playlist name rendered as text, unescaped weirdness intact', savedRow.querySelector('.saved-pl-name').textContent === trickyName);
  check('name available via dataset for delegated handlers', savedRow.dataset.name === trickyName);

  calls.length = 0;
  const loadBtn = savedRow.querySelector('[data-onclick="loadSavedPlaylist"]');
  // playlists() will return {} from the mock (GET /playlists), so this just verifies
  // the request goes out with no crash and no stale encodeURIComponent artifacts.
  click(loadBtn);
  await sleep(20);
  check('loadSavedPlaylist fetched /playlists', calls.some(c => c.url === '/playlists' && c.method === 'GET'));

  console.log('\n--- Live state arrives over SSE, not polling ---');
  const stateStreams = MockEventSource.instances.filter(s => s.url === '/current_state/stream');
  check('exactly one EventSource was opened at /current_state/stream', stateStreams.length === 1);
  check('the only other EventSource is the debug panel\'s /serial_log/stream',
    MockEventSource.instances.length === 2 &&
    MockEventSource.instances.filter(s => s.url === '/serial_log/stream').length === 1);
  check('no /current_state polling request was ever made', !calls.some(c => c.url === '/current_state'));

  const source = stateStreams[0];
  await sleep(10); // let the mock's async onopen fire

  source.emit({ is_homed: false, state: ' '.repeat(64), active_app: 'weather' });
  await sleep(10);
  check('a pushed snapshot toggles the homing overlay',
    document.getElementById('homing-control').style.display === 'flex');
  check('a pushed snapshot updates the active-app banner',
    document.getElementById('control-banner').classList.contains('visible') &&
    document.getElementById('control-app-name').textContent === 'Weather');

  source.emit({ is_homed: true, state: 'X'.repeat(64), active_app: null });
  await sleep(10);
  check('homing overlay clears once is_homed is true',
    document.getElementById('homing-control').style.display === 'none');
  check('banner hides once active_app is null',
    !document.getElementById('control-banner').classList.contains('visible'));

  console.log('\n--- Malformed SSE payload logged and skipped, not thrown ---');
  let threw = false;
  try { source.emitRaw('not valid json'); } catch (e) { threw = true; }
  await sleep(10);
  check('a malformed message does not throw / app still responsive', !threw && document.getElementById('tab-tuning') !== null);

  console.log('\n--- Stream disconnect shows the status banner; reconnect clears it ---');
  const streamStatus = document.getElementById('streamStatus');
  check('status banner starts hidden', !streamStatus.classList.contains('visible'));
  source.simulateError();
  await sleep(10);
  check('status banner becomes visible on stream error', streamStatus.classList.contains('visible'));
  source.simulateReconnect();
  await sleep(10);
  check('status banner hides again once the stream reconnects', !streamStatus.classList.contains('visible'));

  click(document.getElementById('tab-tuning'));
  await sleep(30);
  check('tuning tab loaded module grid', document.querySelectorAll('#modMatrix .mod-cell').length === 64);

  console.log('\n--- Optimistic-UI revert on failure (auto-home toggle) ---');
  const autoHomeToggle = document.getElementById('autoHomeToggle');
  autoHomeToggle.checked = true;
  // Force this specific call to fail by monkey-patching fetch just for this one call.
  const realFetch = window.fetch;
  window.fetch = async (url, opts) => {
    if (url === '/toggle_autohome') return { ok: false, status: 500, json: async () => ({message: 'boom'}) };
    return realFetch(url, opts);
  };
  change(autoHomeToggle);
  await sleep(20);
  check('checkbox reverted to previous state after failed save', autoHomeToggle.checked === false);
  window.fetch = realFetch;

  console.log('\n--- Optimistic-UI revert on failure (calibration timeout, HTTP 500 body) ---');
  const inspectCalib = document.getElementById('inspectCalib');
  const before = inspectCalib.textContent;
  window.confirm = () => true; // jsdom has no real confirm() dialog
  click(document.querySelector('[data-onclick="calibrateSelected"]'));
  await sleep(20);
  check('calibration display reverted after simulated 500/Timeout response', inspectCalib.textContent === before);

  console.log('\n--- Offset adjust buttons carry delta via dataset, not string-interpolated onclick ---');
  const plusOne = document.querySelector('[data-onclick="adjustOffset"][data-delta="1"]');
  check('offset button has no legacy onclick attribute', plusOne.getAttribute('onclick') === null);
  calls.length = 0;
  click(plusOne);
  await sleep(20);
  check('adjust request sent with delta=1 from dataset', calls.some(c => c.url.match(/\/modules\/\d+\/adjust/) && JSON.parse(c.body).delta === 1));
  check('offset display updated from response', document.getElementById('inspectOffset').textContent === '2900');

  console.log('\n--- Per-module toggles in the Hardware Inspector ---');
  const modToggle = (key) => document.getElementById(`modToggle-${key}`);
  check('toggles reflect the selected module\'s stored settings',
    modToggle('autoHome').checked === true && modToggle('motorClockwise').checked === true &&
    modToggle('motorRelease').checked === false);
  check('toggles are enabled for a provisioned module', !modToggle('autoHome').disabled);

  calls.length = 0;
  modToggle('motorRelease').checked = true;
  change(modToggle('motorRelease'));
  await sleep(20);
  const settingCall = calls.find(c => c.url === '/modules/0/setting' && c.method === 'POST');
  check('toggling posts to the per-module setting endpoint', !!settingCall);
  check('body names the setting and carries a real boolean',
    settingCall && JSON.parse(settingCall.body).setting === 'motorRelease' && JSON.parse(settingCall.body).value === true);
  check('toggle stays on and is re-enabled after success',
    modToggle('motorRelease').checked === true && !modToggle('motorRelease').disabled);
  check('local settings updated, so switching modules keeps the value',
    globalVar('currentSettings').modules['0'].motorRelease === true);

  window.fetch = async (url, opts) => {
    if (url === '/modules/0/setting') return { ok: false, status: 500, json: async () => ({message: 'boom'}) };
    return realFetch(url, opts);
  };
  modToggle('autoHome').checked = false;
  change(modToggle('autoHome'));
  await sleep(20);
  check('toggle reverts after a failed save', modToggle('autoHome').checked === true);
  check('stored value is unchanged after a failed save', globalVar('currentSettings').modules['0'].autoHome === true);
  check('toggle is re-enabled after a failed save', !modToggle('autoHome').disabled);
  window.fetch = realFetch;

  autoHomeToggle.checked = false;
  change(autoHomeToggle);
  await sleep(20);
  check('global auto-home toggle is mirrored into the per-module toggle', modToggle('autoHome').checked === false);
  check('global auto-home toggle is mirrored into stored module settings',
    globalVar('currentSettings').modules['0'].autoHome === false);

  click(document.querySelector('#modMatrix .mod-cell[data-id="5"]'));
  await sleep(20);
  check('toggles are disabled and cleared for an unprovisioned module',
    MODULE_TOGGLES_ALL().every(k => modToggle(k).disabled && !modToggle(k).checked) &&
    document.getElementById('moduleToggles').classList.contains('disabled'));
  click(document.querySelector('#modMatrix .mod-cell[data-id="0"]'));
  await sleep(20);
  check('selecting a provisioned module again re-enables its toggles', !modToggle('autoHome').disabled);

  console.log('\n--- Module IDs are displayed in hex, not decimal ---');
  check('grid cell for module 10 shows hex (0A), not decimal',
    document.querySelector('#modMatrix .mod-cell[data-id="10"]').textContent === '0A');
  check('grid cell for module 63 (the last one) shows hex (3F), not decimal',
    document.querySelector('#modMatrix .mod-cell[data-id="63"]').textContent === '3F');

  click(document.querySelector('#modMatrix .mod-cell[data-id="10"]'));
  await sleep(20);
  check('inspector title shows the selected module id in hex', document.getElementById('inspectTitle').textContent === 'MODULE 0A');

  let lastConfirmMsg = null;
  window.confirm = (msg) => { lastConfirmMsg = msg; return true; };
  const lastToastText = () => document.getElementById('toastContainer').lastElementChild.textContent;

  calls.length = 0;
  click(document.querySelector('[data-onclick="homeSelected"]'));
  await sleep(20);
  check('home request still addresses the module by its real decimal id', calls.some(c => c.url === '/modules/10/home'));
  check('homing toast names the module in hex, not decimal', lastToastText() === 'Homing module 0A');

  click(document.querySelector('[data-onclick="calibrateSelected"]'));
  await sleep(20);
  check('calibrate confirmation names the module in hex', lastConfirmMsg === 'Calibrate Module 0A? It will spin 360° to measure steps.');

  click(document.querySelector('#modMatrix .mod-cell[data-id="0"]'));
  await sleep(20);

  console.log('\n--- ADD MODULE button provisions the selected module ---');
  calls.length = 0;
  click(document.querySelector('[data-onclick="provisionModule"]'));
  await sleep(20);
  check('provision request was sent (action is registered)', calls.some(c => c.url === '/provision_module' && c.method === 'POST'));
  check('provision body carries the selected module id as a plain number',
    calls.some(c => c.url === '/provision_module' && JSON.parse(c.body).id === globalVar('selectedModule')));
  check('provision confirmation names the target module in hex', lastConfirmMsg === 'Assign ID 00 to the unprovisioned module on the bus?');
  await sleep(20);
  check('provisioned-module toast names the assigned id in hex, not decimal', lastToastText() === 'Module assigned ID 0A');

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('Test harness crashed:', err);
  process.exit(1);
});
