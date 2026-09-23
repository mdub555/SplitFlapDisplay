const api = {
  config:             () => fetch('/config').then(r=>r.json()),
  currentState:       () => fetch('/current_state').then(r=>r.json()),

  apps:               () => fetch('/apps').then(r=>r.json()),
  saveAppSettings:    (key, data) => fetch(`/apps/${key}/settings`, {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)
  }),
  runApp:             (key) => fetch('/run_app', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({app:key})
  }),
  stopApp:            () => fetch('/stop_app', {method:'POST'}),

  globalFields:       () => fetch('/global_fields').then(r=>r.json()),
  getSettings:        () => fetch('/settings').then(r=>r.json()),
  saveGlobalSettings: (data) => fetch('/settings', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)
  }),
  toggleAutoHome:     (enabled) => fetch('/toggle_autohome', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({enabled})
  }),

  updatePlaylist:     (pages, delay) => fetch('/update_playlist', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pages, delay})
  }),

  playlists:          () => fetch('/playlists').then(r=>r.json()),
  savePlaylist:       (name, pages, delay) => fetch('/playlists', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, pages, delay})
  }).then(r=>r.json()),
  deletePlaylist:     (name) => fetch(`/playlists/${encodeURIComponent(name)}`, {method:'DELETE'}),

  adjustOffset:       (modId, delta) => fetch(`/modules/${modId}/adjust`, {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({delta})
  }).then(r=>r.json()),
  homeModule:         (modId) => fetch(`/modules/${modId}/home`, {method:'POST'}),
  calibrateModule:    (modId) => fetch(`/modules/${modId}/calibrate`, {method:'POST'}).then(r=>r.json()),
  syncModule:         (modId) => fetch(`/modules/${modId}/sync`, {method:'POST'}).then(r=>r.json()),
  syncAllModules:     () => fetch('/modules/sync_all', {method:'POST'}).then(r=>r.json()),
  homeAll:            () => fetch('/home_all'),

  backupSettings:     () => fetch('/backup_settings').then(r=>r.json()),
  restoreSettings:    (data) => fetch('/restore_settings', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)
  }).then(r=>r.json()),
  provisionModule:    () => fetch('/provision_module', {method:'POST'}).then(r => r.json()),
};
