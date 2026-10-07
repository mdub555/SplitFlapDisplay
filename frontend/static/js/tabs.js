// Switching between the pages with the tab bar.
function switchTab(button) {
  const name = button.dataset.tab;
  document.querySelectorAll('.tab-btn').forEach(tab => tab.classList.toggle('active', tab === button));
  document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === `page-${name}`));
  if (name === 'tuning') loadTuningData();
  if (name === 'apps') { buildAppsGrid(); loadGlobalSettings(); }
}

registerActions({ switchTab });
