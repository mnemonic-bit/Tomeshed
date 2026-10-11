(() => {
  const $ = id => document.getElementById(id);
  const overlay = $('reader');
  const scroller = $('readerScroll');
  const body = $('readerContent');
  const status = $('readerPosition');
  const panel = $('readerDocumentPanel');
  const panelContent = $('readerPanelContent');
  const panelErrorNode = $('readerPanelError');
  const controls = ['readerPrevious', 'readerNext', 'readerZoomOut', 'readerZoomIn', 'readerZoomPercent'].map($);
  const zoomField = $('readerZoomPercent');
  let current = null;
  let generation = 0;
  let timer = null;
  let writeQueue = Promise.resolve();
  let scrollFrame = 0;
  let skipScroll = false;
  let panelReturnFocus = null;
  let panelPointerFocus = null;
  let panelMinimized = false;

  function isOpenFor(id) { return Boolean(current && current.id === id && !overlay.hidden); }
  function panelError(id, message) {
    if (!isOpenFor(id)) return;
    panelErrorNode.textContent = message;
    panelErrorNode.hidden = false;
  }
  function updateDocument(item) {
    if (!item || !isOpenFor(item.id)) return;
    current.documentItem = item;
    const scrollTop = panel.scrollTop;
    const active = panel.contains(document.activeElement) ? document.activeElement : null;
    const name = active?.getAttribute('name');
    const label = active?.getAttribute('aria-label') || active?.textContent;
    panelContent.replaceChildren(window.tomeshedCatalog.renderDocumentInfo(item));
    panelContent.querySelector('.reader-panel-details')?.toggleAttribute('inert', panelMinimized);
    panelContent.querySelector('.reader-panel-rail')?.toggleAttribute('inert', !panelMinimized);
    panel.scrollTop = scrollTop;
    $('readerTitle').textContent = item.title;
    panelErrorNode.hidden = true;
    if (active) {
      const next = (name && panel.querySelector(`[name="${CSS.escape(name)}"]`)) ||
        [...panel.querySelectorAll('button, input, select, a')].find(node => (node.getAttribute('aria-label') || node.textContent) === label);
      (next || $('readerPanelMinimize')).focus({preventScroll: true});
    }
  }
  function updateReadingState(item) {
    if (!item || !isOpenFor(item.id)) return;
    current.documentItem = {...current.documentItem, ...item};
    const state = panelContent.querySelector('[data-reader-field="reading-state"] span');
    const lastRead = panelContent.querySelector('[data-reader-field="last-read"] span');
    if (state) state.textContent = current.documentItem.reading_state.replace('_', ' ');
    if (lastRead) lastRead.textContent = current.documentItem.last_read_at
      ? new Date(current.documentItem.last_read_at * 1000).toLocaleString() : 'Never';
  }
  function setPanelMinimized(minimized) {
    const position = current?.opened ? positionNow() : null;
    panelMinimized = minimized;
    if (minimized) {
      panelReturnFocus = panelPointerFocus || (panel.contains(document.activeElement) ? document.activeElement : $('readerPanelMinimize'));
      panelPointerFocus = null;
      current.panelScrollTop = panel.scrollTop;
      panel.classList.add('is-minimized');
      panelContent.querySelector('.reader-panel-details')?.setAttribute('inert', '');
      panelContent.querySelector('.reader-panel-rail')?.removeAttribute('inert');
      $('readerPanelRestore').hidden = false;
      $('readerPanelMinimize').hidden = true;
      $('readerPanelRestore').focus();
    } else {
      panel.classList.remove('is-minimized');
      panelContent.querySelector('.reader-panel-details')?.removeAttribute('inert');
      panelContent.querySelector('.reader-panel-rail')?.setAttribute('inert', '');
      $('readerPanelRestore').hidden = true;
      $('readerPanelMinimize').hidden = false;
      (panelReturnFocus?.isConnected ? panelReturnFocus : $('readerPanelMinimize')).focus({preventScroll: true});
      panel.scrollTop = current.panelScrollTop || 0;
      requestAnimationFrame(() => { if (current) panel.scrollTop = current.panelScrollTop || 0; });
    }
    if (position) requestAnimationFrame(() => { if (current?.opened) restore(position); });
  }

  function endpoint(suffix) { return `/api/documents/${encodeURIComponent(current.id)}/${suffix}`; }
  function clamp(value, minimum, maximum) { return Math.max(minimum, Math.min(maximum, value)); }
  function maximumScroll() { return Math.max(0, scroller.scrollHeight - scroller.clientHeight); }
  function percent() { return maximumScroll() ? clamp(scroller.scrollTop / maximumScroll() * 100, 0, 100) : 0; }
  function visibleElement(selector) {
    const viewport = scroller.getBoundingClientRect();
    let choice = null, area = -1;
    for (const node of body.querySelectorAll(selector)) {
      const box = node.getBoundingClientRect();
      if (selector !== '.pdf-page' && box.bottom > viewport.top + 16 && box.top < viewport.bottom) return node;
      const visibleHeight = Math.max(0, Math.min(box.bottom, viewport.bottom) - Math.max(box.top, viewport.top));
      const visibleWidth = Math.max(0, Math.min(box.right, viewport.right) - Math.max(box.left, viewport.left));
      const visible = visibleHeight * visibleWidth;
      if (visible > area) { area = visible; choice = node; }
    }
    return choice;
  }
  function positionNow() {
    if (!current || !current.content) return null;
    const type = current.content.format;
    const node = visibleElement(type === 'pdf' ? '.pdf-page' : '[data-locator]');
    if (!node) return null;
    const top = node.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop;
    const offset = clamp((scroller.scrollTop - top) / Math.max(1, node.offsetHeight), 0, 1);
    let locator;
    if (type === 'pdf') locator = {page: Number(node.dataset.page), offset};
    else if (type === 'epub') locator = {section: node.dataset.section, element: Number(node.dataset.element), offset};
    else locator = {element: node.dataset.locator, offset};
    return {locator, percent: percent()};
  }
  function label(position, approximate = false) {
    if (!current?.content || !position) return;
    const content = current.content;
    let value;
    if (content.format === 'pdf') value = `Page ${position.locator.page} of ${content.page_count}`;
    else if (content.format === 'epub') {
      const section = content.sections.find(item => item.path === position.locator.section);
      const markerEntries = section ? Object.entries(section.markers).filter(([number]) => Number(number) <= position.locator.element) : [];
      value = markerEntries.length ? `Page ${markerEntries.at(-1)[1]}` : `Location ${position.locator.element} · ${Math.round(position.percent)}%`;
    } else {
      const index = content.elements.findIndex(item => item.ref === position.locator.element);
      const item = content.elements[index];
      value = item?.page ? `Page ${item.page}` : `Location ${index + 1} of ${content.elements.length}`;
    }
    status.textContent = approximate ? `${value} · approximate restore` : value;
  }
  function scheduleSave() {
    if (!current?.opened || skipScroll || Date.now() < (current.suppressUntil || 0)) return;
    current.approximate = false;
    const position = positionNow();
    if (!position) return;
    current.pending = position;
    label(position);
    clearTimeout(timer);
    timer = setTimeout(flushSave, 500);
  }
  function flushSave() {
    clearTimeout(timer); timer = null;
    const id = current?.id;
    const position = current?.pending;
    if (!id || !position) return;
    current.pending = null;
    const url = `/api/documents/${encodeURIComponent(id)}/progress`;
    writeQueue = writeQueue.catch(() => {}).then(() => fetch(url, {
      method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(position), credentials: 'same-origin'
    })).then(response => {
      if (!response.ok && current?.id === id) status.textContent = `Position could not be saved (${response.status})`;
    }).catch(() => {
      if (current?.id === id) status.textContent = 'Position could not be saved';
    });
  }
  function captureLatestMovement() {
    if (current?.opened && Math.abs(scroller.scrollTop - (current.programmaticTop || 0)) > 2) {
      current.pending = positionNow();
    }
  }
  function jump(node, offset = 0, record = true) {
    if (!node) return;
    skipScroll = true;
    current.suppressUntil = Date.now() + 120;
    const top = node.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop;
    scroller.scrollTop = clamp(top + clamp(offset, 0, 1) * node.offsetHeight, 0, maximumScroll());
    current.programmaticTop = scroller.scrollTop;
    setTimeout(() => { skipScroll = false; if (record) scheduleSave(); }, 120);
  }
  function restore(saved) {
    if (!saved) { current.suppressUntil = Date.now() + 120; scroller.scrollTop = 0; current.programmaticTop = 0; label(positionNow()); return; }
    const content = current.content;
    const locator = saved.locator;
    let node = null;
    let approximate = false;
    if (content.format === 'pdf') {
      const page = clamp(locator.page, 1, content.page_count);
      node = body.querySelector(`[data-page="${page}"]`);
      approximate = page !== locator.page;
    } else if (content.format === 'epub') {
      node = [...body.querySelectorAll('[data-locator]')].find(item => item.dataset.section === locator.section && Number(item.dataset.element) === locator.element);
      approximate = !node;
    } else {
      node = [...body.querySelectorAll('[data-locator]')].find(item => item.dataset.locator === locator.element);
      approximate = !node;
    }
    if (approximate && content.format !== 'pdf') {
      current.suppressUntil = Date.now() + 120;
      scroller.scrollTop = maximumScroll() * clamp(saved.percent, 0, 100) / 100;
      current.programmaticTop = scroller.scrollTop;
      node = visibleElement('[data-locator]');
    } else jump(node, locator.offset, false);
    current.approximate = approximate;
    label(positionNow() || saved, approximate);
  }
  function renderPdf(content) {
    content.pages.forEach(([width, height], index) => {
      const page = document.createElement('figure'); page.className = 'pdf-page'; page.dataset.page = String(index + 1);
      page.style.aspectRatio = `${width} / ${height}`;
      page.style.setProperty('--pdf-natural-width', `${width * 1.5}px`);
      const image = document.createElement('img'); image.alt = `Page ${index + 1}`;
      image.loading = index < 3 ? 'eager' : 'lazy';
      image.src = endpoint(`reader/page/${index + 1}`);
      image.addEventListener('error', () => {
        if (current?.opened) showFailure('rendering_error', `Could not render page ${index + 1}.`);
      });
      page.append(image); body.append(page);
    });
  }
  function renderEpub(content) {
    for (const section of content.sections) {
      const wrapper = document.createElement('section'); wrapper.className = 'epub-section';
      wrapper.id = `section-${section.path}`; wrapper.innerHTML = section.html;
      wrapper.querySelectorAll('[data-locator]').forEach(node => {
        const value = node.dataset.locator;
        node.dataset.section = section.path;
        node.dataset.element = value.slice(value.lastIndexOf(':') + 1);
      });
      body.append(wrapper);
    }
    const toc = $('readerToc'); toc.replaceChildren();
    for (const entry of content.toc) {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = entry.label;
      button.addEventListener('click', () => {
        const section = content.sections.find(item => item.path === entry.section);
        const block = entry.fragment && section?.anchors?.[entry.fragment] || 1;
        const target = section && body.querySelector(`[id="loc-${section.index}-${block}"]`);
        jump(target || body.querySelector('.epub-section'), 0);
      });
      toc.append(button);
    }
    toc.hidden = !content.toc.length;
  }
  function renderDocling(content) {
    for (const item of content.elements) {
      const holder = document.createElement('div'); holder.innerHTML = item.html;
      body.append(...holder.children);
    }
  }
  function showFailure(kind, message) {
    current.opened = false;
    clearTimeout(timer); timer = null; current.pending = null;
    body.replaceChildren();
    $('readerToc').hidden = true;
    controls.forEach(control => control.hidden = true);
    $('readerZoom').hidden = true;
    const wording = {source_missing: 'Source missing', rendering_error: 'Rendering error', unsupported_content: 'Unsupported content'};
    $('readerError').textContent = `${wording[kind] || 'Reader error'}: ${message} Use Close to return to the library.`;
    $('readerError').hidden = false;
    status.textContent = wording[kind] || 'Reader error';
  }
  async function open(documentItem, opener, bookshelfId = null) {
    if (current) close();
    const token = ++generation;
    current = {id: documentItem.id, documentItem, opener, bookshelfId, scrollY: window.scrollY, content: null, pending: null, opened: false, zoom: 1};
    body.style.setProperty('--reader-zoom', 1);
    zoomField.value = '100';
    document.body.classList.add('reader-open');
    overlay.hidden = false; body.replaceChildren(); $('readerError').hidden = true;
    panel.classList.toggle('is-minimized', panelMinimized);
    $('readerPanelRestore').hidden = !panelMinimized;
    $('readerPanelMinimize').hidden = panelMinimized;
    panel.scrollTop = 0; panelReturnFocus = null; panelErrorNode.hidden = true;
    panelContent.replaceChildren(window.tomeshedCatalog.renderDocumentInfo(documentItem));
    panelContent.querySelector('.reader-panel-details')?.toggleAttribute('inert', panelMinimized);
    panelContent.querySelector('.reader-panel-rail')?.toggleAttribute('inert', !panelMinimized);
    $('readerToc').hidden = true; controls.forEach(control => control.hidden = false);
    $('readerZoom').hidden = false;
    $('readerTitle').textContent = documentItem.title;
    status.textContent = 'Opening…';
    $('readerClose').focus();
    try {
      await writeQueue;
      if (token !== generation) return;
      const [sourceResponse, progressResponse] = await Promise.all([fetch(endpoint('reader')), fetch(endpoint('progress'))]);
      if (token !== generation) return;
      if (!sourceResponse.ok) {
        const error = await sourceResponse.json(); showFailure(error.state, error.error); return;
      }
      if (!progressResponse.ok) throw new Error('Could not load reading position');
      const content = await sourceResponse.json();
      const progress = await progressResponse.json();
      if (token !== generation) return;
      current.content = content;
      if (content.format === 'pdf') renderPdf(content);
      else if (content.format === 'epub') renderEpub(content);
      else if (content.format === 'docling') renderDocling(content);
      else { showFailure('unsupported_content', 'Unknown document type'); return; }
      if (!body.children.length) { showFailure('unsupported_content', 'The source has no displayable content'); return; }
      if (content.format === 'pdf') {
        const first = body.querySelector('.pdf-page img');
        if (!first) { showFailure('unsupported_content', 'The PDF has no pages'); return; }
        await first.decode();
      }
      await new Promise(resolve => requestAnimationFrame(resolve));
      if (token !== generation || $('readerError').hidden === false) return;
      current.opened = true;
      restore(progress.position);
      current.openPromise = fetch(endpoint('reader-open'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(current.bookshelfId ? {bookshelf_id: current.bookshelfId} : {}), credentials: 'same-origin'}).then(async response => {
        if (!response.ok) throw new Error(`Reader open could not be recorded (${response.status})`);
        const result = await response.json();
        if (token === generation) {
          updateReadingState(result.document);
          window.tomeshedCatalog?.readerState(current.id, result.document);
        }
        if (token === generation) window.tomeshedBookshelves?.refresh();
      }).catch(error => { if (token === generation) status.textContent = error.message; });
    } catch (error) {
      if (token === generation) showFailure('rendering_error', error.message);
    }
  }
  function close() {
    if (!current) return;
    captureLatestMovement();
    flushSave();
    const {id, opener, scrollY} = current;
    ++generation; current = null;
    overlay.hidden = true; document.body.classList.remove('reader-open');
    window.scrollTo(0, scrollY);
    const card = document.querySelector(`.document-card[data-document-id="${CSS.escape(id)}"] .document-open`);
    (card || (opener?.isConnected ? opener : $('librarySearch'))).focus();
  }
  function navigate(direction) {
    if (!current?.opened) return;
    const type = current.content.format;
    const nodes = [...body.querySelectorAll(type === 'pdf' ? '.pdf-page' : type === 'epub' ? '.epub-section' : '[data-locator]')];
    const position = positionNow();
    let index;
    if (type === 'pdf') index = position.locator.page - 1;
    else if (type === 'epub') index = nodes.findIndex(node => node.querySelector(`[data-element="${position.locator.element}"]`)?.dataset.section === position.locator.section);
    else index = nodes.findIndex(node => node.dataset.locator === position.locator.element);
    jump(nodes[clamp(index + direction, 0, nodes.length - 1)]);
  }
  function setZoom(value) {
    if (!current?.opened) return;
    const saved = positionNow();
    current.zoom = clamp(Math.round(value * 10000) / 10000, .65, 2.5);
    body.style.setProperty('--reader-zoom', current.zoom);
    zoomField.value = String(Number((current.zoom * 100).toFixed(2)));
    restore(saved);
  }
  function applyZoomField() {
    if (!current?.opened) return;
    const value = zoomField.value.trim();
    if (/^\d+(?:\.\d+)?$/.test(value) && Number(value) >= 65 && Number(value) <= 250) {
      setZoom(Number(value) / 100);
    } else {
      zoomField.value = String(Number((current.zoom * 100).toFixed(2)));
    }
  }
  $('readerClose').addEventListener('click', close);
  $('readerPanelMinimize').addEventListener('pointerdown', () => {
    panelPointerFocus = panel.contains(document.activeElement) ? document.activeElement : null;
  });
  $('readerPanelMinimize').addEventListener('click', () => setPanelMinimized(true));
  $('readerPanelRestore').addEventListener('click', () => setPanelMinimized(false));
  $('readerPrevious').addEventListener('click', () => navigate(-1));
  $('readerNext').addEventListener('click', () => navigate(1));
  $('readerZoomOut').addEventListener('click', () => setZoom(current.zoom - .15));
  $('readerZoomIn').addEventListener('click', () => setZoom(current.zoom + .15));
  zoomField.addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); applyZoomField(); zoomField.blur(); }
  });
  zoomField.addEventListener('change', applyZoomField);
  scroller.addEventListener('scroll', () => {
    if (current?.opened && Date.now() < (current.suppressUntil || 0)) {
      clearTimeout(current.suppressedScrollTimer);
      const owner = current;
      owner.suppressedScrollTimer = setTimeout(() => {
        if (current === owner && Math.abs(scroller.scrollTop - owner.programmaticTop) > 2) scheduleSave();
      }, Math.max(1, owner.suppressUntil - Date.now() + 2));
      return;
    }
    if (scrollFrame) cancelAnimationFrame(scrollFrame);
    scrollFrame = requestAnimationFrame(scheduleSave);
  }, {passive: true});
  document.addEventListener('keydown', event => {
    if (overlay.hidden || $('bookshelfDialog').open) return;
    if (event.key === 'Escape') { event.preventDefault(); close(); }
    if (event.key === 'Tab') {
      const focusable = [...overlay.querySelectorAll('button, a[href], input, select, textarea, [tabindex="0"]')]
        .filter(node => !node.hidden && !node.disabled && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden');
      if (!focusable.length) return;
      const index = focusable.indexOf(document.activeElement);
      const next = event.shiftKey ? (index <= 0 ? focusable.length - 1 : index - 1)
        : (index < 0 || index === focusable.length - 1 ? 0 : index + 1);
      event.preventDefault();
      focusable[next].focus();
    }
  });
  document.addEventListener('focusin', event => {
    if (!overlay.hidden && !$('bookshelfDialog').open && !overlay.contains(event.target)) $('readerClose').focus();
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { captureLatestMovement(); flushSave(); } });
  window.tomeshedReader = {open, close, isOpenFor, updateDocument, panelError};
})();
