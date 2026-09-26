document.addEventListener('DOMContentLoaded', () => {
  api.config().then(cfg => {
    // If /config itself fails, fall back to the placeholder grid size from
    // constants.js rather than leaving the page uninitialized — a wrong
    // grid size is recoverable (reload once the backend's back), a blank
    // page isn't.
    setGridConfig(cfg || {grid_rows: GRID_ROWS, grid_cols: GRID_COLS, num_modules: NUM_MODULES});
    initLiveGrids();
    startLivePolling();
    initControlPage();
    buildAppsGrid();   // pre-populates window.appsByKey so live-flap app-name lookups work immediately
  });
});
