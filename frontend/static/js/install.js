// Installing the page as an app on a phone (or desktop). The manifest and
// icons (see routes/pages.py) are what make that possible; a browser that's
// willing to install the page says so with a beforeinstallprompt event, and
// only then does the Install button show. Browsers without the event (Safari)
// still offer Share → Add to Home Screen.

let installPrompt = null;

window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();   // our button, instead of the browser's own banner
  installPrompt = e;
  byId('installBtn').hidden = false;
});

window.addEventListener('appinstalled', () => {
  installPrompt = null;
  byId('installBtn').hidden = true;
});

function installApp() {
  if (!installPrompt) return;
  installPrompt.prompt();
  installPrompt.userChoice.then(() => {
    // A prompt can only be used once; the browser fires a new event if it
    // will offer again.
    installPrompt = null;
    byId('installBtn').hidden = true;
  });
}

registerActions({ installApp });
