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
    input.addEventListener('input', updatePreview);
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
    btn.addEventListener('click', () => insertColor(emoji));
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
    div.textContent = ch===' '?'':ch;
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

// Reads (idx, field) off the row's data attributes rather than having each
// input's onchange string-interpolate the index and field name — the row
// wrapper carries data-idx once, each control inside it just adds data-field.
function updatePlaylistItemFromInput(el){
  const row = el.closest('[data-idx]');
  if(!row) return;
  updatePlaylistItem(parseInt(row.dataset.idx, 10), el.dataset.field, el.value);
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

function buildPlaylistRow(item, idx){
  const arr = Array.from(item.text);
  const rows = [];
  for(let r=0;r<GRID_ROWS;r++){
    rows.push(arr.slice(r*GRID_COLS, (r+1)*GRID_COLS).join(''));
  }

  const row = document.createElement('div');
  row.className = 'playlist-item';
  row.style.cssText = 'flex-direction:column;align-items:stretch;gap:8px';
  row.dataset.idx = idx;

  // Header: page number + move/edit/delete buttons
  const header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center';

  const label = document.createElement('span');
  label.style.cssText = 'color:var(--accent);font-weight:bold';
  label.textContent = `Page ${idx + 1}`;
  header.appendChild(label);

  const btnGroup = document.createElement('div');
  btnGroup.style.cssText = 'display:flex;gap:4px';
  const addBtn = (text, cls, onclick, dir) => {
    const b = document.createElement('button');
    b.className = cls;
    b.textContent = text;
    b.dataset.onclick = onclick;
    if (dir !== undefined) b.dataset.dir = dir;
    btnGroup.appendChild(b);
  };
  addBtn('▲', 'btn btn-secondary btn-sm', 'movePlaylist', -1);
  addBtn('▼', 'btn btn-secondary btn-sm', 'movePlaylist', 1);
  addBtn('EDIT', 'btn btn-secondary btn-sm', 'editPlaylist');
  addBtn('DEL', 'btn-del', 'removeFromPlaylist');
  header.appendChild(btnGroup);
  row.appendChild(header);

  // Text preview — built with <br> between rows, but each row's text goes
  // through textContent-safe construction (no raw HTML from flap content).
  const preview = document.createElement('div');
  preview.style.cssText = "background:#111;padding:10px;border-radius:4px;font-family:'Courier New',monospace;font-size:1rem;line-height:1.5;text-align:center;letter-spacing:1px;border:1px solid #333";
  rows.forEach((r, i) => {
    if (i > 0) preview.appendChild(document.createElement('br'));
    // A run of spaces would otherwise collapse visually; render as &nbsp;
    // via a text node with the non-breaking space character (safe — no HTML
    // parsing involved) instead of the old innerHTML + regex-replace.
    preview.appendChild(document.createTextNode(r.replace(/ /g, '\u00A0')));
  });
  row.appendChild(preview);

  // Per-page delay / style / speed controls
  const controls = document.createElement('div');
  controls.style.cssText = 'display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:8px 10px;background:#1a1a1a;border-radius:5px;border-top:1px solid #2a2a2a';

  const delayLabel = document.createElement('label');
  delayLabel.style.cssText = 'font-size:.78rem;color:#aaa;display:flex;align-items:center;gap:4px';
  delayLabel.append('⏱ ');
  const delayInput = document.createElement('input');
  delayInput.type = 'number';
  delayInput.value = item.delay || 5;
  delayInput.min = '0.5'; delayInput.max = '60'; delayInput.step = '0.5';
  delayInput.style.cssText = 'width:50px;background:#111;color:#fff;border:1px solid #444;border-radius:3px;padding:3px 5px;font-size:.8rem;text-align:center';
  delayInput.dataset.onchange = 'updatePlaylistItemFromInput';
  delayInput.dataset.field = 'delay';
  delayLabel.appendChild(delayInput);
  delayLabel.append(' s');
  controls.appendChild(delayLabel);

  const styleLabel = document.createElement('label');
  styleLabel.style.cssText = 'font-size:.78rem;color:#aaa;display:flex;align-items:center;gap:4px';
  styleLabel.append('↔ ');
  const styleSelect = document.createElement('select');
  styleSelect.style.cssText = 'background:#111;color:#fff;border:1px solid #444;border-radius:3px;padding:3px 5px;font-size:.78rem';
  styleSelect.innerHTML = buildStyleOptions(item.style || 'ltr'); // static, trusted markup — see constants.js
  styleSelect.dataset.onchange = 'updatePlaylistItemFromInput';
  styleSelect.dataset.field = 'style';
  styleLabel.appendChild(styleSelect);
  controls.appendChild(styleLabel);

  const speedLabel = document.createElement('label');
  speedLabel.style.cssText = 'font-size:.78rem;color:#aaa;display:flex;align-items:center;gap:4px';
  speedLabel.append('⚡ ');
  const speedInput = document.createElement('input');
  speedInput.type = 'number';
  speedInput.value = item.speed || 15;
  speedInput.min = '0'; speedInput.max = '500'; speedInput.step = '5';
  speedInput.style.cssText = 'width:50px;background:#111;color:#fff;border:1px solid #444;border-radius:3px;padding:3px 5px;font-size:.8rem;text-align:center';
  speedInput.dataset.onchange = 'updatePlaylistItemFromInput';
  speedInput.dataset.field = 'speed';
  speedLabel.appendChild(speedInput);
  speedLabel.append(' ms');
  controls.appendChild(speedLabel);

  row.appendChild(controls);
  return row;
}

function renderPlaylist(){
  const list = document.getElementById('playlistList');
  if(!playlist.length){
    list.innerHTML='<div class="empty-note">Queue is empty</div>';
    return;
  }
  list.innerHTML='';
  playlist.forEach((item, idx) => list.appendChild(buildPlaylistRow(item, idx)));
}

function editPlaylist(el){
  const idx = parseInt(el.closest('[data-idx]').dataset.idx, 10);
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

function movePlaylist(el){
  const idx = parseInt(el.closest('[data-idx]').dataset.idx, 10);
  const dir = parseInt(el.dataset.dir, 10);
  if(idx+dir<0||idx+dir>=playlist.length) return;
  [playlist[idx],playlist[idx+dir]]=[playlist[idx+dir],playlist[idx]];
  if(editingIndex===idx) editingIndex=idx+dir;
  else if(editingIndex===idx+dir) editingIndex=idx;
  renderPlaylist();
}

function removeFromPlaylist(el){
  const idx = parseInt(el.closest('[data-idx]').dataset.idx, 10);
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
  api.updatePlaylist(pages, delay).then(result=>{
    if (result) showToast('Pushed to display');
  });
}

function stopApp(){
  api.stopApp().then(result=>{
    if (result) showToast('App stopped');
  });
}

function loadSavedPlaylists(){
  api.playlists().then(data=>renderSavedPlaylists(data || {}));
}

function buildSavedPlaylistRow(name, item){
  const row = document.createElement('div');
  row.className = 'saved-pl-item';
  row.dataset.name = name;

  const nameSpan = document.createElement('span');
  nameSpan.className = 'saved-pl-name';
  nameSpan.textContent = name; // textContent — safe regardless of what characters the name contains
  row.appendChild(nameSpan);

  const meta = document.createElement('span');
  meta.style.cssText = 'color:#666;font-size:.8rem';
  meta.textContent = `${item.pages.length}p·${item.delay}s`;
  row.appendChild(meta);

  const addBtn = (text, cls, onclick) => {
    const b = document.createElement('button');
    b.className = cls;
    b.textContent = text;
    b.dataset.onclick = onclick;
    row.appendChild(b);
  };
  addBtn('Load', 'btn btn-secondary btn-sm', 'loadSavedPlaylist');
  addBtn('Run', 'btn btn-success btn-sm', 'runSavedPlaylist');
  addBtn('✕', 'btn-del', 'deleteSavedPlaylist');

  return row;
}

function renderSavedPlaylists(data){
  const list = document.getElementById('savedPlaylistList');
  const names = Object.keys(data||{});
  if(!names.length){
    list.innerHTML='<div class="empty-note">No saved playlists yet.</div>';
    return;
  }
  list.innerHTML='';
  names.forEach(name => list.appendChild(buildSavedPlaylistRow(name, data[name])));
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
  api.savePlaylist(name, pages, delay).then(result=>{
    if (!result) return;
    showToast(`Saved "${name}"`);
    document.getElementById('savePlaylistName').value='';
    loadSavedPlaylists();
  });
}

// name now arrives as the raw string (via el.dataset.name) rather than a
// URL-encoded fragment pulled out of an onclick="..." attribute — dataset
// handles arbitrary characters safely, so no encode/decode dance is needed
// here anymore. api.deletePlaylist still URL-encodes internally, which is
// still correct — that's a real requirement of building the request path.
function loadSavedPlaylist(el){
  const name = el.closest('[data-name]').dataset.name;
  api.playlists().then(data=>{
    if (!data) return;
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

function runSavedPlaylist(el){
  const name = el.closest('[data-name]').dataset.name;
  api.playlists().then(data=>{
    if (!data) return;
    const item = data[name];
    if(!item) return;
    api.updatePlaylist(item.pages, item.delay).then(result=>{
      if (result) showToast(`Running "${name}"`);
    });
  });
}

function deleteSavedPlaylist(el){
  const name = el.closest('[data-name]').dataset.name;
  if(!confirm(`Delete playlist "${name}"?`)) return;
  api.deletePlaylist(name).then(result=>{
    if (!result) return;
    showToast(`Deleted "${name}"`,'warn');
    loadSavedPlaylists();
  });
}

function initControlPage(){
  buildLineInputs();
  buildColorPalette();
  const sel = document.getElementById('styleInput');
  if(sel) sel.innerHTML = buildStyleOptions('ltr');
  updatePreview();
  loadSavedPlaylists();
}

registerActions({
  clearDisplay, saveMessage, sync, saveCurrentPlaylist, stopApp,
  toggleMultiMode, updatePreview, updatePlaylistItemFromInput,
  movePlaylist, editPlaylist, removeFromPlaylist,
  loadSavedPlaylist, runSavedPlaylist, deleteSavedPlaylist,
});
