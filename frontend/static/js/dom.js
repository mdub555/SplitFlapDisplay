// el(tag, props, ...children) builds an element in one call:
//
//   el('button', {class: 'btn btn-sm', dataset: {onclick: 'stopApp'}}, 'Stop')
//
// `props` sets `class`, `dataset` (an object of data-* values), `role` and
// ARIA attributes (ariaLabel becomes aria-label, and so on), and any other
// property of the element (value, title, type, min, ...). Children
// can be elements or strings; strings become text nodes, never HTML, so
// user-supplied text is always safe to pass.
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key === 'role') node.setAttribute('role', value);
    else if (key.startsWith('aria')) node.setAttribute(`aria-${key.slice(4).toLowerCase()}`, value);
    else node[key] = value;
  }
  node.append(...children);
  return node;
}


const byId = id => document.getElementById(id);
