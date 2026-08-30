let editingIndex = null;
let playlist = [];
let lastFocusedInput = null;
let lastCursorPos = 0;

function lineInputIds(){
  return Array.from({length: GRID_ROWS}, (_, i) => `L${i}`);
}

function buildLineInputs(){
  const wrap = document.getElementById('lineInputs');
  wrap.innerHTML = '';
  lineInputIds().forEach((id, i) => {
    const input = document.createElement('input');
    input.type = 'text';
    input.id = id;
    input.className = 'line-input';
    input.placeholder = `LINE ${i + 1}`;
    input.oninput = updatePreview;
    ['focus','keyup','click'].forEach(ev=>input.addEventListener(ev, e=>{
      lastFocusedInput = e.target;
      lastCursorPos = e.target.selectionStart||0;
    }));
    wrap.appendChild(input);
  });
}

function buildColorPalette(){
  const wrap = document.getElementById('colorPalette');
  wrap.innerHTML = '';
  COLOR_PALETTE.forEach(emoji=>{
    const btn = document.createElement('button');
    btn.className = 'color-btn';
    btn.title = COLOR_TITLES[emoji] || '';
    btn.textContent = emoji;
    btn.onclick = () => insertColor(emoji);
    wrap.appendChild(btn);
  });
}

function updatePreview(){
  const grid = document.getElementById('preview');
  grid.innerHTML='';
  grid.style.gridTemplateColumns = `repeat(${GRID_COLS}, 1fr)`;
  const centered = document.getElementById('centerToggle').checked;
  let full='';
  lineInputIds().forEach(id=>{
    const el = document.getElementById(id);
    let chars = Array.from(el.value);
    if(chars.length>GRID_COLS){
      const s = el.selectionStart;
      chars = chars.slice(0,GRID_COLS);
      el.value = chars.join('');
      el.setSelectionRange(s,s);
    }
    let dc = chars.map(c=>c.toUpperCase());
    if(centered){
      const pad = Math.floor((GRID_COLS-dc.length)/2);
      for(let i=0;i<pad;i++) dc.unshift(' ');
    }
    while(dc.length<GRID_COLS) dc.push(' ');
    full += dc.join('');
  });
  for(let ch of Array.from(full)){
    const div = document.createElement('div');
    div.className='flap-unit';
    div.innerText = ch===' '?'':ch;
    grid.appendChild(div);
  }
  return full;
}

function clearDisplay(){
  lineInputIds().forEach(id=>document.getElementById(id).value='');
  if(editingIndex!==null){
    editingIndex=null;
    document.getElementById('saveMsgBtn').textContent='+ Add to Playlist';
  }
  updatePreview();
}

function toggleMultiMode(){
  document.getElementById('multiControls').style.display =
    document.getElementById('modeToggle').checked ? 'block':'none';
}

function insertColor(emoji){
  const target = lastFocusedInput||document.getElementById('L0');
  let chars = Array.from(target.value);
  if(chars.length>=GRID_COLS) return;
  const text = target.value;
  const start = lastCursorPos;
  target.value = text.substring(0,start)+emoji+text.substring(start);
  lastCursorPos += emoji.length;
  target.focus();
  target.setSelectionRange(lastCursorPos,lastCursorPos);
  updatePreview();
}

function updatePlaylistItem(idx, key, value){
  if(!playlist[idx]) return;
  if(key==='delay'||key==='speed') playlist[idx][key]=parseFloat(value)||0;
  else playlist[idx][key]=value;
}

function saveMessage(){
  const raw = {};
  lineInputIds().forEach((id, i) => raw[`raw${i}`] = document.getElementById(id).value);
  const item={
    text: updatePreview(),
    raw,
    centered: document.getElementById('centerToggle').checked,
    delay: parseFloat(document.getElementById('delayInput').value)||5,
    style: document.getElementById('styleInput').value||'ltr',
    speed: parseInt(document.getElementById('speedInput').value)||15,
  };
  if(editingIndex!==null){
    playlist[editingIndex]=item;
    editingIndex=null;
    document.getElementById('saveMsgBtn').textContent='+ Add to Playlist';
    clearDisplay();
  } else {
    playlist.push(item);
  }
  renderPlaylist();
}

