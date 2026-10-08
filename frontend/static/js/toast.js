// A message in the corner for a few seconds. `type` is 'success', 'warn' or 'error'.
function showToast(msg, type = 'success') {
  // The container reads each one out politely; an error interrupts.
  const toast = el('div', {class: type === 'success' ? 'toast' : `toast ${type}`}, msg);
  if (type === 'error') toast.setAttribute('role', 'alert');
  document.getElementById('toastContainer').appendChild(toast);
  requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.add('show')));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
  }, 2800);
}
