// A message in the corner for a few seconds. `type` is 'success', 'warn' or 'error'.
function showToast(msg, type = 'success') {
  const toast = el('div', {class: type === 'success' ? 'toast' : `toast ${type}`}, msg);
  document.getElementById('toastContainer').appendChild(toast);
  requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.add('show')));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
  }, 2800);
}
