// Presenter controls: keyboard and button navigation, the slide counter, the theme
// cycle (system, light, dark) and the speaker-cue overlay. Every slide renders in
// full without this script; it only adds navigation on top.
(() => {
  const root = document.documentElement;
  const slides = Array.from(document.querySelectorAll('.slide'));
  if (!slides.length) return;

  const counter = document.querySelector('[data-counter]');
  const prevBtn = document.querySelector('[data-action="prev"]');
  const nextBtn = document.querySelector('[data-action="next"]');
  const themeBtn = document.querySelector('[data-action="theme"]');
  const themeLabel = document.querySelector('[data-theme-label]');
  const notesBtn = document.querySelector('[data-action="notes"]');
  const notes = document.querySelector('[data-notes]');
  const notesWhen = document.querySelector('[data-notes-when]');
  const notesCue = document.querySelector('[data-notes-cue]');

  const THEME_KEY = 'srq-deck-theme';
  const THEMES = ['system', 'light', 'dark'];
  const THEME_NAMES = { system: 'System', light: 'Light', dark: 'Dark' };

  let current = 0;

  const store = {
    get(key) {
      try {
        return localStorage.getItem(key);
      } catch (e) {
        return null;
      }
    },
    set(key, value) {
      try {
        if (value === null) localStorage.removeItem(key);
        else localStorage.setItem(key, value);
      } catch (e) {
        /* storage unavailable: the choice lasts for this visit only */
      }
    },
  };

  // ---------- Navigation ----------

  function render() {
    if (counter) counter.textContent = `${current + 1} / ${slides.length}`;
    if (prevBtn) prevBtn.disabled = current === 0;
    if (nextBtn) nextBtn.disabled = current === slides.length - 1;
    const slide = slides[current];
    if (notesWhen) notesWhen.textContent = slide.dataset.time ? `Time: ${slide.dataset.time}` : '';
    if (notesCue) notesCue.textContent = slide.dataset.cue || '';
  }

  function goTo(index) {
    const target = Math.max(0, Math.min(slides.length - 1, index));
    slides[target].scrollIntoView({ block: 'start' });
    current = target;
    render();
    if (slides[target].id) history.replaceState(null, '', `#${slides[target].id}`);
  }

  // The slide that fills most of the viewport is the current one, so scrolling
  // by trackpad or touch keeps the counter honest.
  const ratios = new Map();
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => ratios.set(entry.target, entry.intersectionRatio));
      let best = current;
      let bestRatio = -1;
      slides.forEach((slide, i) => {
        const r = ratios.get(slide) || 0;
        if (r > bestRatio) {
          bestRatio = r;
          best = i;
        }
      });
      if (best !== current) {
        current = best;
        render();
        if (slides[best].id) history.replaceState(null, '', `#${slides[best].id}`);
      }
    },
    { threshold: [0, 0.25, 0.5, 0.75, 1] },
  );
  slides.forEach((slide) => observer.observe(slide));

  prevBtn?.addEventListener('click', () => goTo(current - 1));
  nextBtn?.addEventListener('click', () => goTo(current + 1));

  // ---------- Theme ----------

  function currentTheme() {
    return root.dataset.theme === 'light' || root.dataset.theme === 'dark' ? root.dataset.theme : 'system';
  }

  function applyTheme(theme) {
    if (theme === 'system') delete root.dataset.theme;
    else root.dataset.theme = theme;
    store.set(THEME_KEY, theme === 'system' ? null : theme);
    if (themeLabel) themeLabel.textContent = THEME_NAMES[theme];
    themeBtn?.setAttribute('aria-label', `Theme: ${THEME_NAMES[theme].toLowerCase()} (T)`);
  }

  function cycleTheme() {
    const next = THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
    applyTheme(next);
  }

  themeBtn?.addEventListener('click', cycleTheme);
  applyTheme(currentTheme());

  // ---------- Speaker cues ----------

  function toggleNotes(force) {
    if (!notes) return;
    const show = typeof force === 'boolean' ? force : notes.hidden;
    notes.hidden = !show;
    notesBtn?.setAttribute('aria-pressed', String(show));
  }
  notesBtn?.addEventListener('click', () => toggleNotes());

  // ---------- Keyboard ----------

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else root.requestFullscreen?.().catch(() => {});
  }

  document.addEventListener('keydown', (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const tag = event.target && event.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

    const key = event.key;
    let handled = true;
    if (key === 'ArrowRight' || key === 'ArrowDown' || key === 'PageDown' || (key === ' ' && !event.shiftKey)) {
      goTo(current + 1);
    } else if (key === 'ArrowLeft' || key === 'ArrowUp' || key === 'PageUp' || (key === ' ' && event.shiftKey)) {
      goTo(current - 1);
    } else if (key === 'Home') {
      goTo(0);
    } else if (key === 'End') {
      goTo(slides.length - 1);
    } else if (key === 'f' || key === 'F') {
      toggleFullscreen();
    } else if (key === 'n' || key === 'N') {
      toggleNotes();
    } else if (key === 't' || key === 'T') {
      cycleTheme();
    } else {
      handled = false;
    }
    if (handled) event.preventDefault();
  });

  // ---------- Start ----------

  const fromHash = slides.findIndex((s) => `#${s.id}` === location.hash);
  if (fromHash > 0) {
    current = fromHash;
    slides[fromHash].scrollIntoView({ block: 'start' });
  }
  render();
})();
