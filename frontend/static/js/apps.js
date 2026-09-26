window.appsByKey = {};
let appsLoaded = false;

function buildAppCard(a){
  const card = document.createElement('div');
  card.className = 'app-card';
  card.dataset.app = a.key;
  card.dataset.onclick = 'runApp';

  const hasCfg = a.settings_fields && a.settings_fields.length;
  if (hasCfg) {
    const gear = document.createElement('button');
    gear.className = 'app-gear';
    gear.title = 'Settings';
    gear.textContent = '⚙️';
    gear.dataset.onclick = 'openAppSettings';
    // No manual stopPropagation needed: the dispatcher's closest('[data-onclick]')
    // finds this button (the nearest match) before it ever reaches the card's
    // own data-onclick="runApp" further up the tree.
    card.appendChild(gear);
  }

  const icon = document.createElement('span');
  icon.className = 'app-icon';
  icon.textContent = a.icon;
  card.appendChild(icon);

  const name = document.createElement('span');
  name.className = 'app-name';
  name.textContent = a.name;
  card.appendChild(name);

  const desc = document.createElement('span');
  desc.className = 'app-desc';
  desc.textContent = a.desc;
  card.appendChild(desc);

  return card;
}

function buildAppsGrid(){
  if(appsLoaded) return;
  api.apps().then(list=>{
    if (!list) return;
    list.forEach(a => window.appsByKey[a.key] = a);
    const grid = document.getElementById('appsGrid');
    grid.innerHTML = '';
    list.forEach(a => grid.appendChild(buildAppCard(a)));
    appsLoaded = true;
  });
}

function runApp(el){
  const appKey = el.dataset.app;
  api.runApp(appKey).then(result=>{
    if (!result) return;
    const label = (window.appsByKey[appKey]||{name:appKey}).name;
    showToast(`▶ ${label} started`);
  });
}

registerActions({ runApp });
