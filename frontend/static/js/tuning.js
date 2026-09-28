let selectedModule = 0;
let currentSettings = null;

function loadTuningData(){
  document.getElementById('modMatrix').innerHTML='<div class="loading-note">Loading…</div>';
  Promise.all([api.getSettings(), api.globalFields()]).then(([settingsData, fields])=>{
    if (!settingsData || !fields) return; // error toast already shown by the api layer
    currentSettings = settingsData;
    renderGlobalSettingsForm(fields, settingsData);
    document.getElementById('autoHomeToggle').checked = settingsData.auto_home;
    renderModuleGrid();
    selectModule(selectedModule);
  });
}

function renderGlobalSettingsForm(fields, settingsData){
  const grid = document.getElementById('globalSettingsGrid');
  grid.innerHTML = '';
  fields.forEach(f=>{
    const wrap = document.createElement('div');
    if(f.type==='textarea') wrap.className='span2';
    const label = document.createElement('label');
    label.className = 'field-label';
    label.textContent = f.label;
    wrap.appendChild(label);

    let input;
    if(f.type==='select'){
      input = document.createElement('select');
      input.className = 'line-input';
      (f.opts||[]).forEach(opt=>{
        const o = document.createElement('option');
        o.value=opt; o.textContent=opt;
        if((settingsData[f.key]||f.default)===opt) o.selected=true;
        input.appendChild(o);
      });
    } else {
      input = document.createElement('input');
      input.type = f.type||'text';
      input.className = 'line-input';
      input.style.margin = '0';
      if(f.placeholder) input.placeholder = f.placeholder;
      input.value = settingsData[f.key] !== undefined ? settingsData[f.key] : f.default;
    }
    input.id = `gsf_${f.key}`;
    wrap.appendChild(input);
    grid.appendChild(wrap);
  });
}

function saveGlobal(){
  api.globalFields().then(fields=>{
    if (!fields) return;
    const payload = {};
    fields.forEach(f=>{
      const el = document.getElementById(`gsf_${f.key}`);
      if(el) payload[f.key] = el.value;
    });
    api.saveGlobalSettings(payload).then(result=>{
      if (result) showToast('Settings saved');
    });
  });
}

function renderModuleGrid(){
  const grid = document.getElementById('modMatrix');
  grid.innerHTML='';
  grid.style.gridTemplateColumns = `repeat(${GRID_COLS}, 1fr)`;
  for(let i=0;i<NUM_MODULES;i++){
    const cell=document.createElement('div');
    const isUnprovisioned = !currentSettings.modules || !currentSettings.modules[i.toString()];
    cell.className=`mod-cell${i===selectedModule?' active':''} ${isUnprovisioned?' unprovisioned':''}`;
    cell.textContent=i.toString().padStart(2,'0');
    cell.dataset.onclick = 'selectModuleAction';
    cell.dataset.id = i;
    grid.appendChild(cell);
  }
}

function selectModule(id){
  selectedModule=id;
  renderModuleGrid();
  document.getElementById('inspectorPanel').style.display='flex';
  document.getElementById('inspectTitle').textContent=`MODULE ${id.toString().padStart(2,'0')}`;

  const mod = currentSettings.modules ? currentSettings.modules[id.toString()] : null;
  if (mod) {
      document.getElementById('inspectOffset').textContent = mod.homeOffset !== undefined ? mod.homeOffset : 480;
      document.getElementById('inspectCalib').textContent = mod.totalSteps !== undefined ? mod.totalSteps : 4096;
  } else {
      document.getElementById('inspectOffset').textContent = '---';
      document.getElementById('inspectCalib').textContent = '---';
  }
}

function selectModuleAction(el){
  selectModule(parseInt(el.dataset.id, 10));
}

function adjustOffset(el){
  const delta = parseInt(el.dataset.delta, 10);
  api.adjustOffset(selectedModule, delta).then(d=>{
    if (!d) return;
    if (!currentSettings.modules) currentSettings.modules = {};
    if (!currentSettings.modules[selectedModule.toString()]) {
        currentSettings.modules[selectedModule.toString()] = {'homeOffset': 480, 'totalSteps': 4096, 'autoHome': true, 'motorClockwise': true, 'motorRelease': false};
    }
    currentSettings.modules[selectedModule.toString()].homeOffset = d.new_offset;
    document.getElementById('inspectOffset').textContent = d.new_offset;
  });
}

function homeSelected(){
  api.homeModule(selectedModule).then(result=>{
    if (result) showToast(`Homing module ${selectedModule.toString().padStart(2,'0')}`);
  });
}

