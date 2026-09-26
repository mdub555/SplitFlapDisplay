// Lightweight event-delegation framework replacing inline onclick="..." /
// onchange="..." attributes throughout the app.
//
// Usage: elements declare *what* to do via a data-on* attribute instead of
// *how* (raw JS in an HTML attribute string):
//
//   <button data-onclick="stopApp">Stop</button>
//   <button data-onclick="movePlaylist" data-idx="3" data-dir="-1">▲</button>
//
// Each page's JS file registers its handlers once:
//
//   registerActions({ stopApp, movePlaylist });
//
// A handler receives (el, event) — el is the element that declared the
// action (read whatever data-* attributes it needs off el.dataset), event
// is the native DOM event. This means dynamically-rendered rows never need
// to string-interpolate values into HTML attributes (which is both fragile
// and, for free-text fields like playlist names, unsafe) — values travel
// via el.dataset instead, which the browser handles safely regardless of
// what characters they contain.
//
// Only ONE listener per event type exists for the whole page, no matter how
// many buttons get added/removed/re-rendered — no per-element listener
// wiring or cleanup needed when innerHTML gets replaced.

const ACTIONS = {};

function registerActions(map) {
  Object.assign(ACTIONS, map);
}

function dispatchAction(attr, event) {
  const el = event.target.closest(`[${attr}]`);
  if (!el) return;
  const name = el.getAttribute(attr);
  const fn = ACTIONS[name];
  if (!fn) {
    console.warn(`No action registered for ${attr}="${name}"`);
    return;
  }
  fn(el, event);
}

document.addEventListener('click',  e => dispatchAction('data-onclick', e));
document.addEventListener('change', e => dispatchAction('data-onchange', e));
document.addEventListener('input',  e => dispatchAction('data-oninput', e));
