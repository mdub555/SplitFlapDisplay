// The settings modal for one app, opened from the ⚙️ on its card.

let currentAppSettingsKey = null;
let modalOpener = null;   // what had focus before it opened, to go back to

async function openAppSettings(appKey) {
  const appInfo = window.appsByKey[appKey];
  if (!appInfo) return;
  currentAppSettingsKey = appKey;

  const settings = await api.getSettings();
  if (!settings) return; // error toast already shown by the api layer

  byId('appSettingsTitle').textContent = `${appInfo.icon} ${appInfo.name} Settings`;
  const fields = appInfo.settings_fields.map(f => buildField(f, settings[f.key], 'asf_', 'modal-field'));
  // The shared settings it needs are edited in one place, Global Settings.
  const globals = appInfo.global_settings.length
    ? [el('p', {class: 'note centered'}, `Also uses from Global Settings: ${appInfo.global_settings.join(', ')}.`)]
    : [];
  const signIn = appInfo.oauth ? [buildOAuthSection(appInfo.oauth)] : [];
  byId('appSettingsFields').replaceChildren(...(fields.length || globals.length || signIn.length
    ? [...fields, ...signIn, ...globals]
    : [el('p', {class: 'note centered'}, 'No configurable settings for this app.')]));
  modalOpener = document.activeElement;
  byId('appSettingsModal').style.display = 'flex';
  // The page behind can't be reached while it's open.
  document.querySelector('.container').inert = true;
  const first = modalFocusable()[0];
  if (first) first.focus();
}

// The account section for an app that signs in to a service (its `oauth`
// from /apps): whether it's connected, how to set it up, and the buttons.
// For a service that can't send the browser back to this page, a box to
// paste the address it ended up on, shown once Connect has been pressed.
function buildOAuthSection(oauth) {
  const connectLabel = `${oauth.connected ? 'Reconnect' : 'Connect'} ${oauth.provider}`;
  return el('div', {class: 'modal-field oauth-section'},
    el('div', {class: 'field-label'}, `${oauth.provider} account`),
    el('p', {class: 'oauth-status', id: 'oauthStatus'}, oauth.connected ? '✓ Connected' : 'Not connected'),
    oauth.help ? el('p', {class: 'note'}, oauth.help) : '',
    oauth.redirect_uri ? el('p', {class: 'note'}, 'Redirect URI: ', el('code', {}, oauth.redirect_uri)) : '',
    el('div', {class: 'button-row'},
      el('button', {class: 'btn btn-fit', dataset: {onclick: 'oauthConnect'}}, connectLabel),
      oauth.connected ? el('button', {class: 'btn btn-ghost btn-fit', dataset: {onclick: 'oauthDisconnect'}}, 'Disconnect') : ''),
    el('div', {id: 'oauthPaste', hidden: true},
      el('label', {class: 'field-label', htmlFor: 'oauthPasteUrl'},
        `After you approve, ${oauth.provider} sends the tab to a page that won't load. Copy that tab's whole address and paste it here:`),
      el('input', {class: 'input', id: 'oauthPasteUrl', type: 'url', placeholder: `${oauth.redirect_uri || ''}?code=...`}),
      el('div', {class: 'button-row'},
        el('button', {class: 'btn btn-success btn-fit', dataset: {onclick: 'oauthFinish'}}, 'Finish connecting'))));
}

// Saves the settings (the Client ID has to be stored before signing in can
// start), then opens the service's sign-in page in a new tab.
async function oauthConnect() {
  const key = currentAppSettingsKey;
  const appInfo = window.appsByKey[key];
  // Opened now, while the click still counts, or the browser blocks it as a
  // pop-up; it's pointed at the sign-in page once that's known.
  const tab = window.open('', '_blank');
  const values = readFieldValues(appInfo.settings_fields, 'asf_');
  const started = values && await api.saveAppSettings(key, values) && await api.oauthStart(key);
  if (!started) {
    if (tab) tab.close();
    return;
  }
  if (tab) {
    tab.opener = null;
    tab.location = started.authorize_url;
  } else {
    window.open(started.authorize_url, '_blank', 'noopener');
  }
  if (started.paste) {
    byId('oauthPaste').hidden = false;
    byId('oauthPasteUrl').focus();
  } else {
    // It finishes in that tab; look again when they come back to this one.
    window.addEventListener('focus', () => refreshOAuth(key), {once: true});
  }
}

async function oauthFinish() {
  const key = currentAppSettingsKey;
  const url = byId('oauthPasteUrl').value.trim();
  if (!url) {
    showToast('Paste the address from the sign-in tab first', 'warn');
    return;
  }
  if (await api.oauthFinish(key, url)) {
    showToast(`${window.appsByKey[key].oauth.provider} connected`);
    refreshOAuth(key);
  }
}

async function oauthDisconnect() {
  const key = currentAppSettingsKey;
  if (await api.oauthDisconnect(key)) {
    showToast(`${window.appsByKey[key].oauth.provider} disconnected`);
    refreshOAuth(key);
  }
}

// Reads the app's sign-in state again and redraws its section, if its
// settings are still open.
async function refreshOAuth(key) {
  const list = await api.apps();
  const fresh = list && list.find(app => app.key === key);
  if (!fresh) return;
  window.appsByKey[key] = fresh;
  const section = document.querySelector('#appSettingsFields .oauth-section');
  if (section && currentAppSettingsKey === key && modalOpen()) section.replaceWith(buildOAuthSection(fresh.oauth));
}

function closeAppSettings() {
  byId('appSettingsModal').style.display = 'none';
  document.querySelector('.container').inert = false;
  if (modalOpener && document.contains(modalOpener)) modalOpener.focus();
  modalOpener = null;
}

const modalOpen = () => byId('appSettingsModal').style.display === 'flex';

function modalFocusable() {
  return [...byId('appSettingsModal').querySelectorAll('input, select, textarea, button')]
    .filter(control => !control.disabled);
}

// Escape closes it; Tab and Shift+Tab go round the modal's own controls.
document.addEventListener('keydown', e => {
  if (!modalOpen()) return;
  if (e.key === 'Escape') {
    e.preventDefault();
    closeAppSettings();
  } else if (e.key === 'Tab') {
    const controls = modalFocusable();
    const first = controls[0], last = controls[controls.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
});

// A click on the dimmed backdrop (not the box) closes it too.
byId('appSettingsModal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeAppSettings();
});

function saveAppSettings() {
  const appInfo = window.appsByKey[currentAppSettingsKey];
  if (!appInfo) return;
  const values = readFieldValues(appInfo.settings_fields, 'asf_');
  if (!values) return;
  api.saveAppSettings(currentAppSettingsKey, values).then(result => {
    if (!result) return;
    showToast('Settings saved');
    closeAppSettings();
  });
}

registerActions({
  // The gear button is inside the card, which carries the app's key.
  openAppSettings: gear => openAppSettings(gear.closest('[data-app]').dataset.app),
  saveAppSettings,
  closeAppSettings,
  oauthConnect,
  oauthFinish,
  oauthDisconnect,
});
