// The serial debug panel: every message sent or received on the bus, live,
// and a box to send any command. Dump replies are shown as labelled values.

const debugPanel = {
  el: null,
  logEl: null,
  cmdInput: null,
  source: null,

  init() {
    this.el = byId('debug-panel');
    this.logEl = this.el.querySelector('.debug-log');
    this.cmdInput = this.el.querySelector('.debug-cmd-input');
    const cmdSelect = this.el.querySelector('.debug-cmd-select');

    cmdSelect.addEventListener('change', () => { this.cmdInput.value = cmdSelect.value; });
    this.el.querySelector('.debug-cmd-send').addEventListener('click', () => this.send());
    this.cmdInput.addEventListener('keydown', e => { if (e.key === 'Enter') this.send(); });

    this.startLogStream();
  },

  startLogStream() {
    this.source = new EventSource('/serial_log/stream');
    this.source.onmessage = event => this.appendLog(JSON.parse(event.data).msg);
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
      this.appendLine(msg);
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

  // Adds a timestamped line to the log and returns it.
  appendLine(msg) {
    const line = el('div', {class: 'debug-log-line'}, `[${new Date().toLocaleTimeString()}] ${msg}`);
    if (msg.startsWith('SENT:')) line.classList.add('sent');
    if (msg.startsWith('RECV')) line.classList.add('recv');
    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;
    // Keep the log to the last 200 lines.
    while (this.logEl.childNodes.length > 200) this.logEl.firstChild.remove();
    return line;
  },

  async send() {
    const cmd = this.cmdInput.value.trim();
    if (!cmd) return;
    this.appendLine(`(attempting to send: ${cmd})`);
    if (!await api.serialSend(cmd)) this.appendLine('(error: could not send command)');
    this.cmdInput.value = '';
  },

  toggle() {
    this.el.classList.toggle('visible');
  },
};

registerActions({
  toggleDebug: () => debugPanel.toggle(),
});
