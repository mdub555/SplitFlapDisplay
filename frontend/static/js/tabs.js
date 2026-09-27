/**
 * tabs.js
 *
 * Handles the top-level tab switching functionality.
 */

function switchTab(el) {
  const name = el.dataset.tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('page-' + name).classList.add('active');
  if (name === 'tuning') loadTuningData();
  if (name === 'apps') buildAppsGrid();
}

registerActions({ switchTab });
