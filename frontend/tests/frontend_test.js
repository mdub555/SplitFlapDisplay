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
  check('compose grid built with a flap per module', document.querySelectorAll('#preview .flap-unit').length === 64);
  check('color palette built', document.querySelectorAll('#colorPalette .color-btn').length === 8);
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
    document.getElementById('live-app-name').textContent === 'Weather');

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
    fw('debounceMs').value === '100' && fw('recalculateHome').checked === true);
  check('input ranges come from the backend limits',
    fw('debounceMs').min === '0' && fw('debounceMs').max === '65535' && fw('stepDelayUs').min === '1' &&
    fw('stepDelayUs').max === '65535');

  calls.length = 0;
  fw('stepDelayUs').value = '1250';
  fw('debounceMs').value = '150';
  fw('recalculateHome').checked = false;
  click(document.querySelector('[data-onclick="applyFirmwareConfig"]'));
  await sleep(20);
  const fwPost = calls.find(c => c.url === '/firmware_config' && c.method === 'POST');
  check('apply posts to /firmware_config', !!fwPost);
  check('apply sends every setting with real numbers and a real boolean',
    fwPost && JSON.stringify(JSON.parse(fwPost.body)) ===
      JSON.stringify({ stepDelayUs: 1250, homingStepDelayUs: 1800, debounceMs: 150, recalculateHome: false,
                       rampStartDelayUs: 3000, rampSteps: 0, settleMs: 0, staggerMs: 150 }));

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

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('Test harness crashed:', err);
  process.exit(1);
});
