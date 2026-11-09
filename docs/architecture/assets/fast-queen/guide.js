(() => {
  const root = document.documentElement;
  const button = document.querySelector('[data-theme-toggle]');
  const apply = (theme) => {
    root.dataset.theme = theme;
    const next = theme === 'dark' ? 'light' : 'dark';
    button.setAttribute('aria-label', `Switch to ${next} mode`);
    button.setAttribute('aria-pressed', String(theme === 'dark'));
    button.querySelector('[data-theme-label]').textContent = `${next[0].toUpperCase()}${next.slice(1)} mode`;
  };
  let saved;
  try { saved = localStorage.getItem('viventium-guide-theme'); } catch {}
  apply(saved === 'dark' || saved === 'light' ? saved : matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  button.addEventListener('click', () => {
    const theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    apply(theme);
    try { localStorage.setItem('viventium-guide-theme', theme); } catch {}
  });
})();
