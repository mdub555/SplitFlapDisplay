const { dom, window, calls, setFailNextCurrentState } = require('./harness');

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

function click(el) {
  el.dispatchEvent(new window.Event('click', { bubbles: true }));
}
function change(el) {
  el.dispatchEvent(new window.Event('change', { bubbles: true }));
}

async function main() {
  // Fire DOMContentLoaded to run main.js's bootstrap.
  document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true }));
  await sleep(50); // let the config/apps fetches + rendering settle

  console.log('\n--- Boot ---');
  check('GRID_COLS picked up from /config (16)', globalVar('GRID_COLS') === 16);
  check('NUM_MODULES picked up from /config (64)', globalVar('NUM_MODULES') === 64);
  check('line inputs built for 4 rows', document.querySelectorAll('#lineInputs .line-input').length === 4);
  check('color palette built', document.querySelectorAll('#colorPalette .color-btn').length === 8);
  check('live flap grids built (control)', document.querySelectorAll('.live-grid-control .live-flap').length === 64);
  check('apps grid pre-populated by main.js', Object.keys(window.appsByKey).length === 2);

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

  console.log('\n--- Error handling: failed request shows a toast and does not crash ---');
  await sleep(1100); // let one polling tick pass normally first
  setFailNextCurrentState(true);
  await sleep(1100); // this tick's fetch throws inside the mock
  check('a failed /current_state tick does not throw / app still responsive',
    document.getElementById('tab-tuning') !== null);

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

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('Test harness crashed:', err);
  process.exit(1);
});
