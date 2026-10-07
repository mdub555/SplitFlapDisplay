// Every function here resolves — never rejects. On any failure (network
// error, non-2xx response, or a bad JSON body) it logs details to the
// console, shows a toast using the backend's message if one was provided,
// and resolves to null. Callers only ever need one guard:
//
//   api.someCall().then(result => {
//     if (!result) return;   // failure — toast already shown
//     ...
//   });
//
// Pass `errorMessage: null` to suppress the toast for a call that's expected
// to fail transiently and retry on its own — the failure is still logged to
// console either way.
async function apiFetchJson(url, options, errorMessage) {
  let res;
  try {
    res = await fetch(url, options);
  } catch (err) {
    console.error(`Network error calling ${url}:`, err);
    if (errorMessage) showToast(errorMessage, 'error');
    return null;
  }

  let data = null;
  try {
    data = await res.json();
  } catch (err) {
    // Empty or non-JSON body. Fine for a 2xx with no content; a problem if
    // paired with a non-ok status below.
  }

  if (!res.ok) {
    const detail = (data && data.message) ? `: ${data.message}` : ` (${res.status})`;
    console.error(`API error from ${url}${detail}`);
    if (errorMessage) showToast(`${errorMessage}${detail}`, 'error');
    return null;
  }

  return data;
}

// A GET, or a POST with an optional JSON body. `errorMessage` starts the
// toast shown if the call fails.
const apiGet = (url, errorMessage) => apiFetchJson(url, {}, errorMessage);
const apiPost = (url, body, errorMessage) => apiFetchJson(url, body === undefined ? {method: 'POST'} : {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
}, errorMessage);

const api = {
  // Live state arrives over /current_state/stream (see startLiveUpdates in
  // live-flap.js) rather than through a call here.
  apps:               () => apiGet('/apps', 'Could not load app list'),
  saveAppSettings:    (key, data) => apiPost(`/apps/${key}/settings`, data, 'Could not save app settings'),
  runApp:             (key) => apiPost('/run_app', {app: key}, 'Could not start app'),
  stopApp:            () => apiPost('/stop_app', undefined, 'Could not stop'),

  globalFields:       () => apiGet('/global_fields', 'Could not load settings fields'),
  getSettings:        () => apiGet('/settings', 'Could not load settings'),
  saveGlobalSettings: (data) => apiPost('/settings', data, 'Could not save settings'),

  updatePlaylist:     (pages, delay) => apiPost('/update_playlist', {pages, delay}, 'Could not push to display'),
  playlists:          () => apiGet('/playlists', 'Could not load saved playlists'),
  savePlaylist:       (name, pages, delay) => apiPost('/playlists', {name, pages, delay}, 'Could not save playlist'),
  deletePlaylist:     (name) => apiFetchJson(`/playlists/${encodeURIComponent(name)}`, {method: 'DELETE'},
                                             'Could not delete playlist'),
  runPlaylist:        (name) => apiPost(`/playlists/${encodeURIComponent(name)}/run`, undefined,
                                        'Could not run playlist'),

  schedule:           () => apiGet('/schedule', 'Could not load the schedule'),
  saveSchedule:       (data) => apiPost('/schedule', data, 'Could not save the schedule'),

  adjustOffset:       (modId, delta) => apiPost(`/modules/${modId}/adjust`, {delta}, 'Could not adjust offset'),
  homeModule:         (modId) => apiPost(`/modules/${modId}/home`, undefined, 'Could not home module'),
  identifyModule:     (modId) => apiPost(`/modules/${modId}/identify`, undefined, 'Could not identify module'),
  exerciseModule:     (modId, cycles) => apiPost(`/modules/${modId}/exercise`, {cycles}, 'Could not start exercise'),
  stopModule:         (modId) => apiPost(`/modules/${modId}/stop`, undefined, 'Could not stop module'),
  rebootModule:       (modId) => apiPost(`/modules/${modId}/reboot`, undefined, 'Could not reboot module'),
  resetModuleSettings:(modId) => apiPost(`/modules/${modId}/reset_settings`, undefined, 'Could not reset module settings'),
  calibrateModule:    (modId) => apiPost(`/modules/${modId}/calibrate`, undefined, 'Calibration failed'),
  syncModule:         (modId) => apiPost(`/modules/${modId}/sync`, undefined, 'Sync failed'),
  syncAllModules:     () => apiPost('/modules/sync_all', undefined, 'Sync failed'),
  setModuleSetting:   (modId, setting, value) => apiPost(`/modules/${modId}/setting`, {setting, value},
                                                      'Could not update module setting'),
  setTotalSteps:      (modId, steps) => apiPost(`/modules/${modId}/total_steps`, {steps}, 'Could not set total steps'),
  showOnModule:       (modId, payload) => apiPost(`/modules/${modId}/display`, payload, 'Could not update module display'),
  gotoStep:           (modId, step) => apiPost(`/modules/${modId}/goto_step`, {step}, 'Could not move module'),
  homeAll:            () => apiPost('/home_all', undefined, 'Could not home all modules'),
  provisionModule:    (id) => apiPost('/provision_module', {id}, 'Could not provision module'),

  firmwareConfig:     () => apiGet('/firmware_config', 'Could not load firmware settings'),
  saveFirmwareConfig: (values) => apiPost('/firmware_config', values, 'Could not apply firmware settings'),

  backupSettings:     () => apiGet('/backup_settings', 'Could not generate backup'),
  restoreSettings:    (data) => apiPost('/restore_settings', data, 'Restore failed'),

  serialSend:         (cmd) => apiPost('/serial/send', {cmd}, 'Could not send serial command'),
};
