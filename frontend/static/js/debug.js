const debugPanel = {
  el: null,
  logEl: null,
  cmdSelect: null,
  cmdInput: null,
  source: null,

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
    const line = document.createElement('div');
    line.className = 'debug-log-line';

    const timestamp = new Date().toLocaleTimeString();
    line.textContent = `[${timestamp}] ${msg}`;

    if (msg.startsWith('SENT:')) line.classList.add('sent');
    if (msg.startsWith('RECV:')) line.classList.add('recv');

    this.logEl.appendChild(line);
    this.logEl.scrollTop = this.logEl.scrollHeight;

    // Keep log size manageable
    if (this.logEl.childNodes.length > 200) {
      this.logEl.removeChild(this.logEl.firstChild);
    }
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
  toggleDebug,
});

// We'll call debugPanel.init() from main.js
