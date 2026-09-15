document.querySelectorAll('[data-progress]').forEach((el) => {
  const v = Number(el.dataset.progress || 0);
  el.style.width = `${Math.max(0, Math.min(100, v))}%`;
});
