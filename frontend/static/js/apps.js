// The Apps page: one card per app, which runs it, with a ⚙️ button for its
// settings if it has any; and the global settings the apps share.

window.appsByKey = {};
let appsRequest = null;   // the /apps request, once it's made (and hasn't failed)

function buildAppCard(app) {
  return el('div', {class: 'app-card', dataset: {app: app.key, onclick: 'runApp'}},
    // The dispatcher acts on the nearest data-onclick, so clicking the gear
    // opens the settings without also running the app.
    app.settings_fields.length
      ? el('button', {class: 'app-gear', title: 'Settings', dataset: {onclick: 'openAppSettings'}}, '⚙️')
      : '',
    el('span', {class: 'app-icon'}, app.icon),
    el('span', {class: 'app-name'}, app.name),
    el('span', {class: 'app-desc'}, app.desc));
}

// Fills the grid (and appsByKey) once; resolves when that's done. After a
// failure the next call tries again.
function buildAppsGrid() {
  if (!appsRequest) {
    appsRequest = api.apps().then(list => {
      if (!list) { appsRequest = null; return; }
      list.forEach(app => { window.appsByKey[app.key] = app; });
      byId('appsGrid').replaceChildren(...list.map(buildAppCard));
      renderBanner();   // a running app's name, if the banner went up first
      markRunning();
    });
  }
  return appsRequest;
}

function appName(key) {
  return (window.appsByKey[key] || {name: key}).name;
}

function runApp(card) {
  const key = card.dataset.app;
  api.runApp(key).then(result => {
    if (result) showToast(`▶ ${appName(key)} started`);
  });
}

// The global settings (timezone, YouTube keys, ...), read fresh each time
// the page is opened. The fields come from /global_fields.
function loadGlobalSettings() {
  Promise.all([api.getSettings(), api.globalFields()]).then(([settings, fields]) => {
    if (!settings || !fields) return; // error toast already shown by the api layer
    byId('globalSettingsGrid').replaceChildren(...fields.map(f => buildField(f, settings[f.key], 'gsf_')));
  });
}

function saveGlobal() {
  api.globalFields().then(fields => {
    if (!fields) return;
    api.saveGlobalSettings(readFieldValues(fields, 'gsf_')).then(result => {
      if (result) showToast('Settings saved');
    });
  });
}

registerActions({ runApp, saveGlobal });
