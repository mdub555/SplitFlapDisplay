// The Apps page: one card per app, which runs it, with a ⚙️ button for its
// settings if it has any.

window.appsByKey = {};
let appsLoaded = false;

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

function buildAppsGrid() {
  if (appsLoaded) return;
  api.apps().then(list => {
    if (!list) return;
    list.forEach(app => { window.appsByKey[app.key] = app; });
    byId('appsGrid').replaceChildren(...list.map(buildAppCard));
    appsLoaded = true;
  });
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

registerActions({ runApp });
