// The schedule, on the Apps page: which app or saved playlist the display
// shows at which times of the week. The backend runs it (display/scheduler.py);
// this only edits it.

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];   // as Python's weekday()
const DAY_FULL_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const NEW_SLOT = {days: [0, 1, 2, 3, 4], start: '07:00', end: '09:00', target: ''};
let schedulePlaylists = {};   // the saved playlists, for the target lists

// What a target ('app:<key>' or 'playlist:<name>') is called on screen.
function targetLabel(target) {
  if (!target) return 'nothing';
  if (target === 'blank') return 'a blank display';
  const [kind, ...rest] = target.split(':');
  const key = rest.join(':');
  return kind === 'app' ? appName(key) : `playlist "${key}"`;
}

// A <select> of everything the display can be set to show, with `selected`
// chosen. `blank` labels a first, empty option. A target that no longer
// exists (a deleted playlist) stays in the list, marked, so saving doesn't
// silently change it.
function targetSelect(selected, blank, props = {}) {
  const apps = Object.values(window.appsByKey);
  const names = Object.keys(schedulePlaylists);
  const known = new Set(['blank', ...apps.map(a => `app:${a.key}`), ...names.map(n => `playlist:${n}`)]);
  const select = el('select', {class: 'input', ...props},
    el('option', {value: ''}, blank),
    ...(selected && !known.has(selected) ? [el('option', {value: selected}, `${targetLabel(selected)} (missing)`)] : []),
    el('optgroup', {label: 'Display'}, el('option', {value: 'blank'}, '■ Blank the display')),
    el('optgroup', {label: 'Apps'}, ...apps.map(a => el('option', {value: `app:${a.key}`}, `${a.icon} ${a.name}`))),
    ...(names.length
      ? [el('optgroup', {label: 'Saved playlists'}, ...names.map(n => el('option', {value: `playlist:${n}`}, n)))]
      : []));
  select.value = selected || '';
  return select;
}

function buildScheduleEntry(entry) {
  const button = (text, action, title, cls = 'btn btn-secondary btn-sm', dir) =>
    el('button', {class: cls, title, ariaLabel: title, dataset: {onclick: action, ...(dir !== undefined && {dir})}}, text);
  return el('div', {class: 'schedule-entry', role: 'group', ariaLabel: 'Time slot'},
    el('div', {class: 'schedule-days', role: 'group', ariaLabel: 'Days'}, ...DAY_NAMES.map((name, day) =>
      el('label', {class: 'day-chip'},
        el('input', {type: 'checkbox', checked: entry.days.includes(day), ariaLabel: DAY_FULL_NAMES[day], dataset: {day}}),
        el('span', {ariaHidden: 'true'}, name)))),
    el('div', {class: 'row row-tight schedule-times'},
      el('input', {type: 'time', class: 'input', value: entry.start, dataset: {time: 'start'},
                   title: 'Start time', ariaLabel: 'Start time'}),
      el('span', {ariaHidden: 'true'}, '–'),
      el('input', {type: 'time', class: 'input', value: entry.end, dataset: {time: 'end'},
                   title: 'End time', ariaLabel: 'End time'})),
    targetSelect(entry.target, 'Choose what to show…', {dataset: {target: ''}, ariaLabel: 'What to show'}),
    el('div', {class: 'row row-tight'},
      button('▲', 'moveScheduleEntry', 'Check this slot earlier', undefined, -1),
      button('▼', 'moveScheduleEntry', 'Check this slot later', undefined, 1),
      button('✕', 'removeScheduleEntry', 'Remove this slot', 'btn btn-danger btn-sm')));
}

function renderSchedule(reply) {
  const {schedule} = reply;
  byId('scheduleEnabled').checked = !!schedule.enabled;
  byId('scheduleEntries').replaceChildren(...schedule.entries.map(buildScheduleEntry));
  byId('scheduleDefault').replaceWith(targetSelect(schedule.default, 'Leave as is', {id: 'scheduleDefault'}));
  byId('scheduleStatus').textContent = schedule.enabled
    ? `Display clock: ${reply.now}. Scheduled now: ${targetLabel(reply.current)}.`
    : `Display clock: ${reply.now}. The schedule is off.`;
}

function loadSchedule() {
  return Promise.all([buildAppsGrid(), api.schedule(), api.playlists()]).then(([, reply, playlists]) => {
    if (!reply) return;
    schedulePlaylists = playlists || {};
    renderSchedule(reply);
  });
}

// The schedule as the form shows it.
function readSchedule() {
  return {
    enabled: byId('scheduleEnabled').checked,
    default: byId('scheduleDefault').value,
    entries: [...byId('scheduleEntries').querySelectorAll('.schedule-entry')].map(row => ({
      days: [...row.querySelectorAll('[data-day]')].filter(box => box.checked).map(box => Number(box.dataset.day)),
      start: row.querySelector('[data-time="start"]').value,
      end: row.querySelector('[data-time="end"]').value,
      target: row.querySelector('[data-target]').value,
    })),
  };
}

function saveSchedule() {
  api.saveSchedule(readSchedule()).then(reply => {
    if (!reply) return;   // the api layer shows what's wrong with it
    renderSchedule(reply);
    showToast('Schedule saved');
  });
}

function addScheduleEntry() {
  const slot = buildScheduleEntry(NEW_SLOT);
  byId('scheduleEntries').append(slot);
  slot.querySelector('[data-day]').focus();
}

function moveScheduleEntry(button) {
  const row = button.closest('.schedule-entry');
  if (Number(button.dataset.dir) < 0) {
    if (row.previousElementSibling) row.previousElementSibling.before(row);
  } else if (row.nextElementSibling) {
    row.nextElementSibling.after(row);
  }
  button.focus();   // moving it in the page can drop focus
}

function removeScheduleEntry(button) {
  const row = button.closest('.schedule-entry');
  const list = byId('scheduleEntries');
  const after = row.nextElementSibling;   // where it goes back, on undo
  const next = row.nextElementSibling || row.previousElementSibling;
  row.remove();
  (next ? next.querySelector('[data-onclick="removeScheduleEntry"]') : document.querySelector('[data-onclick="addScheduleEntry"]')).focus();
  showToast('Time slot removed (Save Schedule to keep it that way)', 'success', {undo: () => {
    if (after && after.parentNode === list) list.insertBefore(row, after);
    else list.append(row);
    row.querySelector('[data-onclick="removeScheduleEntry"]').focus();
  }});
}

registerActions({ saveSchedule, addScheduleEntry, moveScheduleEntry, removeScheduleEntry });
