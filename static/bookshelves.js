(() => {
  const $ = id => document.getElementById(id);
  const dialog = $('bookshelfDialog');
  const body = $('bookshelfDialogBody');
  const status = $('bookshelfStatus');
  let snapshot = {owned: [], shared: [], order_revision: 0};
  let active = null;
  let mode = null;
  let draft = null;
  let searchGeneration = 0;
  const previewBubble = $('bookshelfPreviewBubble');
  const previewGrid = $('bookshelfPreviewGrid');
  previewGrid.tabIndex = 0;
  previewGrid.setAttribute('aria-label', 'Bookshelf documents');
  const previewTitle = $('bookshelfPreviewTitle');
  const previewClose = $('bookshelfPreviewClose');
  let previewActive = null;
  let previewHover = null;
  let previewFocusTimer = null;
  let previewRequest = null;
  let previewGeneration = 0;
  let previewPointerX = null;
  let previewPointerY = null;
  let lastTouch = 0;
  const suppressPreviewFocus = new WeakSet();

  function node(tag, className, value) { const item = document.createElement(tag); if (className) item.className = className; if (value !== undefined) item.textContent = value; return item; }
  function button(label, action, className = '') { const item = node('button', className, label); item.type = 'button'; item.addEventListener('click', action); return item; }
  async function request(path, options = {}) {
    const response = await fetch(path, {credentials: 'same-origin', ...options});
    const value = await response.json().catch(() => ({}));
    if (!response.ok) { const error = new Error(value.error || `Request failed (${response.status})`); error.status = response.status; error.current = value.current; throw error; }
    return value;
  }
  const json = (method, value) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(value)});
  function report(message) { status.textContent = message; }
  function reveal(title, content) { $('bookshelfDialogTitle').textContent = title; body.replaceChildren(...content); report(''); if (!dialog.open) dialog.showModal(); }
  function close() { if (dialog.open) dialog.close(); active = null; mode = null; draft = null; }
  $('closeBookshelfDialog').addEventListener('click', close);
  dialog.addEventListener('close', () => { active = null; mode = null; draft = null; });

  function cover(documentId) { const img = node('img', 'bookshelf-cover'); img.alt = ''; img.loading = 'lazy'; img.src = `/api/documents/${encodeURIComponent(documentId)}/thumbnail`; img.addEventListener('error', () => img.remove()); return img; }
  function cancelPreviewHover() { clearTimeout(previewHover?.timer); previewHover = null; }
  function cancelPreviewFocus() { clearTimeout(previewFocusTimer); previewFocusTimer = null; }
  function visiblePreviewCard(state = previewActive) {
    if (!state?.card.isConnected || !state.card.getClientRects().length) return false;
    const rect = state.trigger.getBoundingClientRect();
    const header = document.querySelector('.app-header')?.getBoundingClientRect().bottom || 0;
    const footer = $('versionFooter')?.getBoundingClientRect().top || innerHeight;
    return rect.bottom > header && rect.top < footer && rect.right > 0 && rect.left < innerWidth;
  }
  function closePreview(returnFocus = false) {
    cancelPreviewHover(); cancelPreviewFocus();
    if (!previewActive) return;
    const prior = previewActive;
    previewActive = null; previewGeneration++;
    previewRequest?.abort(); previewRequest = null;
    previewBubble.hidden = true;
    prior.trigger.setAttribute('aria-expanded', 'false');
    if (returnFocus && prior.focusReturn && visiblePreviewCard(prior)) {
      suppressPreviewFocus.add(prior.trigger);
      prior.trigger.focus();
    }
  }
  function inPreviewBridge(x, y) {
    if (!previewActive) return false;
    const anchor = previewActive.trigger.getBoundingClientRect();
    const card = previewActive.card.getBoundingClientRect();
    const bubble = previewBubble.getBoundingClientRect();
    const inside = rect => x >= rect.left - 2 && x <= rect.right + 2 && y >= rect.top - 2 && y <= rect.bottom + 2;
    if (inside(card) || inside(bubble)) return true;
    const left = Math.min(anchor.right, bubble.right);
    const right = Math.max(anchor.left, bubble.left);
    return x >= left - 2 && x <= right + 2 &&
      y >= Math.max(anchor.top, bubble.top) - 2 && y <= Math.min(anchor.bottom, bubble.bottom) + 2;
  }
  function placePreview() {
    if (!previewActive || !visiblePreviewCard()) { closePreview(); return; }
    const anchor = previewActive.trigger.getBoundingClientRect();
    const header = document.querySelector('.app-header')?.getBoundingClientRect().bottom || 0;
    const footer = $('versionFooter')?.getBoundingClientRect().top || innerHeight;
    const topBound = Math.max(12, header + 8);
    const bottomBound = Math.min(innerHeight - 12, footer - 8);
    const gap = 12;
    const leftRoom = Math.max(0, anchor.left - 12 - gap);
    const rightRoom = Math.max(0, innerWidth - anchor.right - 12 - gap);
    const side = rightRoom >= 380 || rightRoom >= leftRoom ? 'right' : 'left';
    const room = side === 'right' ? rightRoom : leftRoom;
    const margin = Math.min(12, Math.floor(innerWidth / 4));
    const maxWidth = Math.max(1, innerWidth - margin * 2);
    const minimumWidth = Math.min(100, maxWidth);
    const width = Math.min(maxWidth, Math.max(minimumWidth, Math.min(380, room)));
    previewBubble.style.minWidth = `${minimumWidth}px`;
    previewBubble.style.width = `${width}px`;
    const availableHeight = Math.max(0, bottomBound - topBound);
    previewBubble.style.maxHeight = `${availableHeight}px`;
    previewBubble.style.height = `${availableHeight}px`;
    const chromeHeight = previewBubble.getBoundingClientRect().height - previewGrid.clientHeight;
    const tiles = [...previewGrid.querySelectorAll('.bookshelf-preview-tile')].slice(0, 4);
    const visibleContent = tiles.length ? tiles : [...previewGrid.children];
    const gridBox = previewGrid.getBoundingClientRect();
    const gridHeight = visibleContent.length
      ? Math.max(...visibleContent.map(item => item.getBoundingClientRect().bottom - gridBox.top + previewGrid.scrollTop +
        (parseFloat(getComputedStyle(item).marginBottom) || 0))) +
        (parseFloat(getComputedStyle(previewGrid).paddingBottom) || 0)
      : previewGrid.scrollHeight;
    const height = Math.min(availableHeight, Math.max(100, Math.ceil(gridHeight + chromeHeight)));
    previewBubble.style.height = `${height}px`;
    const beside = side === 'right' ? anchor.right + gap : anchor.left - gap - width;
    previewBubble.style.left = `${Math.max(margin, Math.min(innerWidth - margin - width, beside))}px`;
    previewBubble.style.top = `${Math.max(topBound, Math.min(bottomBound - height, anchor.top + anchor.height / 2 - height / 2))}px`;
    previewBubble.dataset.side = side;
    const box = previewBubble.getBoundingClientRect();
    previewBubble.style.setProperty('--preview-pointer-y', `${Math.max(16, Math.min(box.height - 16, anchor.top + anchor.height / 2 - box.top))}px`);
    if (previewActive.pointerInside && previewPointerX !== null && !inPreviewBridge(previewPointerX, previewPointerY) &&
        !previewActive.card.contains(document.activeElement) && !previewBubble.contains(document.activeElement)) closePreview();
  }
  function previewTile(item) {
    const tile = node('div', 'bookshelf-preview-tile');
    tile.setAttribute('role', 'img'); tile.setAttribute('aria-label', item.title);
    const art = node('div', 'bookshelf-preview-art');
    const fallback = () => { art.replaceChildren(node('span', 'bookshelf-preview-fallback', item.source_type.toUpperCase())); };
    if (item.thumbnail_available) {
      const image = node('img'); image.alt = ''; image.loading = 'lazy';
      image.addEventListener('error', fallback);
      image.src = `/api/documents/${encodeURIComponent(item.id)}/thumbnail`;
      art.append(image);
    } else fallback();
    tile.append(art, node('span', 'bookshelf-preview-name', item.title));
    return tile;
  }
  async function openPreview(shelf, card, trigger, focusReturn = false, pointer = null) {
    if (!focusReturn && Date.now() - lastTouch < 600) return;
    if (previewActive?.id === shelf.id && previewActive.card === card) {
      if (focusReturn) { previewActive.focusReturn = true; previewClose.focus(); }
      return;
    }
    closePreview(); window.tomeshedPreview?.close();
    if (pointer) { previewPointerX = pointer.clientX; previewPointerY = pointer.clientY; }
    previewActive = {id: shelf.id, card, trigger, focusReturn, pointerInside: Boolean(pointer)};
    const owner = previewActive;
    const generation = ++previewGeneration;
    previewBubble.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    previewTitle.textContent = shelf.name;
    previewGrid.replaceChildren(node('p', 'bookshelf-preview-message', 'Loading bookshelf…'));
    placePreview();
    if (focusReturn) previewClose.focus();
    previewRequest = new AbortController();
    try {
      const detail = await request(`/api/bookshelves/${encodeURIComponent(shelf.id)}`, {signal: previewRequest.signal});
      if (generation !== previewGeneration || previewActive !== owner || !visiblePreviewCard(owner)) return;
      previewTitle.textContent = `${detail.name} · ${detail.members.length} visible`;
      previewGrid.replaceChildren(...(detail.members.length ? detail.members.map(previewTile) : [node('p', 'bookshelf-preview-message', 'No visible documents')]));
      previewGrid.scrollTop = 0;
      placePreview();
    } catch (error) {
      if (generation !== previewGeneration || previewActive !== owner || error.name === 'AbortError') return;
      previewGrid.replaceChildren(node('p', 'bookshelf-preview-message', 'Bookshelf preview unavailable'));
      placePreview();
    }
  }
  function schedulePreviewHover(shelf, card, trigger, event) {
    if (event.buttons || document.body.classList.contains('reader-open') || Date.now() - lastTouch < 600) { cancelPreviewHover(); return; }
    if (previewActive?.id === shelf.id && previewActive.card === card) return;
    if (previewHover?.id === shelf.id && previewHover.card === card) {
      previewHover.x = event.clientX; previewHover.y = event.clientY; return;
    }
    cancelPreviewHover();
    const pending = {id: shelf.id, card, trigger, x: event.clientX, y: event.clientY};
    pending.timer = setTimeout(() => {
      if (previewHover !== pending) return;
      previewHover = null;
      if (!visiblePreviewCard(pending) || document.body.classList.contains('reader-open')) return;
      const box = trigger.getBoundingClientRect();
      if (pending.x < box.left || pending.x > box.right || pending.y < box.top || pending.y > box.bottom) return;
      openPreview(shelf, card, trigger, false, {clientX: pending.x, clientY: pending.y});
    }, 800);
    previewHover = pending;
  }
  function schedulePreviewFocus(shelf, card, trigger) {
    cancelPreviewFocus();
    if (suppressPreviewFocus.delete(trigger) || !trigger.matches(':focus-visible')) return;
    previewFocusTimer = setTimeout(() => {
      previewFocusTimer = null;
      if (document.activeElement === trigger && visiblePreviewCard({card, trigger}) &&
          !document.body.classList.contains('reader-open')) openPreview(shelf, card, trigger, true);
    }, 800);
  }
  function card(shelf) {
    const item = node('article', 'bookshelf-card'); item.dataset.bookshelfId = shelf.id; item.dataset.owned = String(shelf.owned);
    let suppressTouchClick = false;
    const primary = button('', event => {
      if (suppressTouchClick) { event.preventDefault(); suppressTouchClick = false; return; }
      closePreview(); openDetail(shelf.id);
    }, 'bookshelf-card-open');
    primary.setAttribute('aria-label', `Open bookshelf ${shelf.name}, ${shelf.count} visible ${shelf.count === 1 ? 'document' : 'documents'}`);
    primary.setAttribute('aria-controls', 'bookshelfPreviewBubble'); primary.setAttribute('aria-expanded', 'false');
    primary.addEventListener('pointerenter', event => {
      if (event.pointerType === 'mouse' || event.pointerType === 'pen') schedulePreviewHover(shelf, item, primary, event);
    });
    primary.addEventListener('pointermove', event => {
      if (event.pointerType === 'mouse' || event.pointerType === 'pen') schedulePreviewHover(shelf, item, primary, event);
    });
    primary.addEventListener('pointerleave', cancelPreviewHover);
    primary.addEventListener('focus', () => schedulePreviewFocus(shelf, item, primary));
    primary.addEventListener('blur', cancelPreviewFocus);
    let holdTimer = null;
    let holdStart = null;
    const cancelHold = () => { clearTimeout(holdTimer); holdTimer = null; holdStart = null; };
    primary.addEventListener('pointerdown', event => {
      if (event.pointerType !== 'touch') return;
      cancelHold(); suppressTouchClick = false;
      holdStart = {x: event.clientX, y: event.clientY};
      holdTimer = setTimeout(() => {
        holdTimer = null;
        if (!item.isConnected || document.body.classList.contains('reader-open')) return;
        suppressTouchClick = true;
        openPreview(shelf, item, primary, true);
      }, 800);
    });
    primary.addEventListener('pointermove', event => {
      if (event.pointerType === 'touch' && holdStart &&
          Math.hypot(event.clientX - holdStart.x, event.clientY - holdStart.y) > 12) cancelHold();
    });
    primary.addEventListener('pointerup', () => { cancelHold(); setTimeout(() => { suppressTouchClick = false; }, 500); });
    primary.addEventListener('pointercancel', cancelHold);
    primary.addEventListener('contextmenu', event => { if (holdStart || suppressTouchClick) event.preventDefault(); });
    const mosaic = node('span', `bookshelf-mosaic count-${Math.min(4, shelf.covers.length)}`);
    if (shelf.covers.length) shelf.covers.forEach(id => mosaic.append(cover(id)));
    else mosaic.append(node('span', 'bookshelf-empty-preview', 'No visible documents'));
    primary.append(mosaic, node('span', 'bookshelf-marker', 'Bookshelf'));
    item.append(primary, node('h3', '', shelf.name));
    return item;
  }
  async function refresh() {
    try {
      snapshot = await request('/api/bookshelves');
      if (dialog.open && mode === 'detail' && active) await openDetail(active);
    } catch (error) { $('libraryError').textContent = `Bookshelves could not be loaded: ${error.message}`; $('libraryError').hidden = false; }
  }
  async function moveShelf(index, direction) {
    const ids = snapshot.owned.map(item => item.id);
    const target = index + direction; if (target < 0 || target >= ids.length) return;
    const movedId = ids[index];
    [ids[index], ids[target]] = [ids[target], ids[index]];
    try {
      await request('/api/bookshelves/order', json('PUT', {expected_revision: snapshot.order_revision, ids}));
      await refresh();
      await window.tomeshedCatalog.refresh();
      const row = body.querySelector(`.bookshelf-order-item[data-bookshelf-id="${CSS.escape(movedId)}"]`);
      const movedButton = row?.querySelector(direction < 0 ? '.bookshelf-move-up' : '.bookshelf-move-down');
      (movedButton?.disabled ? row.querySelector('button:not(:disabled)') : movedButton)?.focus();
      report(`Bookshelf moved to position ${target + 1}.`);
    } catch (error) { await refresh(); report(`Bookshelf order changed: ${error.message}`); }
  }
  async function deleteShelf(shelf) {
    if (!confirm(`Delete ${shelf.name}? Its documents and reading positions will remain in the library.`)) return;
    try { await request(`/api/bookshelves/${encodeURIComponent(shelf.id)}`, json('DELETE', {confirm: shelf.name})); close(); await refresh(); await window.tomeshedCatalog.refresh(); }
    catch (error) { $('libraryError').textContent = error.message; $('libraryError').hidden = false; }
  }
  async function readerOpen(documentId, shelfId, opener) {
    const data = await request(`/api/documents/${encodeURIComponent(documentId)}`);
    close(); window.tomeshedPreview.close(); window.tomeshedReader.open(data, opener, shelfId);
  }
  async function continueReading(shelfId, opener) {
    try { const target = await request(`/api/bookshelves/${encodeURIComponent(shelfId)}/continue`, {method: 'POST'}); await readerOpen(target.document_id, shelfId, opener); await refresh(); }
    catch (error) { report(`Continue reading failed: ${error.message}`); await refresh(); }
  }
  async function openDetail(shelfId) {
    closePreview();
    try {
      const shelf = await request(`/api/bookshelves/${encodeURIComponent(shelfId)}`);
      if (shelf.owned && !snapshot.owned.some(item => item.id === shelfId)) snapshot = await request('/api/bookshelves');
      active = shelfId; mode = 'detail';
      const contents = [];
      const summary = node('p', '', `${shelf.count} visible ${shelf.count === 1 ? 'document' : 'documents'}`); contents.push(summary);
      contents.push(button('Continue reading', () => continueReading(shelf.id, dialog), 'primary'));
      contents.at(-1).disabled = !shelf.continue_document_id;
      if (!shelf.members.length) contents.push(node('p', 'bookshelf-empty', 'No visible documents in this bookshelf.'));
      else {
        const list = node('ol', 'bookshelf-members');
        shelf.members.forEach(member => {
          const row = node('li', 'bookshelf-member');
          if (member.thumbnail_available) row.append(cover(member.id));
          const description = node('span', '', `${member.title} · ${member.source_type.toUpperCase()} · ${member.reading_state.replace('_', ' ')}`);
          row.append(description, button('Open', () => readerOpen(member.id, shelf.id, row)));
          list.append(row);
        }); contents.push(list);
      }
      if (shelf.owned) {
        contents.push(button('Edit bookshelf', () => openEditor(shelf.id)));
        contents.push(button('Delete bookshelf', () => deleteShelf(shelf), 'danger'));
        const manager = node('section', 'bookshelf-order-manager');
        manager.setAttribute('aria-label', 'Arrange bookshelves');
        manager.append(node('h3', '', 'Arrange bookshelves'));
        const order = node('ol', 'bookshelf-order-list');
        snapshot.owned.forEach((ownedShelf, index) => {
          const row = node('li', 'bookshelf-order-item'); row.dataset.bookshelfId = ownedShelf.id;
          row.append(node('span', '', ownedShelf.name));
          const up = button('Move bookshelf up', () => moveShelf(index, -1), 'bookshelf-move-up'); up.disabled = index === 0;
          const down = button('Move bookshelf down', () => moveShelf(index, 1), 'bookshelf-move-down'); down.disabled = index === snapshot.owned.length - 1;
          row.append(up, down); order.append(row);
        });
        manager.append(order); contents.push(manager);
      }
      reveal(shelf.name, contents);
    } catch (error) { if (error.status === 404) close(); else report(error.message); await refresh(); }
  }

  function editorMemberRow(entry, index) {
    const row = node('li', 'bookshelf-editor-member'); row.dataset.memberKey = entry.member_id || entry.document?.id || '';
    if (entry.unavailable) row.append(node('span', '', 'Unavailable document'));
    else row.append(node('span', '', `${entry.document.title} · ${entry.document.source_type.toUpperCase()}`));
    row.append(button('Move member up', () => moveMember(index, -1)));
    row.append(button('Move member down', () => moveMember(index, 1)));
    row.children[row.children.length - 2].disabled = index === 0;
    row.children[row.children.length - 1].disabled = index === draft.members.length - 1;
    row.append(button('Remove member', () => { draft.members.splice(index, 1); renderEditor(); }));
    return row;
  }
  function moveMember(index, direction) {
    const target = index + direction; if (target < 0 || target >= draft.members.length) return;
    [draft.members[index], draft.members[target]] = [draft.members[target], draft.members[index]];
    renderEditor();
    const row = body.querySelectorAll('.bookshelf-editor-member')[target];
    row?.querySelector(direction < 0 ? 'button:first-of-type' : 'button:nth-of-type(2)')?.focus();
    report(`Member moved to position ${target + 1}`);
  }
  function renderEditor() {
    mode = 'editor';
    const content = [];
    const nameLabel = node('label', 'bookshelf-field', 'Bookshelf name');
    const input = document.createElement('input'); input.id = 'bookshelfName'; input.maxLength = 120; input.value = draft.name; input.addEventListener('input', () => { draft.name = input.value; });
    nameLabel.append(input); content.push(nameLabel);
    const heading = node('h3', '', 'Documents'); content.push(heading);
    const list = node('ol', 'bookshelf-editor-list');
    draft.members.forEach((entry, index) => list.append(editorMemberRow(entry, index)));
    if (!draft.members.length) list.append(node('li', 'bookshelf-empty', 'No documents selected'));
    content.push(list);
    const searchLabel = node('label', 'bookshelf-field', 'Find documents to add');
    const search = document.createElement('input'); search.type = 'search'; search.id = 'bookshelfSearch'; search.placeholder = 'Search title or author';
    searchLabel.append(search); content.push(searchLabel);
    const available = node('div', 'bookshelf-available'); available.id = 'bookshelfAvailable'; content.push(available);
    search.addEventListener('input', () => loadAvailable(search.value));
    content.push(button('Save bookshelf', saveEditor, 'primary'), button('Cancel', close));
    if (draft.id) {
      const shareHeading = node('h3', '', 'Share read-only'); content.push(shareHeading);
      const shareForm = node('form', 'bookshelf-share-form');
      const recipient = document.createElement('input'); recipient.placeholder = 'Exact username'; recipient.setAttribute('aria-label', 'Exact username');
      shareForm.append(recipient, button('Add recipient', () => share(recipient.value)));
      shareForm.addEventListener('submit', event => { event.preventDefault(); share(recipient.value); });
      content.push(shareForm);
      const recipients = node('div', 'bookshelf-recipients');
      draft.shares.forEach(person => recipients.append(node('span', '', person.username), button(`Revoke ${person.username}`, () => revoke(person.id))));
      content.push(recipients);
    }
    reveal(draft.id ? `Edit ${draft.name}` : 'Create bookshelf', content);
    loadAvailable('');
  }
  async function loadAvailable(query) {
    const generation = ++searchGeneration;
    try {
      const data = await request(`/api/documents?q=${encodeURIComponent(query)}&scope=documents&limit=24`);
      if (generation !== searchGeneration || mode !== 'editor') return;
      const target = $('bookshelfAvailable'); if (!target) return;
      target.replaceChildren();
      for (const item of data.documents) {
        if (draft.members.some(member => member.document?.id === item.id)) continue;
        target.append(button(`Add ${item.title}`, () => { draft.members.push({member_id:null,document:item,unavailable:false}); renderEditor(); }));
      }
      if (!target.children.length) target.append(node('p', '', 'No more matching documents.'));
    } catch (error) { report(error.message); }
  }
  async function openEditor(shelfId = null) {
    try {
      const shelf = shelfId ? await request(`/api/bookshelves/${encodeURIComponent(shelfId)}`) : null;
      active = shelfId;
      draft = {id:shelfId, name:shelf?.name || '', revision:shelf?.revision || 0,
        members:shelf?.editor_members.map(item => ({...item})) || [], shares:shelf?.shares || []};
      renderEditor(); $('bookshelfName').focus();
    } catch (error) { report(error.message); }
  }
  function memberTokens() { return draft.members.map(item => item.unavailable ? {member_id:item.member_id} : item.document.id); }
  async function saveEditor() {
    try {
      const saved = draft.id ? await request(`/api/bookshelves/${encodeURIComponent(draft.id)}`, json('PUT', {name:draft.name,members:memberTokens(),expected_revision:draft.revision}))
        : await request('/api/bookshelves', json('POST', {name:draft.name,members:memberTokens()}));
      await refresh(); await window.tomeshedCatalog.refresh(); openDetail(saved.id);
    } catch (error) {
      report(error.status === 409 ? 'Another session changed this bookshelf. Review the latest version before saving.' : error.message);
      if (error.status === 409) body.append(button('Load latest version', () => openEditor(draft.id)));
    }
  }
  async function share(username) {
    try { const saved = await request(`/api/bookshelves/${encodeURIComponent(draft.id)}/shares`, json('POST', {username})); draft.shares = saved.shares; renderEditor(); report('Recipient added.'); await window.tomeshedCatalog.refresh(); }
    catch (error) { report(error.message); }
  }
  async function revoke(userId) {
    try { const saved = await request(`/api/bookshelves/${encodeURIComponent(draft.id)}/shares/${userId}`, {method:'DELETE'}); draft.shares=saved.shares; renderEditor(); report('Recipient removed.'); await window.tomeshedCatalog.refresh(); }
    catch (error) { report(error.message); }
  }
  function choose(documentItem) {
    active = null; mode = 'choose';
    const options = [node('p', '', `Add ${documentItem.title} to a bookshelf`)];
    for (const shelf of snapshot.owned) options.push(button(shelf.name, async () => {
      try { await request(`/api/bookshelves/${encodeURIComponent(shelf.id)}/members`, json('POST', {document_id:documentItem.id})); close(); await refresh(); await window.tomeshedCatalog.refresh(); }
      catch (error) { report(error.message); }
    }));
    options.push(button('New bookshelf', () => { draft={id:null,name:'',revision:0,members:[{member_id:null,document:documentItem,unavailable:false}],shares:[]}; renderEditor(); }));
    reveal('Add to bookshelf', options);
  }
  $('createBookshelf').addEventListener('click', () => openEditor());
  document.addEventListener('pointermove', event => {
    if (event.pointerType === 'touch') return;
    previewPointerX = event.clientX; previewPointerY = event.clientY;
    if (!previewActive) return;
    previewActive.pointerInside = inPreviewBridge(event.clientX, event.clientY);
    if (!previewActive.pointerInside && !previewActive.card.contains(document.activeElement) &&
        !previewBubble.contains(document.activeElement)) closePreview();
  });
  document.addEventListener('pointerdown', event => {
    cancelPreviewHover(); cancelPreviewFocus();
    if (event.pointerType === 'touch') lastTouch = Date.now();
  }, true);
  document.addEventListener('pointerleave', event => {
    if (event.pointerType === 'touch') return;
    cancelPreviewHover(); previewPointerX = null; previewPointerY = null;
    if (previewActive && !previewActive.card.contains(document.activeElement) &&
        !previewBubble.contains(document.activeElement)) closePreview();
  });
  document.addEventListener('focusin', event => {
    if (previewActive && !previewActive.pointerInside && !previewActive.card.contains(event.target) &&
        !previewBubble.contains(event.target)) closePreview();
  });
  document.addEventListener('keydown', event => {
    if (previewActive && event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closePreview(true); }
  }, true);
  previewClose.addEventListener('click', () => closePreview(true));
  window.addEventListener('resize', placePreview);
  window.addEventListener('scroll', placePreview, true);
  new MutationObserver(() => { if (previewActive && !previewActive.card.isConnected) closePreview(); })
    .observe($('documentGrid'), {childList: true});
  window.tomeshedBookshelves = {refresh, choose, card, closePreview};
  refresh();
})();
