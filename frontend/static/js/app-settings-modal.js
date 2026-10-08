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
  byId('appSettingsFields').replaceChildren(...(appInfo.settings_fields.length
    ? appInfo.settings_fields.map(f => buildField(f, settings[f.key], 'asf_', 'modal-field'))
    : [el('p', {class: 'note centered'}, 'No configurable settings for this app.')]));
  modalOpener = document.activeElement;
  byId('appSettingsModal').style.display = 'flex';
  // The page behind can't be reached while it's open.
  document.querySelector('.container').inert = true;
  const first = modalFocusable()[0];
  if (first) first.focus();
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
});
