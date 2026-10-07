// The settings modal for one app, opened from the ⚙️ on its card.

let currentAppSettingsKey = null;

async function openAppSettings(appKey) {
  const appInfo = window.appsByKey[appKey];
  if (!appInfo) return;
  currentAppSettingsKey = appKey;

  const settings = await api.getSettings();
  if (!settings) return; // error toast already shown by the api layer

  byId('appSettingsTitle').textContent = `${appInfo.icon} ${appInfo.name} Settings`;
  byId('appSettingsFields').replaceChildren(...(appInfo.settings_fields.length
    ? appInfo.settings_fields.map(f => buildField(f, settings[f.key], 'asf_', 'modal-field'))
    : [el('p', {class: 'note centered'}, 'No configurable settings for this app.')]));
  byId('appSettingsModal').style.display = 'flex';
}

function closeAppSettings() {
  byId('appSettingsModal').style.display = 'none';
}

function saveAppSettings() {
  const appInfo = window.appsByKey[currentAppSettingsKey];
  if (!appInfo) return;
  api.saveAppSettings(currentAppSettingsKey, readFieldValues(appInfo.settings_fields, 'asf_')).then(result => {
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
});
