// Previewing in the compose grid: the page (or, in multi-page mode, the
// whole playlist) played the way the display would show it, before it's
// pushed. Each flap starts from what the display shows now, waits its turn
// in the page's transition (its rank x the page's speed), then turns
// forward through the reel to its character at the reel's real speed.
// Nothing is sent; the grid goes back to the page being composed afterwards.
// (Random's order differs on the display every time.)

const PREVIEW_TICK_MS = 30;
let preview = null;   // {timer, pageTimer} while one runs

// Flap index of each character as the grid shows it (colours as emoji).
const SHOWN_INDEX = new Map(Array.from(CHAR_MAP, (ch, i) => [displayChar(ch) || ' ', i]));

const previewing = () => preview !== null;

function previewButton() {
  return byId('previewBtn');
}

// Stops a running preview without redrawing (renderComposer calls this).
function cancelPreview() {
  if (!preview) return;
  clearInterval(preview.timer);
  clearTimeout(preview.pageTimer);
  preview = null;
  byId('composeWrapper').classList.remove('previewing');
  previewButton().textContent = '▷ Preview';
  previewButton().setAttribute('aria-pressed', 'false');
}

function stopPreview() {
  cancelPreview();
  renderComposer();   // the page being composed, back in the grid
}

function togglePreview() {
  if (previewing()) { stopPreview(); return; }
  const pages = currentPages();
  if (!pages.length) { showToast('The playlist is empty', 'warn'); return; }
  // From what the display shows now.
  const from = Array.from({length: composeCells()}, (_, i) => Math.max(0, CHAR_MAP.indexOf((liveState.state || '')[i] || ' ')));
  preview = {timer: null, pageTimer: null};
  byId('composeWrapper').classList.add('previewing');
  previewButton().textContent = '■ Stop preview';
  previewButton().setAttribute('aria-pressed', 'true');
  playPreviewPage(pages, 0, from);
}

// Plays page `n` of `pages`, starting from flap indexes `from`, then holds
// it for its delay and goes on to the next.
function playPreviewPage(pages, n, from) {
  const page = pages[n];
  const chars = Array.from(page.text || '');
  const target = from.map((_, i) => SHOWN_INDEX.get(chars[i] || ' ') ?? 0);
  const style = CONFIG.styles.find(s => s.value === page.style) || CONFIG.styles[0];
  const spacing = (Number(page.speed) || 0) + CONFIG.bus_ms_per_module;
  const stepMs = CONFIG.seconds_per_flap * 1000;
  const startAt = Array(from.length).fill(0);
  style.order.forEach((cell, rank) => { if (cell < from.length) startAt[cell] = rank * spacing; });
  const steps = from.map((f, i) => (target[i] - f + CHAR_MAP.length) % CHAR_MAP.length);
  const jump = reducedMotion.matches;   // straight to the character at its turn
  const finish = Math.max(...steps.map((s, i) => startAt[i] + (jump || !s ? 0 : s * stepMs)));
  const began = performance.now();
  byId('composeWhere').textContent = `Previewing page ${n + 1} of ${pages.length}`;

  const draw = () => {
    const t = performance.now() - began;
    composeFlaps.forEach((flap, i) => {
      let idx = from[i];
      if (t >= startAt[i]) {
        idx = jump ? target[i] : (from[i] + Math.min(steps[i], Math.floor((t - startAt[i]) / stepMs))) % CHAR_MAP.length;
      }
      showInFlap(flap, displayChar(CHAR_MAP[idx]));
    });
    if (t < finish) return;
    clearInterval(preview.timer);
    if (n + 1 >= pages.length) {
      byId('composeWhere').textContent = 'Preview finished';
      preview.pageTimer = setTimeout(stopPreview, pages.length > 1 ? 1500 : 2500);
      return;
    }
    preview.pageTimer = setTimeout(() => playPreviewPage(pages, n + 1, target), (Number(page.delay) || 5) * 1000);
  };
  draw();
  preview.timer = setInterval(draw, PREVIEW_TICK_MS);
}

// Typing in the grid, clicking it or using the palette ends a preview, so
// the edit lands on the page itself.
byId('composeInput').addEventListener('keydown', () => { if (previewing()) stopPreview(); });
byId('composeWrapper').addEventListener('mousedown', () => { if (previewing()) stopPreview(); });

registerActions({ togglePreview });
