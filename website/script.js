// Progressive enhancement: recipes and the full result table also work without JS.
const tablist = document.querySelector('.recipe-tabs');
const tabs = [...document.querySelectorAll('[data-recipe]')];
const panels = [...document.querySelectorAll('.recipe-panel')];
const copyStatus = document.querySelector('.copy-status');

function selectRecipe(tab, focus = false) {
  tabs.forEach((item) => {
    const selected = item === tab;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = selected ? 0 : -1;
  });
  panels.forEach((panel) => { panel.hidden = panel.id !== tab.getAttribute('aria-controls'); });
  if (copyStatus) copyStatus.textContent = '';
  if (focus) tab.focus();
}

if (tablist && tabs.length && panels.length) {
  tablist.hidden = false;
  panels.forEach((panel) => {
    panel.setAttribute('role', 'tabpanel');
    panel.setAttribute('aria-labelledby', 'tab-' + panel.id.replace('recipe-', ''));
    panel.tabIndex = 0;
  });
  selectRecipe(tabs[0]);
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectRecipe(tab));
    tab.addEventListener('keydown', (event) => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) { event.preventDefault(); selectRecipe(tabs[next], true); }
    });
  });
}

document.querySelectorAll('[data-copy]').forEach((button) => {
  button.hidden = false;
  button.addEventListener('click', async () => {
    const code = document.getElementById(button.dataset.copy);
    if (!code) return;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(code.textContent);
      copyStatus.textContent = 'Command copied. Paste it into your terminal when the required environment is ready.';
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(code);
      selection.removeAllRanges();
      selection.addRange(range);
      copyStatus.textContent = 'Command selected. Press Ctrl+C (or ⌘C) to copy.';
    }
  });
});

const filters = document.querySelector('.filters');
const rows = [...document.querySelectorAll('tbody tr[data-split]')];
const counter = document.querySelector('#result-count');
if (filters && rows.length && counter) {
  filters.hidden = false;
  filters.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-filter]');
    if (!button || !filters.contains(button)) return;
    const selected = button.dataset.filter;
    filters.querySelectorAll('button').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
    rows.forEach((row) => { row.hidden = selected !== 'all' && row.dataset.split !== selected; });
    const visible = rows.filter((row) => !row.hidden);
    const passed = visible.filter((row) => row.querySelector('.passed')).length;
    counter.textContent = `${visible.length} videos · ${passed} passed · ${visible.length - passed} failed`;
  });
}
