// Progressive enhancement: without JavaScript, all ten results remain visible.
const filters = document.querySelector('.filters');
const rows = [...document.querySelectorAll('tbody tr[data-split]')];
const counter = document.querySelector('#result-count');
if (filters && rows.length && counter) {
  filters.hidden = false;
  filters.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-filter]');
    if (!button) return;
    const selected = button.dataset.filter;
    filters.querySelectorAll('button').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
    rows.forEach((row) => { row.hidden = selected !== 'all' && row.dataset.split !== selected; });
    const visible = rows.filter((row) => !row.hidden);
    const passed = visible.filter((row) => row.querySelector('.passed')).length;
    counter.textContent = `${visible.length} videos · ${passed} passed · ${visible.length - passed} failed`;
  });
}
