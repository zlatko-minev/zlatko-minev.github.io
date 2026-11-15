// Contact is disclosed only after a deliberate action; this reduces basic scraping.
// A public static site cannot provide bot-proof email protection.
document.querySelectorAll('[data-contact]').forEach(button => {
  button.addEventListener('click', () => {
    const output = document.getElementById(button.getAttribute('aria-controls'));
    if (button.getAttribute('aria-expanded') === 'true') return;
    const address = atob(button.dataset.contact);
    const link = document.createElement('a');
    link.href = 'mailto:' + address;
    link.textContent = address;
    output.append(link);
    button.setAttribute('aria-expanded', 'true');
    link.focus();
  });
});
(() => {
  const list = document.getElementById('favorite-papers');
  if (!list) return;
  const controls = document.querySelector('.ribbon-controls');
  const buttons = controls.querySelectorAll('button');
  controls.hidden = false;
  const update = () => {
    buttons[0].disabled = list.scrollLeft <= 4;
    buttons[1].disabled = list.scrollLeft + list.clientWidth >= list.scrollWidth - 2;
  };
  buttons.forEach(button => button.addEventListener('click', () => {
    const card = list.querySelector('li');
    const gap = parseFloat(getComputedStyle(list).gap) || 18;
    list.scrollBy({left: Number(button.dataset.ribbonStep) * (card.getBoundingClientRect().width + gap), behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  }));
  list.addEventListener('scroll', update, {passive: true});
  window.addEventListener('resize', update);
  update();
})();

(() => {
  const wrap = document.querySelector('.reel-wrap');
  const toggle = wrap?.querySelector('[data-reel-toggle]');
  if (!toggle) return;
  const mq = matchMedia('(prefers-reduced-motion: reduce)');
  let userPaused = false, visible = false;
  const update = () => {
    wrap.classList.toggle('motion-ready', !mq.matches);
    toggle.hidden = mq.matches;
    wrap.toggleAttribute('data-reel-paused', userPaused || !visible || document.hidden || mq.matches);
    toggle.textContent = userPaused ? 'Play showcase' : 'Pause showcase';
    toggle.setAttribute('aria-pressed', String(userPaused));
  };
  toggle.addEventListener('click', () => { userPaused = !userPaused; update(); });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; update(); }).observe(wrap);
  } else visible = true;
  document.addEventListener('visibilitychange', update);
  mq.addEventListener('change', update);
  update();
})();

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-copy]');
  if (!button) return;
  const target = document.getElementById(button.dataset.copy);
  if (!target) return;
  const label = button.textContent;
  try {
    if (!navigator.clipboard) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(target.innerText);
    button.textContent = 'Copied';
  } catch {
    const range = document.createRange();
    range.selectNodeContents(target);
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    button.textContent = 'Selected — press Ctrl/⌘-C';
  }
  setTimeout(() => { button.textContent = label; }, 2500);
});
