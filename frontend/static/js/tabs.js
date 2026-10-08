// Switching between the pages with the tab bar. It's an ARIA tab list: only
// the selected tab is in the Tab order, and the arrow keys (plus Home and
// End) move to the others, as screen reader users expect.
function switchTab(button) {
  const name = button.dataset.tab;
  document.querySelectorAll('.tab-btn').forEach(tab => {
    const selected = tab === button;
    tab.classList.toggle('active', selected);
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === `page-${name}`));
  if (name === 'modules') loadModulesPage();
  if (name === 'apps') { buildAppsGrid(); loadSchedule(); loadGlobalSettings(); }
}

document.querySelector('.tab-bar').addEventListener('keydown', e => {
  const tabs = [...document.querySelectorAll('.tab-btn')];
  const at = tabs.indexOf(document.activeElement);
  if (at < 0) return;
  const to = {
    ArrowRight: (at + 1) % tabs.length,
    ArrowLeft: (at - 1 + tabs.length) % tabs.length,
    Home: 0,
    End: tabs.length - 1,
  }[e.key];
  if (to === undefined) return;
  e.preventDefault();
  tabs[to].focus();
  switchTab(tabs[to]);
});

registerActions({ switchTab });
