(() => {
  const bubble = document.getElementById('previewBubble');
  const content = document.getElementById('previewContent');
  const position = document.getElementById('previewPosition');
  const previous = document.getElementById('previewPrevious');
  const next = document.getElementById('previewNext');
  let active = null;
  let request = null;
  let generation = 0;
  let lastTouch = 0;
  let lastPointerType = 'mouse';
  let pointerX = null;
  let pointerY = null;
  let pendingHover = null;
  let pendingFocus = null;
  let pendingTouchDismiss = null;
  const cursors = new Map();
  const suppressFocus = new WeakSet();
  function cancelHover() {
    if (!pendingHover) return;
    clearTimeout(pendingHover.timer);
    pendingHover = null;
  }
  function cancelFocus() {
    clearTimeout(pendingFocus);
    pendingFocus = null;
  }
  function visibleCard(state = active) {
    if (!state?.card.isConnected || state.card.hidden || !state.card.getClientRects().length) return false;
    const rect = state.thumbnail.getBoundingClientRect();
    const header = document.querySelector('.app-header')?.getBoundingClientRect().bottom || 0;
    const footer = document.getElementById('versionFooter')?.getBoundingClientRect().top || innerHeight;
    return rect.bottom > header && rect.top < footer && rect.right > 0 && rect.left < innerWidth;
  }
  function close(returnFocus = false) {
    cancelHover();
    cancelFocus();
    if (!active) return;
    const prior = active;
    generation++;
    request?.abort(); request = null;
    active = null;
    bubble.hidden = true;
    prior.trigger.setAttribute('aria-expanded', 'false');
    if (returnFocus && prior.focusReturn && visibleCard(prior)) {
      suppressFocus.add(prior.trigger);
      prior.trigger.focus();
    }
  }
  function focusNavigation() {
    if (!active?.focusReturn) return;
    if (active.focusedControl && !active.focusedControl.disabled) active.focusedControl.focus();
    else if (!next.disabled) next.focus();
    else if (!previous.disabled) previous.focus();
    else bubble.focus();
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
    const side = rightRoom >= 495 || rightRoom >= leftRoom ? 'right' : 'left';
    const room = side === 'right' ? rightRoom : leftRoom;
    const displayed = content.firstElementChild;
    const sourceWidth = displayed?.tagName === 'IMG' && displayed.naturalWidth ? displayed.naturalWidth + 22 : 495;
    const width = Math.max(100, Math.min(495, room, sourceWidth));
    bubble.style.width = `${width}px`;
    const availableHeight = Math.max(0, bottomBound - topBound);
    bubble.style.maxHeight = `${availableHeight}px`;
    bubble.style.height = `${availableHeight}px`;
    const chromeHeight = bubble.getBoundingClientRect().height - content.clientHeight;
    const contentHeight = displayed?.getBoundingClientRect().height || 0;
    const height = Math.min(availableHeight, Math.ceil(Math.max(72, contentHeight) + chromeHeight));
    bubble.style.height = `${height}px`;
    bubble.style.left = `${side === 'right' ? anchor.right + gap : anchor.left - gap - width}px`;
    bubble.style.top = `${Math.max(topBound, Math.min(bottomBound - height, anchor.top + anchor.height / 2 - height / 2))}px`;
    bubble.dataset.side = side;
    const stage = bubble.querySelector('.preview-stage');
    const inset = displayed ? Math.max(0, displayed.getBoundingClientRect().left - stage.getBoundingClientRect().left) : 0;
    stage.style.setProperty('--preview-page-inset', `${inset}px`);
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
    focusNavigation();
  }
  function render(result, token) {
    if (!active) return;
    const owner = active;
    const show = displayed => {
      if (active !== owner || token !== generation) return;
      active.index = result.index;
      active.total = result.total;
      cursors.set(active.id, result.index);
      content.replaceChildren(displayed);
      position.textContent = `${result.label}${result.approximate ? ' · approximate restore' : ''}`;
      previous.disabled = result.index <= 0;
      next.disabled = result.index >= result.total - 1;
      place();
      focusNavigation();
    };
    if (result.image) {
      const image = document.createElement('img');
      image.alt = result.label;
      image.addEventListener('load', () => show(image), {once: true});
      image.addEventListener('error', () => { if (active === owner && token === generation) showFailure(); }, {once: true});
      image.src = result.image;
    } else {
      const excerpt = document.createElement('div'); excerpt.className = 'preview-excerpt';
      excerpt.innerHTML = result.html;
      excerpt.querySelectorAll('a').forEach(link => link.removeAttribute('href'));
      excerpt.querySelectorAll('img').forEach(image => image.addEventListener('load', () => {
        if (active === owner && active.index === result.index && excerpt.isConnected) place();
      }));
      show(excerpt);
    }
  }
  async function load(index = null, opening = false) {
    if (!active) return;
    const owner = active;
    const token = ++generation;
    request?.abort(); request = new AbortController();
    if (opening || content.firstElementChild?.tagName !== 'IMG') {
      content.textContent = 'Loading preview…'; position.textContent = 'Loading preview…';
    }
    previous.disabled = true; next.disabled = true;
    const base = `/api/documents/${encodeURIComponent(owner.id)}/preview`;
    const url = opening ? `${base}${index ? `?index=${index}` : ''}` : `${base}/location/${index}`;
    try {
      const response = await fetch(url, {signal: request.signal, credentials: 'same-origin'});
      if (!response.ok) throw new Error(`Preview request failed (${response.status})`);
      const result = await response.json();
      if (token !== generation || active !== owner || !visibleCard(owner)) return;
      render(result, token);
    } catch (error) {
      if (token === generation && active === owner && error.name !== 'AbortError') showFailure();
    }
  }
  function open(id, card, thumbnail, trigger, focusReturn = false, pointerEvent = null) {
    if (!focusReturn && Date.now() - lastTouch < 600) return;
    if (pointerEvent) { pointerX = pointerEvent.clientX; pointerY = pointerEvent.clientY; }
    if (active?.id === id && active.card === card) { if (focusReturn) { active.focusReturn = true; focusNavigation(); } return; }
    close();
    window.tomeshedBookshelves?.closePreview();
    active = {id, card, thumbnail, trigger, focusReturn, pointerInside: Boolean(pointerEvent), index: cursors.get(id) ?? 0, total: 0};
    bubble.hidden = false;
    bubble.dataset.pointerType = pointerEvent?.pointerType || lastPointerType;
    trigger.setAttribute('aria-expanded', 'true');
    place();
    if (focusReturn) bubble.focus();
    load(active.index, true);
  }
  function scheduleHover(id, card, thumbnail, trigger, event) {
    if (event.buttons || document.body.classList.contains('reader-open') || Date.now() - lastTouch < 600) {
      cancelHover();
      return;
    }
    if (active?.id === id && active.card === card) return;
    if (pendingHover?.id === id && pendingHover.card === card) {
      pendingHover.x = event.clientX;
      pendingHover.y = event.clientY;
      return;
    }
    cancelHover();
    const pending = {id, card, thumbnail, x: event.clientX, y: event.clientY, pointerType: event.pointerType};
    pending.timer = setTimeout(() => {
      if (pendingHover !== pending) return;
      pendingHover = null;
      if (!visibleCard(pending) || document.body.classList.contains('reader-open')) return;
      const bounds = thumbnail.getBoundingClientRect();
      if (pending.x < bounds.left || pending.x > bounds.right || pending.y < bounds.top || pending.y > bounds.bottom) return;
      open(id, card, thumbnail, trigger, false, {clientX: pending.x, clientY: pending.y, pointerType: pending.pointerType});
    }, 800);
    pendingHover = pending;
  }
  function scheduleFocus(id, card, thumbnail, trigger) {
    cancelFocus();
    if (suppressFocus.delete(trigger) || !trigger.matches(':focus-visible')) return;
    pendingFocus = setTimeout(() => {
      pendingFocus = null;
      if (document.activeElement === trigger && visibleCard({card, thumbnail}) &&
          !document.body.classList.contains('reader-open')) open(id, card, thumbnail, trigger, true);
    }, 800);
  }
  function move(delta) {
    if (!active) return;
    const index = active.index + delta;
    if (index >= 0 && index < active.total) {
      if (active.focusReturn) active.focusedControl = delta < 0 ? previous : next;
      load(index);
    }
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
    lastPointerType = event.pointerType;
    bubble.dataset.pointerType = event.pointerType;
    pointerX = event.clientX; pointerY = event.clientY;
    if (!active) return;
    active.pointerInside = inBridge(event.clientX, event.clientY);
    if (!active.pointerInside && !active.card.contains(document.activeElement) && !bubble.contains(document.activeElement)) close();
  });
  document.addEventListener('pointerdown', event => {
    cancelHover();
    cancelFocus();
    lastPointerType = event.pointerType;
    bubble.dataset.pointerType = event.pointerType;
    if (event.pointerType === 'touch') {
      lastTouch = Date.now();
      pendingTouchDismiss = null;
      if (active && !active.card.contains(event.target) && !bubble.contains(event.target)) {
        pendingTouchDismiss = active;
        close();
      }
    }
  }, true);
  document.addEventListener('click', () => {
    const prior = pendingTouchDismiss;
    pendingTouchDismiss = null;
    if (prior?.focusReturn && visibleCard(prior) && document.activeElement === document.body) {
      suppressFocus.add(prior.trigger);
      prior.trigger.focus();
    }
  });
  document.addEventListener('pointercancel', () => { pendingTouchDismiss = null; }, true);
  document.addEventListener('dragstart', cancelHover, true);
  document.addEventListener('pointerleave', event => {
    if (event.pointerType === 'touch') return;
    cancelHover();
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
  window.addEventListener('resize', () => place(true));
  window.addEventListener('scroll', () => place(true), true);
  window.tomeshedPreview = {open, close, scheduleHover, cancelHover, scheduleFocus, cancelFocus, isOpen: () => Boolean(active)};
})();
