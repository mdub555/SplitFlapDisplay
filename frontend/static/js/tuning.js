let selectedModule = 0;
let currentSettings = null;

function loadTuningData(){
  document.getElementById('modMatrix').innerHTML='<div class="loading-note">Loading…</div>';
  Promise.all([api.getSettings(), api.globalFields()]).then(([settingsData, fields])=>{
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
    const payload = {};
    fields.forEach(f=>{
      const el = document.getElementById(`gsf_${f.key}`);
      if(el) payload[f.key] = el.value;
    });
    api.saveGlobalSettings(payload).then(()=>showToast('Settings saved'));
  });
}

function renderModuleGrid(){
  const grid = document.getElementById('modMatrix');
  grid.innerHTML='';
  grid.style.gridTemplateColumns = `repeat(${GRID_COLS}, 1fr)`;
  for(let i=0;i<NUM_MODULES;i++){
    const cell=document.createElement('div');
    cell.className=`mod-cell${i===selectedModule?' active':''}`;
    cell.textContent=i.toString().padStart(2,'0');
    cell.onclick=()=>selectModule(i);
    grid.appendChild(cell);
  }
}

function selectModule(id){
  selectedModule=id;
  renderModuleGrid();
  document.getElementById('inspectorPanel').style.display='flex';
  document.getElementById('inspectTitle').textContent=`MODULE ${id.toString().padStart(2,'0')}`;
  document.getElementById('inspectOffset').textContent=currentSettings.offsets[id.toString()]||2832;
  document.getElementById('inspectCalib').textContent=currentSettings.calibrations[id.toString()]||4096;
}

function adjustOffset(delta){
  api.adjustOffset(selectedModule, delta).then(d=>{
    currentSettings.offsets[selectedModule.toString()]=d.new_offset;
    document.getElementById('inspectOffset').textContent=d.new_offset;
  });
}

function homeSelected(){
  api.homeModule(selectedModule);
  showToast(`Homing module ${selectedModule.toString().padStart(2,'0')}`);
}

function homeAll(){
  if(!confirm(`Re-home all ${NUM_MODULES} modules via broadcast?`)) return;
  api.homeAll().then(()=>showToast('Homing all modules','warn'));
}

function calibrateSelected(){
  if(!confirm(`Calibrate Module ${selectedModule}? It will spin 360° to measure steps.`)) return;
  document.getElementById('inspectCalib').textContent='Measuring…';
  api.calibrateModule(selectedModule).then(d=>{
    if(d.status==='success'){
      currentSettings.calibrations[selectedModule.toString()]=d.steps;
      document.getElementById('inspectCalib').textContent=d.steps;
      showToast(`Module ${selectedModule}: ${d.steps} steps`);
    } else {
      showToast('Calibration timeout','error');
    }
  });
}

function syncOneFromHardware(){
  document.getElementById('inspectOffset').textContent='Syncing…';
  api.syncModule(selectedModule).then(d=>{
    if(d.status==='success'){ currentSettings=d.settings; selectModule(selectedModule); showToast('Synced'); }
    else showToast('Sync failed','error');
  });
}

function syncAllFromHardware(){
  if(!confirm(`Poll all ${NUM_MODULES} modules to rebuild settings.json?`)) return;
  document.body.style.cursor='wait';
  api.syncAllModules().then(d=>{
    document.body.style.cursor='default';
    currentSettings=d.settings;
    selectModule(selectedModule);
    showToast('All modules synced');
  });
}

function toggleAutoHome(){
  api.toggleAutoHome(document.getElementById('autoHomeToggle').checked);
}


function provisionModule(){
  if(!confirm('Assign the next grid ID to the unprovisioned module on the bus?')) return;
  showToast('Provisioning…', 'warn');
  api.provisionModule().then(d=>{
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
    const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download=`splitflap_backup_${new Date().toISOString().slice(0,10)}.json`;
    a.click();
    showToast('Backup downloaded');
  });
}

function uploadBackup(input){
  if(!input.files.length) return;
  const reader=new FileReader();
  reader.onload=e=>{
    try{
      const data=JSON.parse(e.target.result);
      if(!confirm(`Restore calibration data and push to all modules?`)) return;
      document.getElementById('restoreStatus').textContent='Restoring…';
      api.restoreSettings(data).then(d=>{
        document.getElementById('restoreStatus').textContent=d.status==='success'?'✓ Done':'✗ Error';
        if(d.status==='success'){ showToast('Restore complete'); loadTuningData(); }
        else showToast('Restore error','error');
      });
    }catch(err){
      showToast('Invalid JSON file','error');
    }
    input.value='';
  };
  reader.readAsText(input.files[0]);
}
