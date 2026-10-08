const { dom, window, calls, MockEventSource, savedPlaylists } = require('./harness');

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
const MODULE_TOGGLES_ALL = () => ['motorClockwise'];

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
  check('compose grid built with a flap per module', document.querySelectorAll('#preview .flap-unit').length === 64);
  check('color palette built', document.querySelectorAll('#colorPalette .color-btn:not(.symbol-btn)').length === 8);
  check('degree and heart buttons follow the colours',
    [...document.querySelectorAll('#colorPalette .symbol-btn')].map(b => b.textContent).join('') === '°♥');
  check('live flap grid built', document.querySelectorAll('#liveGrid .live-flap').length === 64);
  check('the live display sits above the tabs, outside every page',
    !document.getElementById('liveGrid').closest('.page') &&
    !!(document.getElementById('liveGrid').compareDocumentPosition(document.querySelector('.tab-bar')) & window.Node.DOCUMENT_POSITION_FOLLOWING));
  check('apps grid pre-populated by main.js', Object.keys(window.appsByKey).length === 2);

  console.log('\n--- Debug page ---');
  click(document.getElementById('tab-debug'));
  check('DEBUG tab shows the debug page', document.getElementById('page-debug').classList.contains('active'));
  check('and hides the control page', !document.getElementById('page-control').classList.contains('active'));
  click(document.getElementById('tab-control'));

  console.log('\n--- Tab switching (data-onclick delegation) ---');
  const appsTab = document.getElementById('tab-apps');
  click(appsTab);
  await sleep(20);
  check('apps tab becomes active on click', document.getElementById('page-apps').classList.contains('active'));
  check('control tab becomes inactive', !document.getElementById('page-control').classList.contains('active'));
  check('apps grid rendered with 2 cards', document.querySelectorAll('#appsGrid .app-card').length === 2);

  console.log('\n--- Global settings live on the Apps page ---');
  const globalGrid = document.getElementById('globalSettingsGrid');
  check('the global settings are on the Apps page, not Modules',
    !!globalGrid.closest('#page-apps') && !document.querySelector('#page-modules #globalSettingsGrid'));
  check('opening Apps fills them from /settings', document.getElementById('gsf_timezone').value === 'US/Eastern');
  document.getElementById('gsf_timezone').value = 'UTC';
  calls.length = 0;
  click(document.querySelector('#page-apps [data-onclick="saveGlobal"]'));
  await sleep(20);
  const globalSave = calls.find(c => c.url === '/settings' && c.method === 'POST');
  check('Save Settings posts the edited values', globalSave && JSON.parse(globalSave.body).timezone === 'UTC');

  const weatherCard = document.querySelector('#appsGrid .app-card[data-app="weather"]');
  check('weather card has a gear icon (has settings_fields)', !!weatherCard.querySelector('.app-gear'));
  const timeCard = document.querySelector('#appsGrid .app-card[data-app="time"]');
  check('time card has NO gear icon (no settings_fields)', !timeCard.querySelector('.app-gear'));

  console.log('\n--- Running an app via delegated click ---');
  calls.length = 0;
  click(weatherCard.querySelector('.app-run'));
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

  // Type something with HTML-special characters into the grid and add it to the
  // playlist: exactly the case that would be dangerous with innerHTML.
  const composeInput = document.getElementById('composeInput');
  const flapText = () => [...document.querySelectorAll('#preview .flap-unit')].map(f => f.textContent || ' ').join('');
  const typeKeys = text => {
    composeInput.value = '_' + text;
    composeInput.dispatchEvent(new window.Event('input', { bubbles: true }));
  };
  typeKeys('(hi) & #1');
  click(document.getElementById('saveMsgBtn'));
  await sleep(20);

  const row = document.querySelector('#playlistList .playlist-item');
  check('playlist row was created', !!row);
  check('row carries data-idx for delegation', row && row.dataset.idx === '0');
  check('no live <b> element was injected into the preview (textContent, not innerHTML)',
    row && row.querySelectorAll('b').length === 0);
  check('the typed text (uppercased) is present as text', row && row.textContent.replace(/\u00a0/g, ' ').includes('(HI) & #1'));

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
  check('the only other EventSource is the Debug page\'s /serial_log/stream',
    MockEventSource.instances.length === 2 &&
    MockEventSource.instances.filter(s => s.url === '/serial_log/stream').length === 1);
  check('no /current_state polling request was ever made', !calls.some(c => c.url === '/current_state'));

  const source = stateStreams[0];
  await sleep(10); // let the mock's async onopen fire

  source.emit({ is_homed: false, state: ' '.repeat(64), active_app: 'weather' });
  await sleep(10);
  check('a pushed snapshot toggles the homing overlay',
    document.getElementById('homingOverlay').style.display === 'flex');
  check('a pushed snapshot updates the active-app banner',
    document.getElementById('live-banner').classList.contains('visible') &&
    document.getElementById('liveBannerText').textContent === '▶ Weather is running');

  source.emit({ is_homed: true, state: 'X'.repeat(64), active_app: null });
  await sleep(10);
  check('homing overlay clears once is_homed is true',
    document.getElementById('homingOverlay').style.display === 'none');
  check('banner hides once active_app is null',
    !document.getElementById('live-banner').classList.contains('visible'));

  console.log('\n--- Malformed SSE payload logged and skipped, not thrown ---');
  let threw = false;
  try { source.emitRaw('not valid json'); } catch (e) { threw = true; }
  await sleep(10);
  check('a malformed message does not throw / app still responsive', !threw && document.getElementById('tab-modules') !== null);

  console.log('\n--- Stream disconnect shows the status banner; reconnect clears it ---');
  const streamStatus = document.getElementById('streamStatus');
  check('status banner starts hidden', !streamStatus.classList.contains('visible'));
  source.simulateError();
  await sleep(10);
  check('status banner becomes visible on stream error', streamStatus.classList.contains('visible'));
  source.simulateReconnect();
  await sleep(10);
  check('status banner hides again once the stream reconnects', !streamStatus.classList.contains('visible'));

  click(document.getElementById('tab-modules'));
  await sleep(30);
  check('modules tab loaded module grid', document.querySelectorAll('#modMatrix .mod-cell').length === 64);
  const phoneColumns = globalVar('phoneColumns');
  check('on a phone the module grid wraps at a whole fraction of the display width',
    [[16, 8], [15, 5], [12, 6], [10, 5], [9, 9], [8, 8], [13, 8], [1, 1]].every(([cols, n]) => phoneColumns(cols) === n));
  check('inspector shows the selected module\'s drift', document.getElementById('inspectDrift').textContent === '3');
  check('inspector shows the revolution count', document.getElementById('inspectRevolutions').textContent === '12,345');
  const timing = document.getElementById('inspectTiming');
  check('inspector shows the timing the module reported',
    timing.textContent.startsWith('From last sync: step delay 1000 µs · homing step delay 1800 µs · debounce 100 ms · ' +
      'ramp start delay 3000 µs · ramp length 0 steps · settle 0 ms · stagger 120 ms'));
  const flagged = [...timing.querySelectorAll('.mismatch')].map(s => s.dataset.key);
  check('only values that differ from the shared settings are highlighted',
    flagged.length === 1 && flagged[0] === 'staggerMs');
  click(document.querySelector('#modMatrix .mod-cell[data-id="1"]'));
  await sleep(20);
  check('unprovisioned module shows no drift', document.getElementById('inspectDrift').textContent === '---');
  check('unprovisioned module shows no timing', document.getElementById('inspectTiming').textContent === '');
  click(document.querySelector('#modMatrix .mod-cell[data-id="2"]'));
  await sleep(20);
  check('module synced from older firmware asks for a sync',
    document.getElementById('inspectTiming').textContent === 'Sync this module to read its timing settings.');
  click(document.querySelector('#modMatrix .mod-cell[data-id="3"]'));
  await sleep(20);
  check('module synced while step delays were in ms asks for a sync',
    document.getElementById('inspectTiming').textContent === 'Sync this module to read its timing settings.');
  click(document.querySelector('#modMatrix .mod-cell[data-id="0"]'));
  await sleep(20);

  console.log('\n--- Firmware settings shared by every module ---');
  const fw = (key) => document.getElementById(`fw-${key}`);
  const toastCount = () => document.getElementById('toastContainer').children.length;
  check('inputs are filled from /firmware_config',
    fw('stepDelayUs').value === '1000' && fw('homingStepDelayUs').value === '1800' &&
    fw('debounceMs').value === '100' && fw('recalculateHome').checked === true &&
    fw('autoHome').checked === true && fw('motorRelease').checked === false);
  check('auto-home and release motor are in the settings for all modules',
    !!fw('autoHome').closest('.config-section').querySelector('[data-onclick="applyFirmwareConfig"]') &&
    !!fw('motorRelease').closest('.config-section').querySelector('[data-onclick="applyFirmwareConfig"]') &&
    !document.getElementById('autoHomeToggle'));
  check('input ranges come from the backend limits',
    fw('debounceMs').min === '0' && fw('debounceMs').max === '65535' && fw('stepDelayUs').min === '1' &&
    fw('stepDelayUs').max === '65535');

  calls.length = 0;
  fw('stepDelayUs').value = '1250';
  fw('debounceMs').value = '150';
  fw('recalculateHome').checked = false;
  fw('autoHome').checked = false;
  click(document.querySelector('[data-onclick="applyFirmwareConfig"]'));
  await sleep(20);
  const fwPost = calls.find(c => c.url === '/firmware_config' && c.method === 'POST');
  check('apply posts to /firmware_config', !!fwPost);
  check('apply sends every setting with real numbers and a real boolean',
    fwPost && JSON.stringify(JSON.parse(fwPost.body)) ===
      JSON.stringify({ stepDelayUs: 1250, homingStepDelayUs: 1800, debounceMs: 150, recalculateHome: false,
                       rampStartDelayUs: 3000, rampSteps: 0, motorRelease: false, settleMs: 0,
                       autoHome: false, staggerMs: 150 }));

  for (const [key, bad] of [['stepDelayUs', '0'], ['stepDelayUs', '65536'], ['debounceMs', '65536'],
                            ['homingStepDelayUs', ''], ['homingStepDelayUs', '1.5'],
                            ['rampStartDelayUs', '0'], ['rampSteps', '256'], ['settleMs', '-1'],
                            ['staggerMs', '256']]) {
    const good = fw(key).value;
    calls.length = 0;
    const toastsBefore = toastCount();
    fw(key).value = bad;
    click(document.querySelector('[data-onclick="applyFirmwareConfig"]'));
    await sleep(20);
    check(`an invalid ${key} (${JSON.stringify(bad)}) sends nothing`,
      !calls.some(c => c.url === '/firmware_config' && c.method === 'POST'));
    check(`an invalid ${key} shows a warning`, toastCount() === toastsBefore + 1);
    fw(key).value = good;
  }

  const realFetch = window.fetch;

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
  check('only motor direction is set per module',
    document.querySelectorAll('#moduleToggles [data-setting]').length === 1 && !!modToggle('motorClockwise'));
  check('the toggle reflects the selected module\'s stored setting', modToggle('motorClockwise').checked === true);
  check('the toggle is enabled for a provisioned module', !modToggle('motorClockwise').disabled);

  calls.length = 0;
  modToggle('motorClockwise').checked = false;
  change(modToggle('motorClockwise'));
  await sleep(20);
  const settingCall = calls.find(c => c.url === '/modules/0/setting' && c.method === 'POST');
  check('toggling posts to the per-module setting endpoint', !!settingCall);
  check('body names the setting and carries a real boolean',
    settingCall && JSON.parse(settingCall.body).setting === 'motorClockwise' && JSON.parse(settingCall.body).value === false);
  check('toggle stays off and is re-enabled after success',
    modToggle('motorClockwise').checked === false && !modToggle('motorClockwise').disabled);
  check('local settings updated, so switching modules keeps the value',
    globalVar('currentSettings').modules['0'].motorClockwise === false);

  window.fetch = async (url, opts) => {
    if (url === '/modules/0/setting') return { ok: false, status: 500, json: async () => ({message: 'boom'}) };
    return realFetch(url, opts);
  };
  modToggle('motorClockwise').checked = true;
  change(modToggle('motorClockwise'));
  await sleep(20);
  check('toggle reverts after a failed save', modToggle('motorClockwise').checked === false);
  check('stored value is unchanged after a failed save', globalVar('currentSettings').modules['0'].motorClockwise === false);
  check('toggle is re-enabled after a failed save', !modToggle('motorClockwise').disabled);
  window.fetch = realFetch;

  click(document.querySelector('#modMatrix .mod-cell[data-id="5"]'));
  await sleep(20);
  check('toggles are disabled and cleared for an unprovisioned module',
    MODULE_TOGGLES_ALL().every(k => modToggle(k).disabled && !modToggle(k).checked) &&
    document.getElementById('moduleToggles').classList.contains('disabled'));
  click(document.querySelector('#modMatrix .mod-cell[data-id="0"]'));
  await sleep(20);
  check('selecting a provisioned module again re-enables its toggles', !modToggle('motorClockwise').disabled);

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

  calls.length = 0;
  click(document.querySelector('[data-onclick="identifySelected"]'));
  await sleep(20);
  check('identify posts to the selected module', calls.some(c => c.url === '/modules/10/identify' && c.method === 'POST'));
  check('identify toast names the module in hex', lastToastText() === 'Module 0A: status LED blinking for 10 s');

  calls.length = 0;
  document.getElementById('exerciseInput').value = '3';
  click(document.querySelector('[data-onclick="exerciseSelected"]'));
  await sleep(20);
  const exPost = calls.find(c => c.url === '/modules/10/exercise');
  check('exercise posts the cycle count as a number', exPost && JSON.parse(exPost.body).cycles === 3);
  calls.length = 0;
  document.getElementById('exerciseInput').value = '0';
  click(document.querySelector('[data-onclick="exerciseSelected"]'));
  await sleep(20);
  check('exercise with 0 cycles sends nothing', !calls.some(c => c.url === '/modules/10/exercise'));
  click(document.querySelector('[data-onclick="stopSelected"]'));
  await sleep(20);
  check('stop posts to the selected module', calls.some(c => c.url === '/modules/10/stop'));

  calls.length = 0;
  click(document.querySelector('[data-onclick="rebootSelected"]'));
  await sleep(20);
  check('reboot asks first, naming the module in hex', lastConfirmMsg === 'Reboot module 0A?');
  check('reboot posts to the selected module', calls.some(c => c.url === '/modules/10/reboot' && c.method === 'POST'));

  calls.length = 0;
  click(document.querySelector('[data-onclick="resetSettingsSelected"]'));
  await sleep(20);
  check('reset settings asks first', lastConfirmMsg.startsWith('Reset every setting on module 0A'));
  check('reset settings posts to the selected module', calls.some(c => c.url === '/modules/10/reset_settings'));
  check('reset settings shows the values the module reported',
    document.getElementById('inspectOffset').textContent === '480' && lastToastText() === 'Module 0A reset to defaults');

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

  console.log('\n--- Debug page shows dump replies as labelled values ---');
  const serialLog = MockEventSource.instances.find(s => s.url === '/serial_log/stream');
  const logEl = document.getElementById('debugLog');
  const logLines = () => [...logEl.querySelectorAll('.debug-log-line')];
  const logBefore = logLines().length;
  const fields = '\tO480\tT4096\tD100\tS1250\tH1800\tC1\tA0\tF1\tE1\tR3000\tL0\tW0\tP150\t#123456\t~-3';
  // A broadcast dump's received text: two replies, one garbled line, then noise.
  serialLog.emit({ msg: `RECV: m05?${fields}\r\nm10?${fields.replace('~-3', '~2')}\r\nm07?\tO48x\r\njunk\r\n` });
  await sleep(10);
  const added = logLines().slice(logBefore);
  check('each received line gets its own log line', added.length === 4);
  const [first, second, garbled, noise] = added;
  const field = (line, key) => line.querySelector(`.dump-field[data-key="${key}"]`).textContent;
  check('a dump reply is shown as labelled values',
    first.classList.contains('dump') && first.classList.contains('recv') &&
    field(first, 'homeOffset') === 'home offset 480 steps' && field(first, 'stepDelayUs') === 'step delay 1,250 µs' &&
    field(first, 'motorClockwise') === 'clockwise yes' && field(first, 'autoHome') === 'auto-home no' &&
    field(first, 'revolutions') === 'revolutions 123,456' && field(first, 'drift') === 'drift -3 steps');
  check('every field is shown', first.querySelectorAll('.dump-field').length === 15);
  check('the reply line names the module on the wire and in hex',
    first.textContent.includes('RECV m05? (module 05): ') && second.textContent.includes('RECV m10? (module 0A): '));
  check('the raw reply is kept as the tooltip', first.title === `m05?${fields}`);
  check('a garbled reply is shown as received', !garbled.classList.contains('dump') &&
    garbled.textContent.endsWith('RECV: m07?\tO48x'));
  check('other received text is shown as received', noise.textContent.endsWith('RECV: junk'));

  console.log('\n--- Debug page builds and sends any command ---');
  const debugSelect = document.getElementById('debugCommand');
  const preview = () => document.getElementById('debugPreview').textContent;
  const param = name => document.getElementById(`debugParam-${name}`);
  const choose = key => { debugSelect.value = key; change(debugSelect); };
  const typeInto = (input, value) => { input.value = value; input.dispatchEvent(new window.Event('input', { bubbles: true })); };
  const sentCmds = () => calls.filter(c => c.url === '/serial/send').map(c => JSON.parse(c.body).cmd);
  const commandKeys = [...debugSelect.options].map(o => o.value);
  check('the dropdown lists every command, grouped',
    commandKeys.length === globalVar('CONFIG').debug_commands.length &&
    [...debugSelect.querySelectorAll('optgroup')].map(g => g.label).join('|') ===
      'Actions|Module|Settings (saved to EEPROM)|Utilities');
  typeInto(document.getElementById('debugModuleId'), '10');
  choose('home');
  check('a command without data goes to the chosen module', preview() === 'm10h');
  check('no inputs for a command without data', document.getElementById('debugParams').children.length === 0);
  choose('show_index');
  typeInto(param('index'), '7');
  check('an index command carries its value', preview() === 'm10+7');
  check('the flap at that index is named', document.getElementById('debugNote').textContent === 'Flap 7: G');
  typeInto(param('index'), '99');
  check('an out-of-range value is refused', document.getElementById('debugSend').disabled);
  choose('show_char');
  typeInto(param('char'), '"');
  check('a quote is sent as its code', preview() === 'm10-q');
  typeInto(param('char'), '\u{1F7E5}');
  check('a colour emoji is sent as its code', preview() === 'm10-r');
  choose('motorClockwise');
  param('value').value = '0'; change(param('value'));
  check('a yes/no setting is a dropdown sent as 0/1', param('value').tagName === 'SELECT' && preview() === 'm10C0');
  const broadcast = document.getElementById('debugBroadcast');
  broadcast.checked = true; change(broadcast);
  check('broadcast sends to *', preview() === 'm*C0' && document.getElementById('debugModuleId').disabled);
  broadcast.checked = false; change(broadcast);
  choose('frame');
  typeInto(param('text'), 'HI!');
  typeInto(param('interval'), '20');
  param('order').value = 'rtl'; change(param('order'));
  check('a frame broadcast always goes to every module, with each character\'s rank',
    preview() === 'm*f20:H#I"!!' && document.getElementById('debugModuleId').disabled);
  choose('calibrate');
  document.getElementById('debugDumpAfter').checked = true;
  change(document.getElementById('debugDumpAfter'));
  calls.length = 0;
  click(document.getElementById('debugSend'));
  await sleep(20);
  check('calibrate can be followed by a state dump', sentCmds().join(',') === 'm10c,m10?');
  choose('reset_settings');
  calls.length = 0;
  click(document.getElementById('debugSend'));
  await sleep(20);
  check('a destructive command asks first, naming the module in hex',
    lastConfirmMsg === 'Reset ALL settings on module 0A to their defaults?' && sentCmds().join() === 'm10!');
  choose('raw');
  typeInto(param('message'), 'm05-B');
  calls.length = 0;
  click(document.getElementById('debugSend'));
  await sleep(20);
  check('a raw message is sent as typed', sentCmds().join() === 'm05-B');
  click(document.querySelector('#flapTable .flap-cell[data-index="3"]'));
  check('picking a flap from the table fills in Show character',
    debugSelect.value === 'show_char' && preview() === 'm10-C');
  click(document.querySelector('[data-onclick="clearDebugLog"]'));
  check('the log can be cleared', logLines().length === 0);

  console.log('\n--- Typing straight into the compose grid ---');
  click(document.getElementById('tab-control'));
  click(document.querySelector('[data-onclick="clearDisplay"]'));
  const key = k => composeInput.dispatchEvent(new window.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));
  const rowN = n => Array.from(flapText()).slice(n * 16, (n + 1) * 16).join('');   // a colour tile is one flap
  const row0 = () => rowN(0);
  const cursorAt = () => [...document.querySelectorAll('#preview .flap-unit')].findIndex(f => f.classList.contains('cursor'));
  typeKeys('hello');
  check('typed letters fill flaps from the cursor, uppercased', row0() === 'HELLO           ' && cursorAt() === 5);
  typeKeys('~');
  check('a character no flap shows is skipped', row0() === 'HELLO           ' && cursorAt() === 5);
  composeInput.value = '';   // a phone keyboard's Backspace deletes the sentinel
  composeInput.dispatchEvent(new window.Event('input', { bubbles: true }));
  check('backspace clears the flap before the cursor', row0() === 'HELL            ' && cursorAt() === 4);
  check('the hidden textarea is reset after each keystroke', composeInput.value === '_');
  key('Enter');
  typeKeys('“ok”');
  check('Enter starts the next line; curly quotes become the quote flap', rowN(1) === '"OK"            ');
  click(document.querySelector('#preview .flap-unit[data-cell="2"]'));
  typeKeys('x');
  check('clicking a flap moves the cursor there; typing overwrites', row0() === 'HEXL            ');
  key('ArrowDown'); key('ArrowLeft');
  check('arrow keys move the cursor', cursorAt() === 18);
  key('Delete');
  check('Delete clears the flap under the cursor', rowN(1) === '"O "            ' && cursorAt() === 18);
  click(document.querySelector('#colorPalette .color-btn'));
  check('a colour tile goes in at the cursor', rowN(1) === '"O🟥"            ');
  const paste = new window.Event('paste', { bubbles: true, cancelable: true });
  paste.clipboardData = { getData: () => 'AB\nCD' };
  click(document.querySelector('#preview .flap-unit[data-cell="48"]'));
  composeInput.dispatchEvent(paste);
  check('pasted lines go on successive rows', rowN(3) === 'AB              ' && rowN(4) === '');
  click(document.querySelector('[data-onclick="centerLines"]'));
  check('Center Lines centers each line in its row', row0() === '      HEXL      ' &&
    rowN(1) === '      "O🟥"      ' && rowN(2).trim() === '' && rowN(3) === '       AB       ');
  calls.length = 0;
  click(document.querySelector('[data-onclick="sync"]'));
  await sleep(20);
  const pushed = calls.find(c => c.url === '/update_playlist');
  check('PUSH sends the grid as one page of 64 flaps',
    pushed && Array.from(JSON.parse(pushed.body).pages[0].text).length === 64 &&
    JSON.parse(pushed.body).pages[0].text.startsWith('      HEXL      '));

  console.log('\n--- Editing a playlist page puts it back in the grid ---');
  document.getElementById('modeToggle').checked = true;
  change(document.getElementById('modeToggle'));
  click(document.getElementById('saveMsgBtn'));
  click(document.querySelector('[data-onclick="clearDisplay"]'));
  check('the grid clears', flapText().trim() === '');
  click(document.querySelector('#playlistList .playlist-item:last-child [data-onclick="editPlaylist"]'));
  check('EDIT restores the page into the grid', row0() === '      HEXL      ' && rowN(1) === '      "O🟥"      ');

  console.log('\n--- Degree and heart buttons ---');
  click(document.querySelector('#preview .flap-unit[data-cell="32"]'));
  document.querySelectorAll('#colorPalette .symbol-btn').forEach(click);
  check('the degree and heart buttons type their flaps at the cursor', rowN(2) === '°♥              ');

  console.log('\n--- The banner shows a playing playlist, with STOP ---');
  const banner = document.getElementById('live-banner');
  const bannerText = () => document.getElementById('liveBannerText').textContent;
  const live = MockEventSource.instances.find(s => s.url === '/current_state/stream');
  const snapshot = extra => ({ is_homed: true, state: ' '.repeat(64), active_app: null, playlist: null,
                               scheduled: false, hardware_connected: true, ...extra });
  live.emit(snapshot({ playlist: { name: null, page: 1, pages: 3 } }));
  check('an unsaved playlist shows its page', banner.classList.contains('visible') && bannerText() === '▶ Playlist · page 2 of 3');
  live.emit(snapshot({ playlist: { name: 'Morning', page: 0, pages: 2 }, scheduled: true }));
  check('a saved playlist shows its name, and that it was scheduled',
    bannerText() === '▶ Playlist "Morning" · page 1 of 2 (scheduled)');
  live.emit(snapshot({ playlist: { name: null, page: 0, pages: 1 } }));
  check('a single pushed page gets no banner (nothing is cycling)', !banner.classList.contains('visible'));
  live.emit(snapshot({ playlist: { name: 'Morning', page: 0, pages: 2 } }));
  calls.length = 0;
  click(banner.querySelector('[data-onclick="stopApp"]'));
  await sleep(20);
  check('STOP on a playlist posts /stop_app', calls.some(c => c.url === '/stop_app' && c.method === 'POST'));

  console.log('\n--- Simulation badge ---');
  const simBadge = document.getElementById('simBadge');
  check('no badge while the hardware is connected', simBadge.hidden);
  live.emit(snapshot({ hardware_connected: false }));
  check('the badge shows when the serial port is not open', !simBadge.hidden);
  live.emit(snapshot({}));
  check('and hides again once it is', simBadge.hidden);

  console.log('\n--- Saved playlists: edit in place ---');
  window.confirm = () => { throw new Error('unexpected confirm'); };
  const plName = document.getElementById('savePlaylistName');
  plName.value = 'Morning';
  calls.length = 0;
  click(document.querySelector('[data-onclick="saveCurrentPlaylist"]'));
  await sleep(50);
  check('a new name saves without asking', 'Morning' in savedPlaylists);
  check('the name stays in the box and the playlist is now the one being edited',
    plName.value === 'Morning' && !document.getElementById('loadedPlaylistNote').hidden &&
    document.querySelector('.saved-pl-item[data-name="Morning"]').classList.contains('loaded'));
  const pagesBefore = savedPlaylists.Morning.pages.length;
  click(document.querySelector('[data-onclick="clearDisplay"]'));   // stop editing a page...
  click(document.getElementById('saveMsgBtn'));                       // ...so this adds one
  click(document.querySelector('[data-onclick="saveCurrentPlaylist"]'));
  await sleep(50);
  check('saving again updates it without asking', savedPlaylists.Morning.pages.length === pagesBefore + 1);

  savedPlaylists.Evening = { pages: [{ text: 'EVE' }], delay: 5 };
  plName.value = 'Evening';
  let asked = null;
  window.confirm = msg => { asked = msg; return false; };
  click(document.querySelector('[data-onclick="saveCurrentPlaylist"]'));
  await sleep(50);
  check('saving over a different saved playlist asks first', asked === 'Replace the saved playlist "Evening"?');
  check('and declining leaves it alone', savedPlaylists.Evening.pages.length === 1);
  window.loadSavedPlaylists();   // as the page would after any change, to show Evening
  await sleep(50);

  calls.length = 0;
  click(document.querySelector('.saved-pl-item[data-name="Morning"] [data-onclick="runSavedPlaylist"]'));
  await sleep(50);
  check('Run plays the playlist by name', calls.some(c => c.url === '/playlists/Morning/run' && c.method === 'POST'));
  live.emit(snapshot({ playlist: { name: 'Morning', page: 0, pages: 2 } }));
  check('the playing saved playlist is highlighted',
    document.querySelector('.saved-pl-item[data-name="Morning"]').classList.contains('running') &&
    !document.querySelector('.saved-pl-item[data-name="Evening"]').classList.contains('running'));

  window.confirm = () => true;
  click(document.querySelector('.saved-pl-item[data-name="Evening"] [data-onclick="loadSavedPlaylist"]'));
  await sleep(50);
  check('Edit loads the playlist, its name and its pages',
    plName.value === 'Evening' && globalVar('loadedPlaylist') === 'Evening' &&
    document.querySelectorAll('#playlistList .playlist-item').length === 1 &&
    globalVar('editingIndex') === null);
  click(document.querySelector('.saved-pl-item[data-name="Evening"] [data-onclick="deleteSavedPlaylist"]'));
  await sleep(50);
  check('deleting the playlist being edited stops editing it',
    globalVar('loadedPlaylist') === null && document.getElementById('loadedPlaylistNote').hidden);

  console.log('\n--- The draft survives a reload ---');
  const draft = () => JSON.parse(window.localStorage.getItem('splitflap.controlDraft'));
  check('the playlist being built is kept in localStorage',
    draft().playlist.length === 1 && draft().multi === true && draft().name === 'Evening');
  document.getElementById('delayInput').value = '7.5';
  change(document.getElementById('delayInput'));
  check('changing a default updates the draft', draft().delay === '7.5');
  window.localStorage.setItem('splitflap.controlDraft', JSON.stringify({
    text: 'SAVED', playlist: [{ text: 'ONE' }, 'TWO', 42, null], multi: true, editing: 1,
    loaded: 'Morning', name: 'Morning', delay: '3', style: 'no-such-style', speed: '25' }));
  window.restoreDraft();
  check('restoring puts the grid back', row0() === 'SAVED           ');
  check('and the playlist, skipping anything that is not a page',
    globalVar('playlist').length === 2 && globalVar('playlist')[1].text === 'TWO' &&
    document.querySelectorAll('#playlistList .playlist-item').length === 2);
  check('and the page being edited and the saved playlist it came from',
    document.getElementById('saveMsgBtn').textContent === 'Save Changes to Page 2' &&
    globalVar('loadedPlaylist') === 'Morning');
  check('and the defaults, ignoring a style that no longer exists',
    document.getElementById('delayInput').value === '3' && document.getElementById('speedInput').value === '25' &&
    document.getElementById('styleInput').value !== '');
  window.localStorage.setItem('splitflap.controlDraft', '{not json');
  let restoreThrew = false;
  try { window.restoreDraft(); } catch (e) { restoreThrew = true; }
  check('an unreadable draft is ignored', !restoreThrew);

  console.log('\n--- Schedule ---');
  calls.length = 0;
  click(document.getElementById('tab-apps'));
  await sleep(30);
  check('opening Apps loads the schedule', calls.some(c => c.url === '/schedule' && c.method === 'GET'));
  const slots = () => document.querySelectorAll('#scheduleEntries .schedule-entry');
  check('each time slot is drawn, with its days', slots().length === 1 &&
    [...slots()[0].querySelectorAll('[data-day]')].map(b => b.checked).join() === 'true,true,true,true,true,false,false');
  const slotTarget = slots()[0].querySelector('[data-target]');
  check('a slot showing a deleted playlist keeps it, marked missing',
    slotTarget.value === 'playlist:Gone' && slotTarget.selectedOptions[0].textContent.includes('(missing)'));
  check('saved playlists are offered as targets', !!slotTarget.querySelector('option[value="playlist:Morning"]'));
  check('the default is chosen', document.getElementById('scheduleDefault').value === 'app:time');
  check('the status line names the display clock and what is scheduled now',
    document.getElementById('scheduleStatus').textContent === 'Display clock: Tue 14:05. Scheduled now: Time.');

  click(document.querySelector('[data-onclick="addScheduleEntry"]'));
  check('Add Time Slot adds a weekday slot', slots().length === 2);
  click(slots()[1].querySelector('[data-onclick="moveScheduleEntry"][data-dir="-1"]'));
  check('a slot can be moved up', slots()[0].querySelector('[data-target]').value === '');
  calls.length = 0;
  click(document.querySelector('[data-onclick="saveSchedule"]'));
  await sleep(20);
  check('a slot with nothing to show is refused, with the reason',
    [...document.querySelectorAll('.toast.error')].some(t => t.textContent.includes('needs something to show')));
  slots()[0].querySelector('[data-target]').value = 'app:weather';
  slots()[0].querySelector('[data-time="start"]').value = '22:00';
  slots()[0].querySelector('[data-time="end"]').value = '06:00';
  slots()[0].querySelector('[data-day="5"]').checked = true;
  click(slots()[1].querySelector('[data-onclick="removeScheduleEntry"]'));
  calls.length = 0;
  click(document.querySelector('[data-onclick="saveSchedule"]'));
  await sleep(20);
  const savedSchedule = calls.find(c => c.url === '/schedule' && c.method === 'POST');
  check('Save Schedule posts the form', savedSchedule && JSON.stringify(JSON.parse(savedSchedule.body)) === JSON.stringify({
    enabled: true, default: 'app:time',
    entries: [{ days: [0, 1, 2, 3, 4, 5], start: '22:00', end: '06:00', target: 'app:weather' }] }));

  console.log('\n--- Settings fields keep their types ---');
  const fieldBox = document.createElement('div');
  document.body.append(fieldBox);
  const typedFields = [
    { key: 'spd', label: 'Speed', type: 'number', default: '0.4', min: '0.1', max: '5' },
    { key: 'on', label: 'Enabled', type: 'checkbox' },
    { key: 'nm', label: 'Name', type: 'text' },
  ];
  fieldBox.append(...typedFields.map(f => window.buildField(f, { spd: 2, on: 'true', nm: 'x' }[f.key], 'tf_')));
  check('a checkbox field is a switch, on from a stored "true"', document.getElementById('tf_on').checked);
  document.getElementById('tf_spd').value = '1.5';
  check('numbers are read as numbers and checkboxes as true/false',
    JSON.stringify(window.readFieldValues(typedFields, 'tf_')) === '{"spd":1.5,"on":true,"nm":"x"}');
  document.getElementById('tf_spd').value = '';
  check('a blank number is sent blank (the backend uses the default)', window.readFieldValues(typedFields, 'tf_').spd === '');
  fieldBox.remove();

  console.log('\n--- Playlist: duplicate, show one page, drag, checked values ---');
  click(document.getElementById('tab-control'));
  await sleep(20);
  window.eval(`playlist = [{text: 'AAA', delay: 2, style: 'ltr', speed: 15},
                           {text: 'BBB', delay: 3, style: 'rtl', speed: 15}]`);
  window.stopEditing();
  window.renderPlaylist();
  const plRows = () => [...document.querySelectorAll('#playlistList .playlist-item')];
  const plTexts = () => globalVar('playlist').map(p => p.text).join();
  click(plRows()[0].querySelector('[data-onclick="duplicatePlaylistPage"]'));
  check('⧉ puts a copy right after the page', plTexts() === 'AAA,AAA,BBB' &&
    globalVar('playlist')[0] !== globalVar('playlist')[1]);

  calls.length = 0;
  click(plRows()[2].querySelector('[data-onclick="pushPlaylistPage"]'));
  await sleep(20);
  const onePage = calls.find(c => c.url === '/update_playlist');
  check('▶ shows just that page, with its delay as a number', onePage &&
    JSON.parse(onePage.body).pages.length === 1 && JSON.parse(onePage.body).pages[0].text === 'BBB' &&
    JSON.parse(onePage.body).delay === 3);

  click(plRows()[0].querySelector('[data-onclick="editPlaylist"]'));   // page 1 is being edited
  // Lay the rows out 100px apart, as a browser would.
  plRows().forEach((row, i) => { row.getBoundingClientRect = () => ({ top: i * 100, height: 100 }); });
  const pointer = (target, type, clientY) =>
    target.dispatchEvent(new window.MouseEvent(type, { bubbles: true, clientY, button: 0 }));
  pointer(plRows()[0].querySelector('.drag-handle'), 'pointerdown', 50);
  check('the dragged row is marked', plRows()[0].classList.contains('dragging'));
  pointer(document, 'pointermove', 260);
  pointer(document, 'pointerup', 260);
  check('dragging a page to the bottom moves it there', plTexts() === 'AAA,BBB,AAA' && !document.querySelector('.dragging'));
  check('the page being edited stays the one being edited',
    globalVar('editingIndex') === 2 && document.getElementById('saveMsgBtn').textContent === 'Save Changes to Page 3');
  click(plRows()[1].querySelector('[data-onclick="movePlaylist"][data-dir="-1"]'));
  check('▲ still moves a page up', plTexts() === 'BBB,AAA,AAA' && globalVar('editingIndex') === 2);
  click(plRows()[2].querySelector('[data-onclick="removeFromPlaylist"]'));
  check('removing the page being edited stops editing', globalVar('editingIndex') === null && plTexts() === 'BBB,AAA');

  const delayBox = plRows()[0].querySelector('[data-field="delay"]');
  delayBox.value = '0';
  change(delayBox);
  check('a delay out of range is refused and put back', delayBox.value === '3' && globalVar('playlist')[0].delay === 3 &&
    [...document.querySelectorAll('.toast.warn')].some(t => t.textContent === 'Delay must be from 0.5 to 60'));
  const speedBox = plRows()[0].querySelector('[data-field="speed"]');
  speedBox.value = '20';
  change(speedBox);
  check('a good value is kept as a number', globalVar('playlist')[0].speed === 20);

  document.getElementById('delayInput').value = '4';
  calls.length = 0;
  click(document.querySelector('[data-onclick="sync"]'));
  await sleep(20);
  check('PUSH sends the default delay as a number', JSON.parse(calls.find(c => c.url === '/update_playlist').body).delay === 4);

  const summary = window.playlistSummary;
  check('saved playlists sum up their pages', summary({ pages: [{ delay: 2 }, { delay: 8 }, {}], delay: 5 }) === '3 pages · 2–8 s' &&
    summary({ pages: [{}, 'X'], delay: '5' }) === '2 pages · 5 s each' && summary({ pages: [{}], delay: 5 }) === '1 page · 5 s' &&
    summary({ pages: [], delay: 5 }) === '0 pages');

  console.log('\n--- Home All is a POST ---');
  click(document.getElementById('tab-modules'));
  await sleep(30);
  window.confirm = () => true;
  calls.length = 0;
  click(document.querySelector('[data-onclick="homeAll"]'));
  await sleep(20);
  check('Home All posts to /home_all', calls.some(c => c.url === '/home_all' && c.method === 'POST'));

  console.log('\n--- Settings saved elsewhere reload the Modules page ---');
  live.emit(snapshot({ settings_version: 5 }));
  await sleep(10);
  calls.length = 0;
  live.emit(snapshot({ settings_version: 6 }));
  live.emit(snapshot({ settings_version: 7 }));   // a burst: one reload
  await sleep(400);
  check('a new settings version reloads the module data and shared settings, once',
    calls.filter(c => c.url === '/settings').length === 1 && calls.filter(c => c.url === '/firmware_config').length === 1);
  check('and the saved playlists', calls.some(c => c.url === '/playlists'));
  const fwInput = document.querySelector('#firmwareSettings input[type="number"]');
  fwInput.value = '1234';
  fwInput.dispatchEvent(new window.Event('input', { bubbles: true }));
  calls.length = 0;
  live.emit(snapshot({ settings_version: 8 }));
  await sleep(400);
  check('shared settings being edited are not overwritten',
    calls.some(c => c.url === '/settings') && !calls.some(c => c.url === '/firmware_config') && fwInput.value === '1234');
  calls.length = 0;
  click(document.getElementById('tab-control'));
  live.emit(snapshot({ settings_version: 9 }));
  await sleep(400);
  check('with the Modules page closed, nothing of it is reloaded', !calls.some(c => c.url === '/settings'));

  console.log('\n--- Sync progress on the module grid ---');
  click(document.getElementById('tab-modules'));
  await sleep(30);
  const cell = id => document.querySelector(`#modMatrix .mod-cell[data-id="${id}"]`);
  const syncSnap = sync => snapshot({ settings_version: 9, sync });
  live.emit(syncSnap({ running: false, ok: { '2': 1 }, failed: [] }));
  check('a success from before the page loaded does not flash', !cell(2).classList.contains('sync-flash'));
  live.emit(syncSnap({ running: true, ok: { '2': 1 }, failed: [] }));
  const syncBtn = document.getElementById('syncAllBtn');
  check('while a sync runs its button says so and is disabled', syncBtn.disabled && syncBtn.textContent === 'SYNCING…');
  live.emit(syncSnap({ running: true, ok: { '2': 1, '0': 2 }, failed: [] }));
  check('a module that syncs flashes green', cell(0).classList.contains('sync-flash') && !cell(2).classList.contains('sync-flash'));
  live.emit(syncSnap({ running: true, ok: { '2': 1, '0': 2 }, failed: [3] }));
  check('a module that fails turns orange', cell(3).classList.contains('sync-failed') && !cell(0).classList.contains('sync-failed'));
  await sleep(200);
  window.renderModuleGrid();
  check('a redrawn cell carries on its flash from where it was',
    cell(0).classList.contains('sync-flash') && parseFloat(cell(0).style.animationDelay) <= -150);
  live.emit(syncSnap({ running: false, ok: { '2': 1, '0': 2 }, failed: [3] }));
  check('the button comes back when the sync ends', !syncBtn.disabled && syncBtn.textContent === 'SYNC ALL (EEPROM)');
  click(cell(3));
  check('the failed module\'s inspector says Sync failed', !document.getElementById('inspectSyncFailed').hidden &&
    document.getElementById('inspectSyncFailed').textContent.includes('Sync failed'));
  click(cell(0));
  check('a module that synced does not', document.getElementById('inspectSyncFailed').hidden);
  await sleep(1100);
  live.emit(syncSnap({ running: false, ok: { '2': 1, '0': 2 }, failed: [3] }));
  check('the flash ends; the failure stays orange', !cell(0).classList.contains('sync-flash') && cell(3).classList.contains('sync-failed'));
  live.emit(syncSnap({ running: false, ok: { '2': 1, '0': 2, '3': 3 }, failed: [] }));
  check('a failed module that syncs again flashes green and is no longer orange',
    cell(3).classList.contains('sync-flash') && !cell(3).classList.contains('sync-failed'));
  window.confirm = () => true;
  click(syncBtn);
  await sleep(30);
  check('Sync All ends with a summary naming the failures',
    [...document.querySelectorAll('.toast.warn')].some(t => t.textContent === '1 synced; sync failed for 03'));

  console.log('\n--- Install as an app ---');
  const installBtn = document.getElementById('installBtn');
  check('no Install button until the browser offers it', installBtn.hidden);
  let prompted = false;
  const offer = new window.Event('beforeinstallprompt', { cancelable: true });
  offer.prompt = () => { prompted = true; };
  offer.userChoice = Promise.resolve({ outcome: 'accepted' });
  window.dispatchEvent(offer);
  check('the button shows when it does, instead of the browser banner', !installBtn.hidden && offer.defaultPrevented);
  click(installBtn);
  await sleep(10);
  check('it opens the browser\'s install prompt, then goes', prompted && installBtn.hidden);

  console.log('\n--- Accessibility ---');
  const keydown = (target, k, opts = {}) =>
    target.dispatchEvent(new window.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...opts }));
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  click(document.getElementById('tab-control'));
  check('tabs say which is selected, and only it is in the Tab order',
    tabs.map(t => `${t.getAttribute('aria-selected')}/${t.tabIndex}`).join() === 'true/0,false/-1,false/-1,false/-1');
  check('each tab has a plain name and controls its page',
    tabs.map(t => t.getAttribute('aria-label')).join() === 'Control,Apps,Modules,Debug' &&
    tabs.every(t => document.getElementById(t.getAttribute('aria-controls')).getAttribute('role') === 'tabpanel'));
  tabs[0].focus();
  keydown(tabs[0], 'ArrowLeft');
  check('ArrowLeft from the first tab wraps to the last, and opens it',
    document.activeElement === tabs[3] && document.getElementById('page-debug').classList.contains('active'));
  keydown(tabs[3], 'Home');
  check('Home goes back to the first tab', document.activeElement === tabs[0] && tabs[0].getAttribute('aria-selected') === 'true');

  live.emit(snapshot({ is_homed: true, state: 'HELLO'.padEnd(16) + ' '.repeat(16) + 'WORLD'.padEnd(32) }));
  check('screen readers get the display as text, row by row',
    document.getElementById('liveDisplay').getAttribute('aria-label') === 'The display shows: HELLO / WORLD');
  live.emit(snapshot({ is_homed: false, state: ' '.repeat(64) }));
  check('and hear when it needs homing',
    document.getElementById('liveDisplay').getAttribute('aria-label') === 'Homing required. The display is blank');
  check('the flaps themselves are hidden from them', document.getElementById('liveGrid').getAttribute('aria-hidden') === 'true');

  click(document.querySelector('[data-onclick="clearDisplay"]'));
  click(document.querySelector('#preview .flap-unit[data-cell="17"]'));
  typeKeys('hi');
  check('the composer says where the cursor is and what the row says',
    document.getElementById('composeWhere').textContent === 'Row 2 of 4, column 4. Row 2: HI');

  {
    window.showToast('Boom', 'error');
    window.showToast('Fine');
    const toasts = [...document.querySelectorAll('#toastContainer .toast')].slice(-2);
    check('an error toast interrupts; others are read politely',
      toasts[0].getAttribute('role') === 'alert' && !toasts[1].hasAttribute('role') &&
      document.getElementById('toastContainer').getAttribute('aria-live') === 'polite');
  }

  check('playlist buttons name the page they act on',
    !!document.querySelector('#playlistList [aria-label="Move page 1 down"]') &&
    !!document.querySelector('#playlistList [aria-label="Page 1 delay in seconds"]') &&
    document.querySelector('#playlistList .drag-handle').getAttribute('aria-hidden') === 'true');
  calls.length = 0;
  const firstDown = document.querySelector('#playlistList [aria-label="Move page 1 down"]');
  click(firstDown);
  check('moving a page keeps focus on its button in the new place',
    document.activeElement === document.querySelector('#playlistList [aria-label="Move page 2 down"]'));

  click(document.getElementById('tab-modules'));
  await sleep(30);
  const modCell = id => document.querySelector(`#modMatrix .mod-cell[data-id="${id}"]`);
  click(modCell(0));
  check('module cells are buttons; only the selected one is in the Tab order',
    modCell(0).tagName === 'BUTTON' && modCell(0).tabIndex === 0 && modCell(1).tabIndex === -1 &&
    modCell(0).getAttribute('aria-current') === 'true');
  check('a cell says its state', modCell(1).getAttribute('aria-label') === 'Module 01, not set up' &&
    modCell(3).getAttribute('aria-label') === 'Module 03');
  keydown(modCell(0), 'ArrowDown');
  check('arrow keys move the selection round the grid', globalVar('selectedModule') === 16 && document.activeElement === modCell(16));
  keydown(modCell(16), 'ArrowLeft');
  keydown(modCell(15), 'Home');
  check('Home goes to the first module', globalVar('selectedModule') === 0 && document.activeElement === modCell(0));

  click(document.getElementById('tab-apps'));
  await sleep(30);
  const gearBtn = document.querySelector('.app-card[data-app="weather"] .app-gear');
  check('the settings button is named for its app, beside the run button (not inside it)',
    gearBtn.getAttribute('aria-label') === 'Weather settings' && !gearBtn.closest('.app-run'));
  live.emit(snapshot({ active_app: 'weather' }));
  check('the running app says so to screen readers',
    document.querySelector('.app-card[data-app="weather"] .app-run').textContent.includes('(running)'));
  gearBtn.focus();
  click(gearBtn);
  await sleep(30);
  const modal = document.getElementById('appSettingsModal');
  check('the settings dialog takes focus and makes the page behind inert',
    modal.contains(document.activeElement) && document.querySelector('.container').inert === true);
  const modalButtons = [...modal.querySelectorAll('button')];
  modalButtons[modalButtons.length - 1].focus();
  keydown(modalButtons[modalButtons.length - 1], 'Tab');
  check('Tab from its last control goes round to its first', document.activeElement === document.getElementById('asf_zip_code'));
  keydown(document.activeElement, 'Escape');
  check('Escape closes it and puts focus back on the ⚙️ button',
    modal.style.display === 'none' && document.activeElement === gearBtn && !document.querySelector('.container').inert);
  click(gearBtn);
  await sleep(30);
  modal.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  check('a click on the backdrop closes it too', modal.style.display === 'none');

  check('every switch is labelled by its name', [...document.querySelectorAll('input[role="switch"]')].every(input =>
    document.querySelector(`label[for="${input.id}"]`) || input.closest('.toggle-row').querySelector('label.field-label')));

  console.log('\n--- Unrecognised choices and the restore report ---');
  const tzBox = document.createElement('div');
  document.body.append(tzBox);
  tzBox.append(window.buildField({ key: 'tz', label: 'Timezone', type: 'select', opts: ['UTC', 'US/Eastern'] }, 'EST', 'tzf_'));
  const tzSelect = document.getElementById('tzf_tz');
  check('a stored value that is not a choice is shown as not recognised, not swapped for the first choice',
    tzSelect.value === 'EST' && tzSelect.selectedOptions[0].textContent === 'EST (not recognised)');
  tzBox.remove();

  click(document.getElementById('tab-modules'));
  await sleep(30);
  const backupInput = document.getElementById('backupFile');
  const file = { text: async () => JSON.stringify({ version: 4, modules: {} }) };
  Object.defineProperty(backupInput, 'files', { value: [file], configurable: true });
  window.confirm = () => true;
  change(backupInput);
  await sleep(40);
  const report = document.getElementById('restoreReport');
  check('a restore says what came back and what was skipped, and why',
    !report.hidden && report.textContent.includes('Restored: 2 modules, the schedule.') &&
    report.querySelector('li').textContent === 'Timezone must be one of: ...' && report.classList.contains('warning'));

  console.log('\n--- Blank the display ---');
  live.emit(snapshot({ blank: true, scheduled: true }));
  check('a blanked display says so in the banner, with no STOP',
    document.getElementById('liveBannerText').textContent === '■ The display is blanked (scheduled)' &&
    document.querySelector('#live-banner .aab-stop').hidden);
  live.emit(snapshot({ active_app: 'weather' }));
  check('STOP comes back for anything else', !document.querySelector('#live-banner .aab-stop').hidden);
  click(document.getElementById('tab-apps'));
  await sleep(40);
  const defaultSelect = document.getElementById('scheduleDefault');
  check('the schedule can blank the display', !!defaultSelect.querySelector('option[value="blank"]') &&
    window.targetLabel('blank') === 'a blank display');

  console.log('\n--- Undo ---');
  const undoToasts = () => [...document.querySelectorAll('.toast.has-action')];
  const lastUndo = () => undoToasts().slice(-1)[0];
  click(document.querySelector('[data-onclick="addScheduleEntry"]'));
  const slotCount = document.querySelectorAll('.schedule-entry').length;
  const lastSlot = [...document.querySelectorAll('.schedule-entry')].slice(-1)[0];
  click(lastSlot.querySelector('[data-onclick="removeScheduleEntry"]'));
  check('removing a time slot offers Undo', document.querySelectorAll('.schedule-entry').length === slotCount - 1 &&
    lastUndo().textContent.includes('Time slot removed'));
  click(lastUndo().querySelector('.toast-action'));
  check('Undo puts the slot back where it was', document.querySelectorAll('.schedule-entry').length === slotCount &&
    [...document.querySelectorAll('.schedule-entry')].slice(-1)[0] === lastSlot);

  click(document.getElementById('tab-control'));
  await sleep(20);
  window.eval(`playlist = [{text: 'ONE', delay: 5, style: 'ltr', speed: 15}, {text: 'TWO', delay: 5, style: 'ltr', speed: 15}]`);
  window.stopEditing();
  window.renderPlaylist();
  click(document.querySelector('#playlistList .playlist-item[data-idx="0"] [data-onclick="removeFromPlaylist"]'));
  check('removing a page offers Undo', globalVar('playlist').map(p => p.text).join() === 'TWO' && lastUndo().textContent.includes('Page 1 removed'));
  const pageToast = lastUndo();
  await sleep(20);   // let it finish appearing
  document.body.focus();
  document.body.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'z', ctrlKey: true, bubbles: true, cancelable: true }));
  check('Ctrl+Z undoes it: the page is back in its place', globalVar('playlist').map(p => p.text).join() === 'ONE,TWO');
  check('and the Undo toast goes', globalVar('latestUndo') === null && !pageToast.classList.contains('show'));

  click(document.querySelector('#preview .flap-unit[data-cell="0"]'));
  typeKeys('keep');
  click(document.querySelector('[data-onclick="clearDisplay"]'));
  check('Clear offers Undo', row0().trim() === '' && lastUndo().textContent.includes('Grid cleared'));
  click(lastUndo().querySelector('.toast-action'));
  check('which brings the grid back', row0().startsWith('KEEP'));

  savedPlaylists.Evening = { pages: [{ text: 'EVE' }], delay: 6 };
  await window.loadSavedPlaylists();
  window.confirm = () => { throw new Error('no confirm any more'); };
  calls.length = 0;
  click(document.querySelector('.saved-pl-item[data-name="Evening"] [data-onclick="deleteSavedPlaylist"]'));
  await sleep(50);
  check('deleting a saved playlist needs no confirm, and offers Undo',
    !('Evening' in savedPlaylists) && lastUndo().textContent.includes('Deleted "Evening"'));
  click(lastUndo().querySelector('.toast-action'));
  await sleep(50);
  check('Undo saves it again, as it was', savedPlaylists.Evening &&
    JSON.stringify(savedPlaylists.Evening) === JSON.stringify({ pages: [{ text: 'EVE' }], delay: 6 }) &&
    !!document.querySelector('.saved-pl-item[data-name="Evening"]'));

  console.log('\n--- Renaming a saved playlist ---');
  click(document.querySelector('.saved-pl-item[data-name="Evening"] [data-onclick="startRenamePlaylist"]'));
  const renameBox = document.querySelector('.saved-pl-rename');
  check('Rename turns the name into a box, focused', !!renameBox && document.activeElement === renameBox && renameBox.value === 'Evening');
  renameBox.value = 'Morning';
  renameBox.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  await sleep(50);
  check('a name that is taken is refused, and the box stays', 'Evening' in savedPlaylists && !!document.querySelector('.saved-pl-rename') &&
    [...document.querySelectorAll('.toast.error')].some(t => t.textContent.includes('already a playlist called "Morning"')));
  const box2 = document.querySelector('.saved-pl-rename');
  box2.value = 'Night';
  box2.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  await sleep(60);
  check('Enter renames it, keeping its place, and says the schedule follows',
    Object.keys(savedPlaylists).indexOf('Night') >= 0 && !('Evening' in savedPlaylists) &&
    [...document.querySelectorAll('.toast')].some(t => t.textContent === 'Renamed to "Night"; the schedule follows it') &&
    document.activeElement === document.querySelector('.saved-pl-item[data-name="Night"] [data-onclick="startRenamePlaylist"]'));
  click(document.querySelector('.saved-pl-item[data-name="Night"] [data-onclick="loadSavedPlaylist"]'));
  await sleep(50);
  click(document.querySelector('.saved-pl-item[data-name="Night"] [data-onclick="startRenamePlaylist"]'));
  const box3 = document.querySelector('.saved-pl-rename');
  box3.value = 'Late';
  box3.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  await sleep(60);
  check('renaming the playlist being edited carries the editor along',
    globalVar('loadedPlaylist') === 'Late' && document.getElementById('savePlaylistName').value === 'Late');
  click(document.querySelector('.saved-pl-item[data-name="Late"] [data-onclick="startRenamePlaylist"]'));
  document.querySelector('.saved-pl-rename').dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
  check('Escape cancels', !document.querySelector('.saved-pl-rename') && !!document.querySelector('.saved-pl-item[data-name="Late"]'));

  console.log('\n--- Preview ---');
  document.getElementById('modeToggle').checked = false;
  change(document.getElementById('modeToggle'));
  click(document.querySelector('[data-onclick="clearDisplay"]'));
  click(document.querySelector('#preview .flap-unit[data-cell="0"]'));
  typeKeys('ab');
  document.getElementById('speedInput').value = '300';
  live.emit(snapshot({ state: ' '.repeat(64) }));
  const previewBtn = document.getElementById('previewBtn');
  calls.length = 0;
  click(previewBtn);
  check('Preview starts: the grid says so, and nothing is sent',
    document.getElementById('composeWrapper').classList.contains('previewing') &&
    previewBtn.getAttribute('aria-pressed') === 'true' && calls.length === 0);
  await sleep(180);
  check('flaps start in the transition\'s order, a speed apart: the first has turned, the second not yet', row0().startsWith('A '));
  await sleep(400);
  check('then the next turns, through the reel, to its character', row0().startsWith('AB'));
  click(previewBtn);
  check('Stop preview puts the page back, ending the preview',
    !document.getElementById('composeWrapper').classList.contains('previewing') && row0().startsWith('AB') &&
    previewBtn.textContent === '▷ Preview');
  live.emit(snapshot({ state: 'Z'.repeat(64) }));
  click(previewBtn);
  await sleep(40);
  check('a preview starts from what the display shows now', row0().startsWith('ZZ'));
  key('ArrowRight');
  check('typing (or any key in the grid) ends it', !document.getElementById('composeWrapper').classList.contains('previewing') &&
    row0().startsWith('AB'));

  console.log('\n--- Every page sent shows in the serial log ---');
  const logStream = MockEventSource.instances.find(s => s.url === '/serial_log/stream');
  const serialLines = () => [...document.querySelectorAll('#debugLog .debug-log-line')];
  const pairsFor = text => Array.from(text.padEnd(64)).map((ch, i) => ch + String.fromCharCode(33 + i)).join('');
  logStream.emit({ msg: 'SIMULATED SENT: m*f21:' + pairsFor('HELLO'.padEnd(16) + 'WORLD') });
  const frameLine = serialLines().slice(-1)[0];
  check('a frame broadcast is shown with what it puts on the display',
    frameLine.classList.contains('sent') &&
    frameLine.querySelector('.log-note').textContent === ' → page "HELLO / WORLD", modules 21 ms apart');
  logStream.emit({ msg: 'SENT: m05h' });
  check('other messages are shown as they are', !serialLines().slice(-1)[0].querySelector('.log-note'));
  logStream.emit({ msg: 'NOT SENT (serial lost): m00-A' });
  check('a message that did not reach the bus stands out', serialLines().slice(-1)[0].classList.contains('lost'));
  let logThrew = false;
  try { logStream.emitRaw('{not json'); } catch (e) { logThrew = true; }
  logStream.emit({ msg: 'SENT: m06h' });
  check('a bad log message is skipped, and the log carries on', !logThrew && serialLines().slice(-1)[0].textContent.endsWith('SENT: m06h'));

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('Test harness crashed:', err);
  process.exit(1);
});
