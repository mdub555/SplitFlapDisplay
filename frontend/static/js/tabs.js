// Switching between the pages with the tab bar.
function switchTab(button) {
  const name = button.dataset.tab;
  document.querySelectorAll('.tab-btn').forEach(tab => tab.classList.toggle('active', tab === button));
  document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === `page-${name}`));
  if (name === 'modules') loadModulesPage();
  if (name === 'apps') { buildAppsGrid(); loadSchedule(); loadGlobalSettings(); }
}

registerActions({ switchTab });