function homeAll(){
  if(!confirm(`Re-home all ${NUM_MODULES} modules via broadcast?`)) return;
  api.homeAll().then(result=>{
    if (result) showToast('Homing all modules','warn');
  });
}

function calibrateSelected(){
  if(!confirm(`Calibrate Module ${selectedModule}? It will spin 360° to measure steps.`)) return;

  const mod = currentSettings.modules ? currentSettings.modules[selectedModule.toString()] : null;
  const prevCalib = mod ? (mod.totalSteps || 4096) : 4096;

  document.getElementById('inspectCalib').textContent='Measuring…';
  api.calibrateModule(selectedModule).then(d=>{
    if (!d) {
      document.getElementById('inspectCalib').textContent = prevCalib;
      return;
    }
    if (!currentSettings.modules) currentSettings.modules = {};
    if (!currentSettings.modules[selectedModule.toString()]) {
        currentSettings.modules[selectedModule.toString()] = {'homeOffset': 480, 'totalSteps': 4096, 'autoHome': true, 'motorClockwise': true, 'motorRelease': false};
    }
    currentSettings.modules[selectedModule.toString()].totalSteps = d.steps;
    document.getElementById('inspectCalib').textContent = d.steps;
    showToast(`Module ${selectedModule}: ${d.steps} steps`);
  });
}

function syncOneFromHardware(){
  const mod = currentSettings.modules ? currentSettings.modules[selectedModule.toString()] : null;
  const prevOffset = mod ? (mod.homeOffset || 480) : 480;
  document.getElementById('inspectOffset').textContent='Syncing…';
  api.syncModule(selectedModule).then(d=>{
    if(d && d.status==='success'){
      currentSettings=d.settings;
      selectModule(selectedModule);
      showToast('Synced');
    } else {
      document.getElementById('inspectOffset').textContent = prevOffset;
      if (d) showToast('Sync failed','error');
    }
  });
}

function syncAllFromHardware(){
  if(!confirm(`Poll all ${NUM_MODULES} modules to rebuild settings.json?`)) return;
  document.body.style.cursor='wait';
  api.syncAllModules().then(d=>{
    document.body.style.cursor='default';
    if (!d) return;
    currentSettings=d.settings;
    selectModule(selectedModule);
    showToast('All modules synced');
  });
}

function toggleAutoHome(el){
  const enabled = el.checked;
  api.toggleAutoHome(enabled).then(result=>{
    if (!result) el.checked = !enabled;
  });
}

function provisionModule(){
  const target_id = selectedModule; // Provision the currently selected module
  if(!confirm(`Assign ID ${target_id} to the unprovisioned module on the bus?`)) return;
  showToast('Provisioning…', 'warn');
  api.provisionModule({id: target_id}).then(d=>{
    if (!d) return;
    if(d.status === 'success'){
      showToast(`Module assigned ID ${d.assigned_id}`);
      loadTuningData();
    } else {
      showToast(d.message || 'Provisioning failed', 'error');
    }
  }).catch(()=>showToast('Provisioning failed', 'error'));
}

function downloadBackup(){
  api.backupSettings().then(data=>{
    if (!data) return;
    const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download=`splitflap_backup_${new Date().toISOString().slice(0,10)}.json`;
    a.click();
    showToast('Backup downloaded');
  });
}

function triggerBackupFileInput(){
  document.getElementById('backupFile').click();
}

function uploadBackup(input){
  if(!input.files.length) return;
  const reader=new FileReader();
  reader.onload=e=>{
    let data;
    try{
      data = JSON.parse(e.target.result);
    }catch(err){
      showToast('Invalid JSON file','error');
      input.value='';
      return;
    }
    if(!confirm(`Restore calibration data and push to all modules?`)){
      input.value='';
      return;
    }
    document.getElementById('restoreStatus').textContent='Restoring…';
    api.restoreSettings(data).then(d=>{
      if(d && d.status==='success'){
        document.getElementById('restoreStatus').textContent='✓ Done';
        showToast('Restore complete');
        loadTuningData();
      } else {
        document.getElementById('restoreStatus').textContent='✗ Error';
        if (d) showToast('Restore error','error'); // a null d already got its own toast
      }
    });
    input.value='';
  };
  reader.readAsText(input.files[0]);
}

registerActions({
  selectModuleAction, adjustOffset, homeSelected, homeAll, calibrateSelected,
  syncOneFromHardware, syncAllFromHardware, toggleAutoHome,
  saveGlobal, downloadBackup, triggerBackupFileInput, uploadBackup,
});
