// The Debug page: send any command in the firmware's protocol to a module
// (or all of them), watch every message sent or received on the bus, and
// look up the flap character table. Dump replies are shown as labelled values.

// What a character typed or shown in the UI is sent as: colour emoji, °, ♥
// and " become their codes on the wire; anything else is sent as typed.
const WIRE_CHARS = {
  ...Object.fromEntries(Object.entries(CONFIG.display_chars).map(([code, shown]) => [shown, code])),
  // Every colour tile, the black one (the blank flap, ' ') included.
  ...Object.fromEntries(CONFIG.color_tiles.map(tile => [tile.emoji, tile.code])),
};
const toWireChars = text => Array.from(text).map(ch => WIRE_CHARS[ch] || ch).join('');

const DEBUG_COMMANDS = Object.fromEntries(CONFIG.debug_commands.map(c => [c.key, c]));

const debugPage = {
  logEl: null,
  source: null,

  init() {
    this.logEl = byId('debugLog');
    // Enter in any of the command's inputs sends it.
    byId('debugParams').addEventListener('keydown', e => {
      if (e.key === 'Enter' && e.target.matches('input')) this.send();
    });
    byId('debugModuleId').addEventListener('keydown', e => { if (e.key === 'Enter') this.send(); });
    this.buildFlapTable();
    this.selectCommand();
    this.startLogStream();
  },

  // ── The command form ──

  command() {
    return DEBUG_COMMANDS[byId('debugCommand').value];
  },

  // Builds the inputs for the chosen command.
  selectCommand() {
    const command = this.command();
    const target = command.target === 'module';
    byId('debugModuleId').disabled = !target || byId('debugBroadcast').checked;
    byId('debugBroadcast').disabled = !target;
    byId('debugTarget').classList.toggle('disabled', !target);
    byId('debugCommandHint').textContent = command.hint;
    byId('debugParams').replaceChildren(
      ...command.params.map(param => this.paramField(param)),
      ...(command.dump_after ? [el('label', {class: 'check-label debug-dump-after'},
        el('input', {type: 'checkbox', id: 'debugDumpAfter', dataset: {onchange: 'updateDebugPreview'}}),
        ' Then request a state dump (answered once it finishes)')] : []));
    this.updatePreview();
  },

  paramField(param) {
    const id = `debugParam-${param.name}`;
    let input;
    if (param.kind === 'bool') {
      input = el('select', {class: 'input', id, dataset: {onchange: 'updateDebugPreview'}},
        el('option', {value: '1', selected: param.default}, param.on),
        el('option', {value: '0', selected: !param.default}, param.off));
    } else if (param.kind === 'select') {
      input = el('select', {class: 'input', id, dataset: {onchange: 'updateDebugPreview'}},
        ...param.options.map(([value, label]) => el('option', {value, selected: value === param.default}, label)));
    } else if (param.kind === 'int') {
      input = el('input', {type: 'number', class: 'input', id, min: param.min, max: param.max, step: 1,
        value: param.default ?? '', placeholder: `${param.min}–${param.max}`, dataset: {oninput: 'updateDebugPreview'}});
    } else {
      input = el('input', {type: 'text', class: 'input', id, autocomplete: 'off', spellcheck: false,
        placeholder: param.placeholder || '', dataset: {oninput: 'updateDebugPreview'}});
    }
    const range = param.kind === 'int' ? ` (${param.min}–${param.max}${param.unit ? ' ' + param.unit : ''})` : '';
    return el('div', {class: 'debug-param'},
      el('label', {class: 'field-label', htmlFor: id}, param.label + range), input);
  },

  paramValue(name) {
    return byId(`debugParam-${name}`).value;
  },

  // The chosen module ID, as it goes on the wire (two or more digits, or *).
  target() {
    if (byId('debugBroadcast').checked) return {wire: CONFIG.broadcast, name: 'every module'};
    const raw = byId('debugModuleId').value.trim();
    const id = Number(raw);
    if (!/^\d+$/.test(raw) || id > CONFIG.max_module_id) {
      return {error: `Module ID must be 0–${CONFIG.max_module_id}, or broadcast`};
    }
    return {wire: String(id).padStart(2, '0'), name: `module ${formatModuleId(id)}`};
  },

  // The messages the form describes: {messages, targetName, warning} or {error}.
  build() {
    const command = this.command();
    const values = [];
    for (const param of command.params) {
      const value = this.paramValue(param.name);
      if (param.kind === 'int') {
        const n = Number(value);
        if (value.trim() === '' || !Number.isInteger(n) || n < param.min || n > param.max) {
          return {error: `${param.label} must be a whole number from ${param.min} to ${param.max}`};
        }
        values.push(String(n));
      } else {
        values.push(value);
      }
    }

    if (command.format === 'raw') {
      const message = values[0].trim();
      return message ? {messages: [message], targetName: 'the bus'} : {error: 'Type a message to send'};
    }

    if (command.format === 'frame') {
      const [rawText, interval, order] = values;
      const text = toWireChars(rawText);
      const maxLength = command.params[0].max_length;
      if (!text) return {error: 'Type the text to show'};
      if (text.length > maxLength) return {error: `At most ${maxLength} characters`};
      const n = text.length;
      const rank = i => order === 'rtl' ? n - 1 - i : order === 'all' ? 0 : i;
      const pairs = Array.from(text, (ch, i) => ch + String.fromCharCode('!'.charCodeAt(0) + rank(i))).join('');
      return {messages: [`m${CONFIG.broadcast}${command.cmd}${interval}:${pairs}`],
              targetName: 'every module', warning: this.missingFlaps(text)};
    }

    const target = this.target();
    if (target.error) return target;
    let warning = '';
    if (command.params.some(p => p.kind === 'char')) {
      const ch = toWireChars(values[0].trim() || values[0]);
      if (Array.from(ch).length !== 1) return {error: 'Enter exactly one character'};
      values[0] = ch;
      const index = CHAR_MAP.indexOf(ch);
      warning = index >= 0 ? '' : this.missingFlaps(ch);
    }
    const messages = [`m${target.wire}${command.cmd}${values.join('')}`];
    if (command.dump_after && byId('debugDumpAfter').checked) {
      messages.push(`m${target.wire}${DEBUG_COMMANDS.dump.cmd}`);
    }
    return {messages, targetName: target.name, warning};
  },

  missingFlaps(text) {
    const missing = [...new Set(Array.from(text).filter(ch => !CHAR_MAP.includes(ch)))];
    return missing.length ? `Not on the reel (the module will ignore it): ${missing.join(' ')}` : '';
  },

  // Shows the message that would be sent, and what the target and inputs mean.
  updatePreview() {
    const target = this.target();
    byId('debugModuleHint').textContent = this.command().target !== 'module'
      ? (this.command().target === 'broadcast' ? 'This command always goes to every module.'
                                               : 'The message is sent exactly as typed.')
      : (target.error || `Sends to ${target.name} (IDs are typed in decimal, shown elsewhere in hex).`);

    const built = this.build();
    const preview = byId('debugPreview');
    preview.classList.toggle('invalid', !!built.error);
    preview.textContent = built.error ? built.error : built.messages.join('   then   ');
    byId('debugSend').disabled = !!built.error;

    // A note about the input itself: which flap an index or character is.
    const command = this.command();
    let note = built.warning || '';
    if (!built.error && command.key === 'show_index') {
      note = `Flap ${this.paramValue('index')}: ${this.flapLabel(CHAR_MAP[Number(this.paramValue('index'))])}`;
    } else if (!built.error && command.key === 'show_char' && !note) {
      note = `Flap index ${CHAR_MAP.indexOf(built.messages[0].slice(-1))}`;
    }
    const noteEl = byId('debugNote');
    noteEl.hidden = !note;
    noteEl.textContent = note;
    noteEl.classList.toggle('warning', !!built.warning);
  },

  async send() {
    const built = this.build();
    if (built.error) {
      showToast(built.error, 'error');
      return;
    }
    const confirmText = this.command().confirm;
    if (confirmText && !confirm(confirmText.replace('{target}', built.targetName))) return;
    for (const message of built.messages) {
      if (!await api.serialSend(message)) {
        this.appendLine(`(error: could not send ${message})`);
        return;
      }
    }
  },

  // ── The flap table ──

  flapLabel(ch) {
    if (ch === undefined) return '?';
    if (ch === ' ') return 'blank';
    const shown = displayChar(ch);
    return shown === ch ? ch : `${shown} (${ch})`;
  },

  buildFlapTable() {
    byId('flapTable').replaceChildren(...Array.from(CHAR_MAP, (ch, i) =>
      el('button', {class: 'flap-cell', type: 'button', title: `Use flap ${i}`,
                    dataset: {onclick: 'useFlap', index: i}},
        el('span', {class: 'flap-idx'}, String(i)),
        el('span', {class: 'flap-char'}, ch === ' ' ? '␣' : displayChar(ch)),
        el('span', {class: 'flap-code'}, ch === ' ' ? 'blank' : (displayChar(ch) === ch ? '' : ch)))));
  },

  // Puts a flap from the table into the form: as the character or index to
  // show, switching to Show character unless a flap command is chosen.
  useFlap(index) {
    const select = byId('debugCommand');
    if (!['show_char', 'show_index'].includes(select.value)) {
      select.value = 'show_char';
      this.selectCommand();
    }
    const input = select.value === 'show_index' ? byId('debugParam-index') : byId('debugParam-char');
    input.value = select.value === 'show_index' ? index : CHAR_MAP[index];
    this.updatePreview();
    input.focus();
  },

  // ── The serial log ──

  startLogStream() {
    this.source = new EventSource('/serial_log/stream');
    this.source.onmessage = event => {
      let msg;
      try {
        msg = JSON.parse(event.data).msg;
      } catch (err) {
        console.error('Bad serial log message:', event.data, err);
        return;   // one bad message mustn't stop the log
      }
      if (typeof msg === 'string') this.appendLog(msg);
    };
    this.source.onerror = () => {
      console.error('Serial log stream error.');
      this.source.close();
      setTimeout(() => this.startLogStream(), 5000);   // retry
    };
  },

  appendLog(msg) {
    // Received text can hold several replies (a broadcast dump gets one per
    // module). Each dump reply gets a line of labelled values; anything else
    // is shown as received.
    if (!msg.startsWith('RECV:')) {
      const line = this.appendLine(msg);
      const frame = this.describeFrame(msg);
      if (frame) line.append(el('span', {class: 'log-note'}, ` → ${frame}`));
      return;
    }
    msg.slice('RECV:'.length).split(/\r?\n/).forEach(text => {
      if (!text.trim()) return;
      const dump = this.parseDump(text);
      if (dump) this.appendDump(dump, text.trim());
      else this.appendLine(`RECV: ${text.trim()}`);
    });
  },

  // A dump reply (m<ID>? then each field as a tab, a label and a value; see
  // DUMP_FIELDS in module_protocol.py) as {id, values: [[field, value], ...]},
  // or null if `text` isn't one or a field doesn't parse.
  parseDump(text) {
    const format = CONFIG.dump_format;
    const marker = format.marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = text.match(new RegExp(`m(\\d+)${marker}((?:\\t[^\\t]*)+)`));
    if (!match) return null;
    const byLabel = Object.fromEntries(format.fields.map(f => [f.label, f]));
    const values = [];
    for (const part of match[2].split('\t').slice(1)) {
      const field = byLabel[part[0]];
      if (!field || !/^-?\d+$/.test(part.slice(1))) return null;
      values.push([field, Number(part.slice(1))]);
    }
    return {id: match[1], values};
  },

  appendDump(dump, raw) {
    const fields = dump.values.flatMap(([field, value], i) => {
      const shown = field.kind === 'bool' ? (value ? 'yes' : 'no') : value.toLocaleString();
      const span = el('span', {class: 'dump-field', dataset: {key: field.key}},
        `${field.name} ${shown}${field.unit ? ' ' + field.unit : ''}`);
      return i ? [' · ', span] : [span];
    });
    const line = this.appendLine(
      `RECV m${dump.id}${CONFIG.dump_format.marker} (module ${formatModuleId(Number(dump.id))}): `);
    line.classList.add('dump');
    line.title = raw;
    line.append(...fields);
  },

  // What a frame broadcast (m*f<interval>:<pairs>, how pages go to the
  // display; see frame_message() in display/player.py) puts on the display,
  // in words, or null if `msg` isn't one. Each pair is a module's character
  // and its start rank.
  describeFrame(msg) {
    const frameCmd = (CONFIG.debug_commands.find(c => c.format === 'frame') || {}).cmd;
    const match = frameCmd && msg.match(/^(?:SIMULATED )?SENT: m(.)(.)(\d+):(.*)$/);
    if (!match || match[1] !== CONFIG.broadcast || match[2] !== frameCmd) return null;
    const pairs = Array.from(match[4]);
    const chars = pairs.filter((_, i) => i % 2 === 0).map(ch => displayChar(ch) || ' ');
    const rows = [];
    for (let r = 0; r < GRID_ROWS; r++) {
      const row = chars.slice(r * GRID_COLS, (r + 1) * GRID_COLS).join('').trim();
      if (row) rows.push(row);
    }
    return `page "${rows.join(' / ') || '(blank)'}", modules ${match[3]} ms apart`;
  },

  // Adds a timestamped line to the log and returns it.
  appendLine(msg) {
    const line = el('div', {class: 'debug-log-line'}, `[${new Date().toLocaleTimeString()}] ${msg}`);
    if (msg.startsWith('SENT:') || msg.startsWith('SIMULATED SENT:')) line.classList.add('sent');
    if (msg.startsWith('NOT SENT') || msg.startsWith('SERIAL LOST')) line.classList.add('lost');
    if (msg.startsWith('RECV')) line.classList.add('recv');
    // Only follow new lines if the log was already scrolled to the bottom.
    const atBottom = this.logEl.scrollHeight - this.logEl.scrollTop - this.logEl.clientHeight < 20;
    this.logEl.appendChild(line);
    if (atBottom) this.logEl.scrollTop = this.logEl.scrollHeight;
    // Keep the log to the last 500 lines.
    while (this.logEl.childNodes.length > 500) this.logEl.firstChild.remove();
    return line;
  },
};

registerActions({
  selectDebugCommand: () => debugPage.selectCommand(),
  updateDebugPreview: () => debugPage.updatePreview(),
  toggleDebugBroadcast: () => {
    byId('debugModuleId').disabled = byId('debugBroadcast').checked;
    debugPage.updatePreview();
  },
  sendDebugCommand: () => debugPage.send(),
  clearDebugLog: () => debugPage.logEl.replaceChildren(),
  useFlap: button => debugPage.useFlap(Number(button.dataset.index)),
});
