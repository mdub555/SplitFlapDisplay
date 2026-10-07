// Starts everything once the page has loaded.
document.addEventListener('DOMContentLoaded', () => {
  initLiveGrids();
  startLiveUpdates();
  initControlPage();
  buildAppsGrid();   // fills appsByKey, so the live display can name a running app straight away
  debugPage.init();
});
