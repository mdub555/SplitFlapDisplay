window.appsByKey = {};
let appsLoaded = false;

function buildAppsGrid(){
  if(appsLoaded) return;
  api.apps().then(list=>{
    list.forEach(a => window.appsByKey[a.key] = a);
    const grid = document.getElementById('appsGrid');
    grid.innerHTML = '';
    list.forEach(a=>{
      const div = document.createElement('div');
      div.className = 'app-card';
      div.dataset.app = a.key;
      div.onclick = ()=>runApp(a.key);
      const hasCfg = a.settings_fields && a.settings_fields.length;
      div.innerHTML = `
        ${hasCfg?`<button class="app-gear" title="Settings" onclick="event.stopPropagation();openAppSettings('${a.key}')">⚙️</button>`:''}
        <span class="app-icon">${a.icon}</span>
        <span class="app-name">${a.name}</span>
        <span class="app-desc">${a.desc}</span>`;
      grid.appendChild(div);
    });
    appsLoaded = true;
  });
}

function runApp(appKey){
  api.runApp(appKey);
  const label = (window.appsByKey[appKey]||{name:appKey}).name;
  showToast(`▶ ${label} started`);
}