function renderPlaylist(){
  const list = document.getElementById('playlistList');
  if(!playlist.length){
    list.innerHTML='<div class="empty-note">Queue is empty</div>';
    return;
  }
  list.innerHTML='';
  playlist.forEach((item,idx)=>{
    const arr=Array.from(item.text);
    const rows = [];
    for(let r=0;r<GRID_ROWS;r++){
      rows.push(arr.slice(r*GRID_COLS, (r+1)*GRID_COLS).join('').replace(/ /g,'&nbsp;'));
    }
    const div=document.createElement('div');
    div.className='playlist-item';
    div.style.cssText='flex-direction:column;align-items:stretch;gap:8px';
    div.innerHTML=`
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="color:var(--accent);font-weight:bold">Page ${idx+1}</span>
        <div style="display:flex;gap:4px">
          <button class="btn btn-secondary btn-sm" onclick="movePlaylist(${idx},-1)">▲</button>
          <button class="btn btn-secondary btn-sm" onclick="movePlaylist(${idx},1)">▼</button>
          <button class="btn btn-secondary btn-sm" onclick="editPlaylist(${idx})">EDIT</button>
          <button class="btn-del" onclick="removeFromPlaylist(${idx})">DEL</button>
        </div>
      </div>
      <div style="background:#111;padding:10px;border-radius:4px;font-family:'Courier New',monospace;font-size:1rem;line-height:1.5;text-align:center;letter-spacing:1px;border:1px solid #333">${rows.join('<br>')}</div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:8px 10px;background:#1a1a1a;border-radius:5px;border-top:1px solid #2a2a2a">
        <label style="font-size:.78rem;color:#aaa;display:flex;align-items:center;gap:4px">
          ⏱
          <input type="number" value="${item.delay||5}" min="0.5" max="60" step="0.5"
            style="width:50px;background:#111;color:#fff;border:1px solid #444;border-radius:3px;padding:3px 5px;font-size:.8rem;text-align:center"
            onchange="updatePlaylistItem(${idx},'delay',this.value)">
          s
        </label>
        <label style="font-size:.78rem;color:#aaa;display:flex;align-items:center;gap:4px">
          ↔
          <select style="background:#111;color:#fff;border:1px solid #444;border-radius:3px;padding:3px 5px;font-size:.78rem"
            onchange="updatePlaylistItem(${idx},'style',this.value)">
            ${buildStyleOptions(item.style||'ltr')}
          </select>
        </label>
        <label style="font-size:.78rem;color:#aaa;display:flex;align-items:center;gap:4px">
          ⚡
          <input type="number" value="${item.speed||15}" min="0" max="500" step="5"
            style="width:50px;background:#111;color:#fff;border:1px solid #444;border-radius:3px;padding:3px 5px;font-size:.8rem;text-align:center"
            onchange="updatePlaylistItem(${idx},'speed',this.value)">
          ms
        </label>
      </div>`;
    list.appendChild(div);
  });
}

function editPlaylist(idx){
  editingIndex=idx;
  const item=playlist[idx];
  lineInputIds().forEach((id,i)=>{ document.getElementById(id).value = (item.raw && item.raw[`raw${i}`]) || ''; });
  document.getElementById('centerToggle').checked=item.centered;
  document.getElementById('delayInput').value=item.delay||5;
  document.getElementById('styleInput').value=item.style||'ltr';
  document.getElementById('speedInput').value=item.speed||15;
  document.getElementById('saveMsgBtn').textContent=`Save Changes to Page ${idx+1}`;
  updatePreview();
}

function movePlaylist(idx,dir){
  if(idx+dir<0||idx+dir>=playlist.length) return;
  [playlist[idx],playlist[idx+dir]]=[playlist[idx+dir],playlist[idx]];
  if(editingIndex===idx) editingIndex=idx+dir;
  else if(editingIndex===idx+dir) editingIndex=idx;
  renderPlaylist();
}

function removeFromPlaylist(idx){
  playlist.splice(idx,1);
  if(editingIndex===idx) clearDisplay();
  else if(editingIndex>idx) editingIndex--;
  renderPlaylist();
}

