// A message in the corner for a few seconds. `type` is 'success', 'warn' or 'error'.
//
// Pass {undo: fn} to give it an Undo button: it stays up longer, and Ctrl+Z
// (⌘Z on a Mac) does the same while it's showing, unless the focus is in a
// text field (where Ctrl+Z belongs to the field).
const TOAST_MS = 2800;
const UNDO_TOAST_MS = 8000;
let latestUndo = null;   // {run, toast} for the newest Undo still showing

function showToast(msg, type = 'success', {undo} = {}) {
  // The container reads each one out politely; an error interrupts.
  const toast = el('div', {class: type === 'success' ? 'toast' : `toast ${type}`}, el('span', {}, msg));
  if (type === 'error') toast.setAttribute('role', 'alert');

  let dismissed = false;
  const dismiss = () => {
    dismissed = true;
    if (latestUndo && latestUndo.toast === toast) latestUndo = null;
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
  };
  if (undo) {
    const entry = {toast, run: () => { dismiss(); undo(); }};
    toast.classList.add('has-action');
    toast.append(el('button', {class: 'toast-action', type: 'button', onclick: () => entry.run()}, 'Undo'));
    latestUndo = entry;
  }

  document.getElementById('toastContainer').appendChild(toast);
  // (Not if it's already been dismissed, say by an instant Ctrl+Z.)
  requestAnimationFrame(() => requestAnimationFrame(() => { if (!dismissed) toast.classList.add('show'); }));
  setTimeout(dismiss, undo ? UNDO_TOAST_MS : TOAST_MS);
  return toast;
}

document.addEventListener('keydown', e => {
  if (!latestUndo || e.key.toLowerCase() !== 'z' || !(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey) return;
  const target = e.target;
  // The compose grid's hidden textarea isn't a text field anyone's editing.
  const typing = target.matches && target.matches('input, textarea, select, [contenteditable]') &&
                 target.id !== 'composeInput';
  if (typing) return;
  e.preventDefault();
  latestUndo.run();
});
