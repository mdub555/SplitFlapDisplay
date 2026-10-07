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
// console either way. (No current caller needs this, but the option's kept
// since live state used to be one before it moved to the SSE stream below.)
//
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

const jsonHeaders = {'Content-Type': 'application/json'};

const api = {
  config:             () => apiFetchJson('/config', {}, 'Could not load configuration'),
  // Live state now arrives over /current_state/stream (see live-flap.js's
  // startLiveUpdates) instead of being polled — no api.currentState() wrapper
  // needed here anymore.

  apps:               () => apiFetchJson('/apps', {}, 'Could not load app list'),
  saveAppSettings:    (key, data) => apiFetchJson(`/apps/${key}/settings`, {
    method:'POST', headers: jsonHeaders, body: JSON.stringify(data)
  }, 'Could not save app settings'),
  runApp:             (key) => apiFetchJson('/run_app', {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({app:key})
  }, 'Could not start app'),
  stopApp:            () => apiFetchJson('/stop_app', {method:'POST'}, 'Could not stop app'),

  globalFields:       () => apiFetchJson('/global_fields', {}, 'Could not load settings fields'),
  getSettings:        () => apiFetchJson('/settings', {}, 'Could not load settings'),
  saveGlobalSettings: (data) => apiFetchJson('/settings', {
    method:'POST', headers: jsonHeaders, body: JSON.stringify(data)
  }, 'Could not save settings'),
  toggleAutoHome:     (enabled) => apiFetchJson('/toggle_autohome', {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({enabled})
  }, 'Could not update auto-home'),

  updatePlaylist:     (pages, delay) => apiFetchJson('/update_playlist', {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({pages, delay})
  }, 'Could not push to display'),

  playlists:          () => apiFetchJson('/playlists', {}, 'Could not load saved playlists'),
  savePlaylist:       (name, pages, delay) => apiFetchJson('/playlists', {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({name, pages, delay})
  }, 'Could not save playlist'),
  deletePlaylist:     (name) => apiFetchJson(`/playlists/${encodeURIComponent(name)}`, {method:'DELETE'}, 'Could not delete playlist'),

  adjustOffset:       (modId, delta) => apiFetchJson(`/modules/${modId}/adjust`, {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({delta})
  }, 'Could not adjust offset'),
  homeModule:         (modId) => apiFetchJson(`/modules/${modId}/home`, {method:'POST'}, 'Could not home module'),
  identifyModule:     (modId) => apiFetchJson(`/modules/${modId}/identify`, {method:'POST'}, 'Could not identify module'),
  exerciseModule:     (modId, cycles) => apiFetchJson(`/modules/${modId}/exercise`, {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({cycles})
  }, 'Could not start exercise'),
  stopModule:         (modId) => apiFetchJson(`/modules/${modId}/stop`, {method:'POST'}, 'Could not stop module'),
  rebootModule:       (modId) => apiFetchJson(`/modules/${modId}/reboot`, {method:'POST'}, 'Could not reboot module'),
  resetModuleSettings:(modId) => apiFetchJson(`/modules/${modId}/reset_settings`, {method:'POST'}, 'Could not reset module settings'),
  calibrateModule:    (modId) => apiFetchJson(`/modules/${modId}/calibrate`, {method:'POST'}, 'Calibration failed'),
  syncModule:         (modId) => apiFetchJson(`/modules/${modId}/sync`, {method:'POST'}, 'Sync failed'),
  syncAllModules:     () => apiFetchJson('/modules/sync_all', {method:'POST'}, 'Sync failed'),
  setModuleSetting:   (modId, setting, value) => apiFetchJson(`/modules/${modId}/setting`, {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({setting, value})
  }, 'Could not update module setting'),
  setTotalSteps:      (modId, steps) => apiFetchJson(`/modules/${modId}/total_steps`, {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({steps})
  }, 'Could not set total steps'),
  showOnModule:       (modId, payload) => apiFetchJson(`/modules/${modId}/display`, {
    method:'POST', headers: jsonHeaders, body: JSON.stringify(payload)
  }, 'Could not update module display'),
  gotoStep:           (modId, step) => apiFetchJson(`/modules/${modId}/goto_step`, {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({step})
  }, 'Could not move module'),
  homeAll:            () => apiFetchJson('/home_all', {}, 'Could not home all modules'),

  firmwareConfig:     () => apiFetchJson('/firmware_config', {}, 'Could not load firmware settings'),
  saveFirmwareConfig: (values) => apiFetchJson('/firmware_config', {
    method:'POST', headers: jsonHeaders, body: JSON.stringify(values)
  }, 'Could not apply firmware settings'),

  backupSettings:     () => apiFetchJson('/backup_settings', {}, 'Could not generate backup'),
  restoreSettings:    (data) => apiFetchJson('/restore_settings', {
    method:'POST', headers: jsonHeaders, body: JSON.stringify(data)
  }, 'Restore failed'),
  provisionModule:    (id) => apiFetchJson('/provision_module', {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({id})
  }, 'Could not provision module'),
  dumpFormat:         () => apiFetchJson('/serial/dump_format', {}, 'Could not load the dump format'),
  serialSend:         (cmd) => apiFetchJson('/serial/send', {
    method:'POST', headers: jsonHeaders, body: JSON.stringify({cmd})
  }, 'Could not send serial command'),
};
