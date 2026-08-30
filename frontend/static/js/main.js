document.addEventListener('DOMContentLoaded', () => {
  api.config().then(cfg => {
    setGridConfig(cfg);
    initLiveGrids();
    startLivePolling();
    initControlPage();
    buildAppsGrid();   // pre-populates window.appsByKey so live-flap app-name lookups work immediately
  });
});
