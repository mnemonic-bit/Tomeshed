(() => {
  const bubble = document.getElementById('previewBubble');
  const content = document.getElementById('previewContent');
  const position = document.getElementById('previewPosition');
  const previous = document.getElementById('previewPrevious');
  const next = document.getElementById('previewNext');
  const closeButton = document.getElementById('previewClose');
  let active = null;
  let request = null;
  let generation = 0;
  let lastTouch = 0;
  let pointerX = null;
  let pointerY = null;
  function visibleCard(state = active) {
    if (!state?.card.isConnected || state.card.hidden || !state.card.getClientRects().length) return false;
    const rect = state.thumbnail.getBoundingClientRect();
    const header = document.querySelector('.app-header')?.getBoundingClientRect().bottom || 0;
    const footer = document.getElementById('versionFooter')?.getBoundingClientRect().top || innerHeight;
    return rect.bottom > header && rect.top < footer && rect.right > 0 && rect.left < innerWidth;
  }
  function close(returnFocus = false) {
    if (!active) return;
    const prior = active;
    generation++;
    request?.abort(); request = null;
    active = null;
    bubble.hidden = true;
    prior.button.setAttribute('aria-expanded', 'false');
    if (returnFocus && prior.focusReturn && visibleCard(prior)) prior.button.focus();
  }
  function place(recheckPointer = false) {
    if (!active || !visibleCard()) { close(); return; }
    const anchor = active.thumbnail.getBoundingClientRect();
    const header = document.querySelector('.app-header')?.getBoundingClientRect().bottom || 0;
    const footer = document.getElementById('versionFooter')?.getBoundingClientRect().top || innerHeight;
    const topBound = Math.max(12, header + 8);
    const bottomBound = Math.min(innerHeight - 12, footer - 8);
    const gap = 12;
    const leftRoom = Math.max(0, anchor.left - 12 - gap);
    const rightRoom = Math.max(0, innerWidth - anchor.right - 12 - gap);
    const side = rightRoom >= 330 || rightRoom >= leftRoom ? 'right' : 'left';
    const room = side === 'right' ? rightRoom : leftRoom;
    const width = Math.max(100, Math.min(330, room));
    bubble.style.width = `${width}px`;
    const height = Math.max(100, Math.min(500, bottomBound - topBound));
    bubble.style.height = `${height}px`;
    bubble.style.maxHeight = `${Math.max(100, bottomBound - topBound)}px`;
    bubble.style.left = `${side === 'right' ? anchor.right + gap : anchor.left - gap - width}px`;
    bubble.style.top = `${Math.max(topBound, Math.min(bottomBound - height, anchor.top + anchor.height / 2 - height / 2))}px`;
    bubble.dataset.side = side;
    const box = bubble.getBoundingClientRect();
    bubble.style.setProperty('--preview-pointer-y', `${Math.max(16, Math.min(box.height - 16, anchor.top + anchor.height / 2 - box.top))}px`);
    if (recheckPointer && pointerX !== null && active && active.pointerInside) {
      active.pointerInside = inBridge(pointerX, pointerY);
      if (!active.pointerInside && !active.card.contains(document.activeElement) && !bubble.contains(document.activeElement)) close();
    }
  }
  function showFailure() {
    if (!active) return;
    content.replaceChildren();
    const note = document.createElement('p'); note.className = 'preview-error'; note.textContent = 'Preview unavailable';
    content.append(note); position.textContent = 'Preview unavailable';
    previous.disabled = true; next.disabled = true;
    place();
  }
  function render(result) {
    if (!active) return;
    active.index = result.index;
    active.total = result.total;
    content.replaceChildren();
    if (result.image) {
      const image = document.createElement('img');
      image.alt = result.label; image.src = result.image;
      const owner = active;
      image.addEventListener('error', () => { if (active === owner && active.index === result.index && image.isConnected) showFailure(); });
      content.append(image);
    } else {
      const excerpt = document.createElement('div'); excerpt.className = 'preview-excerpt';
      excerpt.innerHTML = result.html;
      excerpt.querySelectorAll('a').forEach(link => link.removeAttribute('href'));
      content.append(excerpt);
    }
    position.textContent = `${result.label}${result.approximate ? ' · approximate restore' : ''}`;
    previous.disabled = result.index <= 0;
    next.disabled = result.index >= result.total - 1;
    place();
  }
  async function load(index = null) {
    if (!active) return;
    const owner = active;
    const token = ++generation;
    request?.abort(); request = new AbortController();
    content.textContent = 'Loading preview…'; position.textContent = 'Loading preview…';
    previous.disabled = true; next.disabled = true;
    const url = `/api/documents/${encodeURIComponent(owner.id)}/preview${index === null ? '' : `/location/${index}`}`;
    try {
      const response = await fetch(url, {signal: request.signal, credentials: 'same-origin'});
      if (!response.ok) throw new Error(`Preview request failed (${response.status})`);
      const result = await response.json();
      if (token !== generation || active !== owner || !visibleCard(owner)) return;
      render(result);
    } catch (error) {
      if (token === generation && active === owner && error.name !== 'AbortError') showFailure();
    }
  }
  function open(id, card, thumbnail, button, focusReturn = false, pointerEvent = null) {
    if (!focusReturn && Date.now() - lastTouch < 600) return;
    if (pointerEvent) { pointerX = pointerEvent.clientX; pointerY = pointerEvent.clientY; }
    if (active?.id === id && active.card === card) { if (focusReturn) { active.focusReturn = true; closeButton.focus(); } return; }
    close();
    active = {id, card, thumbnail, button, focusReturn, pointerInside: Boolean(pointerEvent), index: 0, total: 0};
    bubble.hidden = false;
    button.setAttribute('aria-expanded', 'true');
    place();
    if (focusReturn) closeButton.focus();
    load();
  }
  function move(delta) {
    if (!active) return;
    const index = active.index + delta;
    if (index >= 0 && index < active.total) load(index);
  }
  function inBridge(x, y) {
    if (!active) return false;
    const a = active.thumbnail.getBoundingClientRect();
    const b = bubble.getBoundingClientRect();
    const c = active.card.getBoundingClientRect();
    const inside = rect => x >= rect.left - 2 && x <= rect.right + 2 && y >= rect.top - 2 && y <= rect.bottom + 2;
    if (inside(c) || inside(b)) return true;
    const gapLeft = Math.min(a.right, b.right);
    const gapRight = Math.max(a.left, b.left);
    return x >= gapLeft - 2 && x <= gapRight + 2 &&
      y >= Math.max(a.top, b.top) - 2 && y <= Math.min(a.bottom, b.bottom) + 2;
  }
  document.addEventListener('pointermove', event => {
    if (event.pointerType === 'touch') return;
    pointerX = event.clientX; pointerY = event.clientY;
    if (!active) return;
    active.pointerInside = inBridge(event.clientX, event.clientY);
    if (!active.pointerInside && !active.card.contains(document.activeElement) && !bubble.contains(document.activeElement)) close();
  });
  document.addEventListener('pointerdown', event => {
    if (event.pointerType === 'touch') lastTouch = Date.now();
  }, true);
  document.addEventListener('pointerleave', event => {
    if (event.pointerType === 'touch') return;
    pointerX = null; pointerY = null;
    if (!active) return;
    active.pointerInside = false;
    if (!active.card.contains(document.activeElement) && !bubble.contains(document.activeElement)) close();
  });
  document.addEventListener('focusin', event => {
    if (active && !active.pointerInside && !active.card.contains(event.target) && !bubble.contains(event.target)) close();
  });
  document.addEventListener('keydown', event => {
    if (active && event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true); }
  }, true);
  previous.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));
  closeButton.addEventListener('click', () => close(true));
  window.addEventListener('resize', () => place(true));
  window.addEventListener('scroll', () => place(true), true);
  window.tomeshedPreview = {open, close, isOpen: () => Boolean(active)};
})();
