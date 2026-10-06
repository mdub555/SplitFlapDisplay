const debugPanel = {
  el: null,
  logEl: null,
  cmdSelect: null,
  cmdInput: null,
  source: null,
  dumpFormat: null,  // from /serial/dump_format; until it loads, replies show raw

  init() {
    this.el = document.getElementById('debug-panel');
    if (!this.el) return;

    this.logEl = this.el.querySelector('.debug-log');
    this.cmdSelect = this.el.querySelector('.debug-cmd-select');
    this.cmdInput = this.el.querySelector('.debug-cmd-input');
    const sendBtn = this.el.querySelector('.debug-cmd-send');

    this.cmdSelect.addEventListener('change', () => {
      this.cmdInput.value = this.cmdSelect.value;
    });

    sendBtn.addEventListener('click', () => this.send());
    this.cmdInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.send();
    });

    api.dumpFormat().then(format => { if (format) this.dumpFormat = format; });
    this.startLogStream();
  },

  startLogStream() {
    this.source = new EventSource('/serial_log/stream');
    this.source.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.appendLog(data.msg);
    };
    this.source.onerror = () => {
      console.error('Serial log stream error.');
      this.source.close();
      // Retry after a delay
      setTimeout(() => this.startLogStream(), 5000);
    };
  },

  appendLog(msg) {
    // Received text can hold several replies (a broadcast dump gets one per
    // module). Each dump reply gets a line of labelled values; anything else
    // is shown as received.
    if (msg.startsWith('RECV:') && this.dumpFormat) {
      msg.slice('RECV:'.length).split(/\r?\n/).forEach(text => {
        if (!text.trim()) return;
        const dump = this.parseDump(text);
        if (dump) this.appendDump(dump, text.trim());
        else this.appendLine(`RECV: ${text.trim()}`);
      });
      return;
    }
    this.appendLine(msg);
  },

  // A dump reply (m<ID>? then each field as a tab, a label and a value; see
  // DUMP_FIELDS in module_protocol.py) as {id, values: [[field, value], ...]},
  // or null if `text` isn't one or a field doesn't parse.
  parseDump(text) {
    const marker = this.dumpFormat.marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = text.match(new RegExp(`m(\\d+)${marker}((?:\\t[^\\t]*)+)`));
    if (!match) return null;
    const byLabel = Object.fromEntries(this.dumpFormat.fields.map(f => [f.label, f]));
    const values = [];
    for (const part of match[2].split('\t').slice(1)) {
      const field = byLabel[part[0]];
      if (!field || !/^-?\d+$/.test(part.slice(1))) return null;
      values.push([field, Number(part.slice(1))]);
    }
    return { id: match[1], values };
  },

  appendDump(dump, raw) {
    const line = this.appendLine(
      `RECV m${dump.id}${this.dumpFormat.marker} (module ${formatModuleId(Number(dump.id))}): `);
    line.classList.add('dump');
    line.title = raw;
    dump.values.forEach(([field, value], i) => {
      if (i) line.appendChild(document.createTextNode(' · '));
      const span = document.createElement('span');
      span.className = 'dump-field';
      span.dataset.key = field.key;
      const shown = field.kind === 'bool' ? (value ? 'yes' : 'no') : value.toLocaleString();
      span.textContent = `${field.name} ${shown}${field.unit ? ' ' + field.unit : ''}`;
      line.appendChild(span);
    });
  },

  // Adds a timestamped line to the log and returns it.
  appendLine(msg) {
    const line = document.createElement('div');
    line.className = 'debug-log-line';

    const timestamp = new Date().toLocaleTimeString();
    line.textContent = `[${timestamp}] ${msg}`;

    if (msg.startsWith('SENT:')) line.classList.add('sent');
    if (msg.startsWith('RECV')) line.classList.add('recv');

    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;

    // Keep log size manageable
    if (this.logEl.childNodes.length > 200) {
      this.logEl.removeChild(this.logEl.firstChild);
    }
    return line;
  },

  async send() {
    const cmd = this.cmdInput.value.trim();
    if (!cmd) return;

    this.appendLog(`(attempting to send: ${cmd})`);
    const result = await api.serialSend(cmd);
    if (!result) {
      this.appendLog(`(error: could not send command)`);
    }
    this.cmdInput.value = '';
  },

  toggle() {
    this.el.classList.toggle('visible');
  }
};

registerActions({
  toggleDebug: () => debugPanel.toggle(),
});

// We'll call debugPanel.init() from main.js
