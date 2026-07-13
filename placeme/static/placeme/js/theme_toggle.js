(function () {
  const root = document.documentElement;
  const btn = document.querySelector('.theme-toggle');
  if (!btn) return;

  const STORAGE_KEY = 'placeme_theme';

  function applyTheme(theme) {
    if (theme === 'light') {
      // Lightest skyblue-ish background, keep all text/colors as-it-is
      root.classList.add('theme-light');
      root.classList.remove('theme-dark');
      btn.textContent = '☀';
      return;
    }

    root.classList.add('theme-dark');
    root.classList.remove('theme-light');
    btn.textContent = '☾';
  }


  const saved = localStorage.getItem(STORAGE_KEY);
  const initial = saved === 'light' || saved === 'dark' ? saved : 'dark';
  applyTheme(initial);

  btn.addEventListener('click', () => {
    const isLight = root.classList.contains('theme-light');
    const next = isLight ? 'dark' : 'light';
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  });
})();

