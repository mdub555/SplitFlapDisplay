// The ⓘ buttons (the info() macro in index.html). Each shows its
// explanation while hovered or focused (base.css), or once clicked: it then
// stays open until it's clicked again, another one opens, Escape is pressed
// or the page is clicked anywhere else.

function closeInfoTips(except) {
  document.querySelectorAll('.info-btn[aria-expanded="true"]').forEach(button => {
    if (button !== except) button.setAttribute('aria-expanded', 'false');
  });
}

document.addEventListener('click', e => {
  if (!e.target.closest('.info-btn')) closeInfoTips();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeInfoTips();
});

registerActions({
  toggleInfo: button => {
    const open = button.getAttribute('aria-expanded') !== 'true';
    closeInfoTips(button);
    button.setAttribute('aria-expanded', String(open));
  },
});