function sync(){
  let pages;
  const delay = document.getElementById('delayInput').value;
  if(document.getElementById('modeToggle').checked){
    pages = playlist.map(p=>({text:p.text, delay:p.delay||5, style:p.style||'ltr', speed:p.speed||15}));
  } else {
    pages = [{
      text: updatePreview(),
      delay: parseFloat(delay)||5,
      style: document.getElementById('styleInput').value||'ltr',
      speed: parseInt(document.getElementById('speedInput').value)||15,
    }];
  }
  api.updatePlaylist(pages, delay);
  showToast('Pushed to display');
}

function stopApp(){
  api.stopApp().then(()=>showToast('App stopped'));
}

function loadSavedPlaylists(){
  api.playlists().then(renderSavedPlaylists);
}

function renderSavedPlaylists(data){
  const list = document.getElementById('savedPlaylistList');
  const names = Object.keys(data||{});
  if(!names.length){
    list.innerHTML='<div class="empty-note">No saved playlists yet.</div>';
    return;
  }
  list.innerHTML='';
  names.forEach(name=>{
    const item = data[name];
    const div = document.createElement('div');
    div.className='saved-pl-item';
    div.innerHTML=`
      <span class="saved-pl-name">${name}</span>
      <span style="color:#666;font-size:.8rem">${item.pages.length}p·${item.delay}s</span>
      <button class="btn btn-secondary btn-sm" onclick="loadSavedPlaylist('${encodeURIComponent(name)}')">Load</button>
      <button class="btn btn-success btn-sm" onclick="runSavedPlaylist('${encodeURIComponent(name)}')">Run</button>
      <button class="btn-del" onclick="deleteSavedPlaylist('${encodeURIComponent(name)}')">✕</button>`;
    list.appendChild(div);
  });
}

function saveCurrentPlaylist(){
  const name = document.getElementById('savePlaylistName').value.trim();
  if(!name){ showToast('Enter a name first','warn'); return; }
  let pages;
  const delay = document.getElementById('delayInput').value;
  if(document.getElementById('modeToggle').checked){
    pages = playlist.map(p=>({text:p.text,delay:p.delay||5,style:p.style||'ltr',speed:p.speed||15}));
  } else {
    pages = [{text:updatePreview(),delay:parseFloat(delay)||5,
              style:document.getElementById('styleInput').value||'ltr',
              speed:parseInt(document.getElementById('speedInput').value)||15}];
  }
  api.savePlaylist(name, pages, delay).then(()=>{
    showToast(`Saved "${name}"`);
    document.getElementById('savePlaylistName').value='';
    loadSavedPlaylists();
  });
}

function loadSavedPlaylist(encodedName){
  const name = decodeURIComponent(encodedName);
  api.playlists().then(data=>{
    const item = data[name];
    if(!item) return;
    playlist = item.pages.map(p=>{
      const text   = typeof p==='object' ? p.text   : p;
      const delay  = typeof p==='object' ? (p.delay||5) : 5;
      const style  = typeof p==='object' ? (p.style||'ltr') : 'ltr';
      const speed  = typeof p==='object' ? (p.speed||15) : 15;
      const raw = {};
      lineInputIds().forEach((id,i)=>{ raw[`raw${i}`] = text.slice(i*GRID_COLS,(i+1)*GRID_COLS).trim(); });
      return { text, delay, style, speed, raw, centered:false };
    });
    document.getElementById('delayInput').value = item.delay;
    document.getElementById('modeToggle').checked = true;
    toggleMultiMode();
    renderPlaylist();
    showToast(`Loaded "${name}"`);
  });
}

function runSavedPlaylist(encodedName){
  const name = decodeURIComponent(encodedName);
  api.playlists().then(data=>{
    const item = data[name];
    if(!item) return;
    api.updatePlaylist(item.pages, item.delay);
    showToast(`Running "${name}"`);
  });
}

function deleteSavedPlaylist(encodedName){
  const name = decodeURIComponent(encodedName);
  if(!confirm(`Delete playlist "${name}"?`)) return;
  api.deletePlaylist(name).then(()=>{ showToast(`Deleted "${name}"`,'warn'); loadSavedPlaylists(); });
}

function initControlPage(){
  buildLineInputs();
  buildColorPalette();
  const sel = document.getElementById('styleInput');
  if(sel) sel.innerHTML = buildStyleOptions('ltr');
  updatePreview();
  loadSavedPlaylists();
}
