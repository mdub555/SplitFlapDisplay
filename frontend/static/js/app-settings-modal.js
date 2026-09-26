let currentAppSettingsKey = null;

async function openAppSettings(appKey){
  currentAppSettingsKey = appKey;
  const appInfo = window.appsByKey[appKey];
  if(!appInfo) return;

  const currentSettings = await api.getSettings();
  if (!currentSettings) return; // error toast already shown by the api layer

  document.getElementById('appSettingsTitle').textContent = `${appInfo.icon} ${appInfo.name} Settings`;
  const fields = document.getElementById('appSettingsFields');
  fields.innerHTML='';

  if(!appInfo.settings_fields.length){
    const note = document.createElement('p');
    note.style.cssText = 'color:#888;text-align:center';
    note.textContent = 'No configurable settings for this app.';
    fields.appendChild(note);
  } else {
    appInfo.settings_fields.forEach(f=>{
      const div = document.createElement('div');
      div.className = 'modal-field';
      const label = document.createElement('label');
      label.textContent = f.label;
      div.appendChild(label);

      let input;
      if(f.type==='select'){
        input = document.createElement('select');
        (f.opts||[]).forEach(opt=>{
          const o = document.createElement('option');
          o.value = opt; o.textContent = opt;
          if((currentSettings[f.key]||'')===opt) o.selected=true;
          input.appendChild(o);
        });
      } else if(f.type==='textarea'){
        input = document.createElement('textarea');
        input.rows = 8;
        if(f.placeholder) input.placeholder = f.placeholder;
        input.value = currentSettings[f.key]||'';
      } else {
        input = document.createElement('input');
        input.type = f.type||'text';
        if(f.min)  input.min  = f.min;
        if(f.max)  input.max  = f.max;
        if(f.step) input.step = f.step;
        if(f.placeholder) input.placeholder = f.placeholder;
        let val = currentSettings[f.key]||'';
        if(f.type==='datetime-local' && val.length>16) val=val.slice(0,16);
        input.value = val;
      }
      input.id = `asf_${f.key}`;
      div.appendChild(input);
      fields.appendChild(div);
    });
  }

  document.getElementById('appSettingsModal').style.display='flex';
}

function closeAppSettings(){
  document.getElementById('appSettingsModal').style.display='none';
}

function saveAppSettings(){
  const appInfo = window.appsByKey[currentAppSettingsKey];
  if(!appInfo) return;
  const payload = {};
  appInfo.settings_fields.forEach(f=>{
    const el = document.getElementById(`asf_${f.key}`);
    if(el) payload[f.key] = el.value;
  });
  api.saveAppSettings(currentAppSettingsKey, payload).then(result=>{
    if (!result) return;
    showToast('Settings saved');
    closeAppSettings();
  });
}

// The gear button lives inside an .app-card that carries data-app; the
// button itself doesn't need its own copy of the key.
function openAppSettingsAction(el){
  const card = el.closest('[data-app]');
  if (card) openAppSettings(card.dataset.app);
}

registerActions({
  openAppSettings: openAppSettingsAction,
  saveAppSettings,
  closeAppSettings,
});
