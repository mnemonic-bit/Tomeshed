const $ = id => document.getElementById(id);
const menuButton = $('accountMenuButton');
const menu = $('accountMenu');
const settings = $('settingsPage');
const library = $('libraryPage');
const themeControl = $('prefTheme');
const pageSizeControl = $('prefPageSize');
let catalogPageSize = '10';
let healthInFlight = false;
const header = document.querySelector('.app-header');
const versionFooter = $('versionFooter');
function updateFixedEdges() {
  document.documentElement.style.setProperty('--app-header-height', `${header.getBoundingClientRect().height}px`);
  document.documentElement.style.setProperty('--version-footer-height', `${versionFooter.getBoundingClientRect().height}px`);
}
updateFixedEdges();
const fixedEdgesObserver = new ResizeObserver(updateFixedEdges);
fixedEdgesObserver.observe(header);
fixedEdgesObserver.observe(versionFooter);

function showError(message) { $('settingsSuccess').hidden = true; $('settingsError').textContent = message; $('settingsError').hidden = false; }
function showSuccess(message) { $('settingsError').hidden = true; $('settingsSuccess').textContent = message; $('settingsSuccess').hidden = false; }
function closeMenu(returnFocus = false) { menu.hidden = true; menuButton.setAttribute('aria-expanded', 'false'); if (returnFocus) menuButton.focus(); }
function openMenu() { menu.hidden = false; menuButton.setAttribute('aria-expanded', 'true'); $('settingsMenuItem').focus(); }
menuButton.addEventListener('click', () => menu.hidden ? openMenu() : closeMenu());
menuButton.addEventListener('keydown', event => { if (event.key === 'ArrowDown') { event.preventDefault(); openMenu(); } });
menu.addEventListener('keydown', event => {
  const items = [...menu.querySelectorAll('[role="menuitem"]')];
  const position = items.indexOf(document.activeElement);
  if (event.key === 'Escape') { event.preventDefault(); closeMenu(true); }
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); items[(position + (event.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length].focus(); }
});
document.addEventListener('click', event => { if (!menu.hidden && !menuButton.contains(event.target) && !menu.contains(event.target)) closeMenu(); });
document.addEventListener('keydown', event => { if (event.key === 'Escape' && !menu.hidden) closeMenu(true); });

function applyTheme(preference) {
  const dark = preference === 'dark' || (preference === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.documentElement.dataset.themePref = preference;
  try { localStorage.setItem('theme', preference); } catch (_) {}
}
const colorScheme = matchMedia('(prefers-color-scheme: dark)');
colorScheme.addEventListener('change', () => { if (document.documentElement.dataset.themePref === 'system') applyTheme('system'); });

async function api(path, options = {}) {
  const response = await fetch(path, {credentials: 'same-origin', ...options});
  let data = null;
  try { data = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(data?.error || `Request failed (${response.status})`);
  return data;
}
async function loadPreferences() {
  try {
    const data = await api('/api/preferences');
    themeControl.value = data.theme; applyTheme(data.theme);
    pageSizeControl.value = data.page_size;
    if (catalogPageSize !== data.page_size) { catalogPageSize = data.page_size; loadCatalog(); }
  }
  catch (error) { showError(`Could not load preferences: ${error.message}`); }
}
themeControl.addEventListener('change', () => applyTheme(themeControl.value));
$('saveTheme').addEventListener('click', async () => {
  const selected = themeControl.value;
  try {
    await api('/api/preferences', {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({theme: selected})});
    showSuccess('Theme saved.');
  } catch (error) { themeControl.value = selected; showError(`Theme was not saved: ${error.message}`); }
});
pageSizeControl.addEventListener('change', async () => {
  const selected = pageSizeControl.value;
  try {
    await api('/api/preferences', {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({page_size: selected})});
    catalogPageSize = selected;
    loadCatalog();
    showSuccess('Items per page saved.');
  } catch (error) { pageSizeControl.value = catalogPageSize; showError(`Items per page was not saved: ${error.message}`); }
});
function openSettings() {
  closeMenu(); library.hidden = true; settings.hidden = false; document.body.classList.add('settings-open');
  $('settingsSearchInput').value = ''; filterSettings(); loadPreferences();
  if ($('userList')) loadUsers();
  $('settingsSearchInput').focus();
}
function closeSettings() { settings.hidden = true; library.hidden = false; document.body.classList.remove('settings-open'); menuButton.focus(); requestAnimationFrame(loadVisibleEndless); }
$('settingsMenuItem').addEventListener('click', openSettings);
$('settingsBack').addEventListener('click', closeSettings);
document.addEventListener('keydown', event => { if (event.key === 'Escape' && !settings.hidden && menu.hidden && document.activeElement !== $('settingsSearchInput')) closeSettings(); });
$('logoutMenuItem').addEventListener('click', async () => {
  try {
    const response = await fetch('/logout', {method: 'POST', credentials: 'same-origin', redirect: 'manual'});
    if (response.type !== 'opaqueredirect' && response.status !== 302) throw new Error(`Unexpected response (${response.status})`);
    window.location.assign('/login');
  } catch (error) { closeMenu(); openSettings(); showError(`Sign-out failed: ${error.message}`); }
});

function filterSettings() {
  const query = $('settingsSearchInput').value.trim().toLocaleLowerCase();
  let matches = 0;
  document.querySelectorAll('.settings-section').forEach(section => {
    const header = section.querySelector('h3');
    let rows = 0;
    section.querySelectorAll('[data-search]').forEach(row => { const found = !query || `${row.dataset.search} ${row.textContent}`.toLocaleLowerCase().includes(query); row.hidden = !found; if (found) rows++; });
    const found = !query || `${section.dataset.search} ${header.textContent} ${section.querySelector('.section-intro')?.textContent || ''}`.toLocaleLowerCase().includes(query) || rows > 0;
    section.hidden = !found;
    if (found) matches++;
  });
  $('settingsNoResults').hidden = matches > 0;
  document.querySelectorAll('.settings-nav button').forEach(button => { button.hidden = $(button.dataset.target).hidden; });
}
$('settingsSearchInput').addEventListener('input', filterSettings);
document.querySelectorAll('.settings-nav button').forEach(button => button.addEventListener('click', () => $(button.dataset.target).scrollIntoView({behavior: 'smooth'})));

function formatUptime(seconds) {
  if (!Number.isFinite(seconds)) return 'Uptime unavailable';
  const minutes = Math.floor(seconds / 60), hours = Math.floor(minutes / 60), days = Math.floor(hours / 24);
  return `Uptime ${days ? `${days}d ` : ''}${hours % 24}h ${minutes % 60}m`;
}
async function checkHealth() {
  if (healthInFlight || document.hidden) return;
  healthInFlight = true;
  try {
    const response = await api('/api/health');
    $('versionFooter').classList.remove('server-unavailable');
    $('connectionStatus').textContent = 'Connected';
    const version = typeof response.version === 'string' && response.version.trim() ? response.version.trim() : null;
    $('apiVersion').textContent = version ? `API v${version}` : 'API version unavailable';
    $('apiUptime').textContent = formatUptime(response.uptime_seconds);
    const uiVersion = $('versionFooter').dataset.uiVersion;
    const mismatch = Boolean(uiVersion && version && uiVersion !== version);
    $('versionWarning').hidden = !mismatch;
    $('versionWarningText').textContent = mismatch ? `Version mismatch: UI v${uiVersion}, API v${version}.` : '';
  } catch (_) {
    $('versionFooter').classList.add('server-unavailable');
    $('connectionStatus').textContent = 'Connection error';
    $('apiVersion').textContent = 'API version unavailable';
    $('apiUptime').textContent = 'Uptime unavailable';
    $('versionWarning').hidden = true;
  } finally { healthInFlight = false; }
}
document.addEventListener('visibilitychange', () => { if (!document.hidden) checkHealth(); });
checkHealth(); setInterval(checkHealth, 25000);

function element(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text != null) node.textContent = text; return node; }
function userControl(label, value, type = 'text') { const wrapper = element('label', '', label); const input = document.createElement(type === 'select' ? 'select' : 'input'); if (type !== 'select') input.type = type; if (type === 'select') { for (const [key, text] of [['normal', 'Normal'], ['admin', 'Administrator']]) { const option = element('option', '', text); option.value = key; input.append(option); } } input.value = value; wrapper.append(input); return [wrapper, input]; }
async function loadUsers() {
  if (!$('userList')) return;
  try { const data = await api('/api/users'); renderUsers(data.users); }
  catch (error) { showError(`Could not load accounts: ${error.message}`); }
}
function renderUsers(users) {
  const list = $('userList'); list.replaceChildren();
  for (const user of users) {
    const card = element('article', 'user-card');
    const heading = element('div', 'user-card-header');
    heading.append(element('strong', '', user.name), element('span', '', `${user.username} · ${user.role} · ${user.suspended ? 'Suspended' : 'Active'}`)); card.append(heading);
    const edit = element('div', 'user-edit');
    const [nameLabel, name] = userControl('Display name', user.name);
    const [usernameLabel, username] = userControl('Username', user.username);
    const [roleLabel, role] = userControl('Role', user.role, 'select');
    const [passwordLabel, password] = userControl('New password', '', 'password'); password.placeholder = 'Leave blank to keep current'; password.autocomplete = 'new-password';
    edit.append(nameLabel, usernameLabel, roleLabel, passwordLabel); card.append(edit);
    const actions = element('div', 'user-actions');
    const save = element('button', '', 'Save changes');
    save.addEventListener('click', async () => { const changes = {name: name.value, username: username.value, role: role.value}; if (password.value) changes.password = password.value; await changeUser(user.id, changes, 'Account updated.'); });
    const toggle = element('button', '', user.suspended ? 'Reactivate' : 'Suspend');
    toggle.addEventListener('click', () => changeUser(user.id, {suspended: !user.suspended}, user.suspended ? 'Account reactivated.' : 'Account suspended.'));
    const remove = element('button', 'danger', 'Remove');
    remove.addEventListener('click', async () => { if (!confirm(`Remove ${user.username}?`)) return; try { await api(`/api/users/${user.id}`, {method: 'DELETE'}); showSuccess('Account removed.'); loadUsers(); } catch (error) { showError(`Account was not removed: ${error.message}`); } });
    actions.append(save, toggle, remove); card.append(actions); list.append(card);
  }
}
async function changeUser(id, changes, message) {
  try { await api(`/api/users/${id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(changes)}); showSuccess(message); loadUsers(); }
  catch (error) { showError(`Account was not changed: ${error.message}`); }
}
if ($('addUserForm')) $('addUserForm').addEventListener('submit', async event => {
  event.preventDefault(); const form = event.currentTarget;
  try { await api('/api/users', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(Object.fromEntries(new FormData(form)))}); form.reset(); showSuccess('Account added.'); loadUsers(); }
  catch (error) { showError(`Account was not added: ${error.message}`); }
});
loadPreferences();

let catalogPage = 0;
let catalogEffectivePageSize = 10;
let catalogLoaded = 0;
let catalogTotal = 0;
let catalogLoading = false;
let catalogSignature = '';
let catalogGeneration = 0;
let searchTimer;
let availableTags = [];
let pendingCatalogMutation = 0;
let deferredCatalogRefresh = false;
const catalogItems = new Map();
let selectedDocumentId = null;
function updateDocumentSelection(card) {
  const item = catalogItems.get(card.dataset.documentId);
  if (!item) return;
  const selected = selectedDocumentId === item.id;
  card.classList.toggle('document-selected', selected);
  card.querySelector('.document-open').setAttribute('aria-pressed', String(selected));
  card.querySelector('.document-selected-open').hidden = !selected;
  card.querySelector('.document-selection-badge, .document-new-badge')?.remove();
  if (selected) {
    const badge = element('span', 'document-selection-badge', '✓');
    badge.setAttribute('aria-hidden', 'true');
    card.append(badge);
  } else if (item.reading_state === 'unread') card.append(element('span', 'document-new-badge', 'new'));
}
function selectDocument(id) {
  const previous = selectedDocumentId;
  selectedDocumentId = id === previous ? null : id;
  for (const candidate of new Set([previous, selectedDocumentId])) {
    if (!candidate) continue;
    const card = $('documentGrid').querySelector(`.document-card[data-document-id="${CSS.escape(candidate)}"]`);
    if (card) updateDocumentSelection(card);
  }
}
function catalogParams(offset = 0, limit = catalogPageSize === 'endless' ? 50 : Number(catalogPageSize)) {
  const params = new URLSearchParams({
    q: $('librarySearch').value.trim(), offset: String(offset), limit: String(limit),
    scope: $('filterScope').value,
    type: $('filterType').value, author: $('filterAuthor').value.trim(),
    favorite: $('filterFavorite').value, reading_state: $('filterReading').value,
    tag_mode: $('filterTagMode').value, sort: $('sortField').value,
    direction: $('sortDirection').value
  });
  document.querySelectorAll('#filterTags input:checked').forEach(input => params.append('tag', input.value));
  return params;
}
function hasActiveCatalogFilters() {
  return Boolean($('filterScope').value !== 'all' || $('filterType').value || $('filterAuthor').value.trim() ||
    $('filterFavorite').value || $('filterReading').value || $('filterTagMode').value !== 'ALL' ||
    document.querySelector('#filterTags input:checked'));
}
function catalogFiltersLabel() {
  const labels = [];
  const q = $('librarySearch').value.trim(); if (q) labels.push(`Search: ${q}`);
  if ($('filterScope').value !== 'all') labels.push($('filterScope').selectedOptions[0].textContent);
  if ($('filterType').value) labels.push(`Type: ${$('filterType').value.toUpperCase()}`);
  if ($('filterAuthor').value.trim()) labels.push(`Author: ${$('filterAuthor').value.trim()}`);
  if ($('filterFavorite').value) labels.push(`Favorite: ${$('filterFavorite').value === 'true' ? 'yes' : 'no'}`);
  if ($('filterReading').value) labels.push(`Reading: ${$('filterReading').selectedOptions[0].textContent}`);
  const tags = [...document.querySelectorAll('#filterTags input:checked')].map(input => input.value);
  if (tags.length) labels.push(`Tags (${ $('filterTagMode').value }): ${tags.join(', ')}`);
  else if ($('filterTagMode').value !== 'ALL') labels.push('Tag matching: Any selected');
  $('activeFilters').textContent = labels.length ? labels.join(' · ') : 'No active filters';
  const active = hasActiveCatalogFilters();
  document.querySelector('.library-search').classList.toggle('has-active-filters', active);
  $('clearFilters').disabled = !active;
}
function renderTagFilters(names) {
  availableTags = names;
  const selected = new Set([...document.querySelectorAll('#filterTags input:checked')].map(input => input.value.toLocaleLowerCase()));
  const target = $('filterTags'); target.replaceChildren();
  for (const name of names) {
    const label = element('label', 'filter-tag'); const input = document.createElement('input');
    input.type = 'checkbox'; input.value = name; input.checked = selected.has(name.toLocaleLowerCase());
    input.addEventListener('change', () => loadCatalog()); label.append(input, document.createTextNode(name)); target.append(label);
  }
  if (!names.length) target.append(element('span', '', 'No tags yet'));
}
function tagButton(name, onClick) { const button = element('button', 'tag-chip', name); button.type = 'button'; button.addEventListener('click', onClick); return button; }
async function documentMutation(id, suffix, options, onSuccess) {
  const confirmed = catalogItems.get(id);
  function restoreCard(item) {
    const card = document.querySelector(`.document-card[data-document-id="${CSS.escape(id)}"]`);
    if (!card || !item) return;
    const focusedClass = card.contains(document.activeElement) ? document.activeElement.classList[0] : null;
    card.replaceWith(renderDocument(item));
    const next = document.querySelector(`.document-card[data-document-id="${CSS.escape(id)}"]`);
    if (focusedClass) next.querySelector(`.${CSS.escape(focusedClass)}`)?.focus({preventScroll: true});
  }
  pendingCatalogMutation++;
  let failure = null;
  try {
    const data = await api(`/api/documents/${encodeURIComponent(id)}/${suffix}`, options);
    catalogItems.set(id, data.document);
    if (data.available_tags) renderTagFilters(data.available_tags);
    restoreCard(data.document);
    window.tomeshedReader?.updateDocument(data.document);
    if (onSuccess) onSuccess(data.document);
  } catch (error) { restoreCard(confirmed); failure = `Change was not saved: ${error.message}`; window.tomeshedReader?.panelError(id, failure); }
  finally {
    pendingCatalogMutation--;
    if (!pendingCatalogMutation) { deferredCatalogRefresh = false; await loadCatalog(false, true); }
    if (failure && !window.tomeshedReader?.isOpenFor(id)) showLibraryError(failure);
  }
}
function renderDocument(document) {
  const card = element('article', 'document-card');
  card.dataset.documentId = document.id;
  const preview = element('div', 'document-preview');
  const open = element('button', 'document-open');
  open.type = 'button'; open.setAttribute('aria-label', `Select ${document.title}`);
  open.title = 'Double-click or press Enter to open';
  const openReader = () => {
    if (selectedDocumentId) selectDocument(selectedDocumentId);
    window.tomeshedPreview.close(); window.tomeshedReader.open(document, open);
  };
  let suppressTouchClick = false;
  open.addEventListener('click', event => {
    if (suppressTouchClick) { event.preventDefault(); suppressTouchClick = false; return; }
    if (!window.document.body.classList.contains('reader-open')) selectDocument(document.id);
  });
  open.addEventListener('dblclick', event => { event.preventDefault(); openReader(); });
  open.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); openReader(); } });
  const fallback = element('span', 'document-fallback', document.source_type.toUpperCase());
  open.append(fallback);
  if (document.thumbnail_available) {
    const img = element('img', 'document-art'); img.alt = ''; img.loading = 'lazy';
    img.src = `/api/documents/${encodeURIComponent(document.id)}/thumbnail`;
    img.addEventListener('error', () => img.remove()); open.append(img);
  }
  preview.append(open);
  if (document.state === 'ready_with_warning') {
    const warning = element('span', 'document-warning-badge', '!');
    warning.setAttribute('role', 'img');
    warning.setAttribute('aria-label', 'Indexing warning; details in reader document panel');
    warning.title = 'Indexing warning';
    preview.append(warning);
  }
  const selectedOpen = element('button', 'document-selected-open', 'Open');
  selectedOpen.type = 'button'; selectedOpen.hidden = true;
  selectedOpen.setAttribute('aria-label', `Open ${document.title}`);
  selectedOpen.addEventListener('click', openReader);
  preview.append(selectedOpen); card.append(preview);
  catalogItems.set(document.id, document);
  updateDocumentSelection(card);
  const star = element('button', 'document-star', document.favorite ? '★' : '☆');
  star.type = 'button'; star.setAttribute('aria-label', document.favorite ? 'Remove from favorites' : 'Add to favorites');
  star.setAttribute('aria-pressed', String(Boolean(document.favorite)));
  star.addEventListener('click', () => documentMutation(document.id, 'favorite', {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({favorite: !document.favorite})}));
  card.append(star);
  if (document.state === 'ready' || document.state === 'ready_with_warning') {
    open.setAttribute('aria-controls', 'previewBubble'); open.setAttribute('aria-expanded', 'false');
    open.addEventListener('focus', () => window.tomeshedPreview.scheduleFocus(document.id, card, preview, open));
    open.addEventListener('blur', () => window.tomeshedPreview.cancelFocus());
    preview.addEventListener('pointermove', event => { if (event.pointerType === 'mouse' || event.pointerType === 'pen') window.tomeshedPreview.scheduleHover(document.id, card, preview, open, event); });
    preview.addEventListener('pointerleave', () => window.tomeshedPreview.cancelHover());
    let holdTimer = null;
    let holdStart = null;
    const cancelHold = () => { clearTimeout(holdTimer); holdTimer = null; holdStart = null; };
    open.addEventListener('pointerdown', event => {
      if (event.pointerType !== 'touch') return;
      cancelHold();
      suppressTouchClick = false;
      holdStart = {x: event.clientX, y: event.clientY};
      holdTimer = setTimeout(() => {
        holdTimer = null;
        if (!card.isConnected || window.document.body.classList.contains('reader-open')) return;
        suppressTouchClick = true;
        window.tomeshedPreview.open(document.id, card, preview, open, true);
      }, 800);
    });
    open.addEventListener('pointermove', event => {
      if (event.pointerType === 'touch' && holdStart &&
          Math.hypot(event.clientX - holdStart.x, event.clientY - holdStart.y) > 12) cancelHold();
    });
    open.addEventListener('pointerup', () => { cancelHold(); setTimeout(() => { suppressTouchClick = false; }, 500); });
    open.addEventListener('pointercancel', cancelHold);
    open.addEventListener('contextmenu', event => {
      if (holdStart || suppressTouchClick) event.preventDefault();
    });
  }
  const copy = element('div', 'document-copy');
  copy.append(element('h3', '', document.title));
  card.append(copy);
  return card;
}
function renderDocumentInfo(document) {
  const content = element('div', 'document-info');
  content.append(element('h3', '', document.title), element('p', 'reader-document-author', document.author));
  const tags = element('div', 'document-tags');
  document.tags.forEach(tag => tags.append(element('span', 'tag-chip', tag)));
  content.append(tags);
  const addShelf = element('button', 'document-bookshelf-action', 'Add to bookshelf');
  addShelf.type = 'button'; addShelf.addEventListener('click', () => window.tomeshedBookshelves?.choose(document));
  content.append(addShelf);
  for (const [name, value] of [['Original filename', document.original_filename], ['Stored filename', document.stored_filename], ...(document.source_url ? [['Source URL', document.source_url]] : []), ['Source type', document.source_type.toUpperCase()], ['Size', `${document.byte_size} bytes`], ['Page count', `${document.page_count ?? 'Unknown'} (${document.count_kind})`], ['Imported', new Date(document.created_at * 1000).toLocaleString()], ['Import state', document.state], ['Reading state', document.reading_state.replace('_', ' ')], ['Last read', document.last_read_at ? new Date(document.last_read_at * 1000).toLocaleString() : 'Never']]) {
    const line = element('p'); line.append(element('strong', '', `${name}: `));
    if (name === 'Reading state') line.dataset.readerField = 'reading-state';
    if (name === 'Last read') line.dataset.readerField = 'last-read';
    line.append(element('span', '', value)); content.append(line);
  }
  const edit = element('form', 'document-metadata-edit');
  const titleLabel = element('label', '', 'Title'); const titleInput = window.document.createElement('input'); titleInput.name = 'title'; titleInput.value = document.title; titleInput.maxLength = 300; titleLabel.append(titleInput);
  const authorLabel = element('label', '', 'Author'); const authorInput = window.document.createElement('input'); authorInput.name = 'author'; authorInput.value = document.author; authorInput.maxLength = 300; authorLabel.append(authorInput);
  const save = element('button', 'secondary', 'Save metadata'); save.type = 'submit'; edit.append(titleLabel, authorLabel, save);
  edit.addEventListener('submit', event => { event.preventDefault(); documentMutation(document.id, 'metadata', {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({title: titleInput.value, author: authorInput.value})}); }); content.append(edit);
  const tagEditor = element('form', 'document-tag-editor'); const tagInput = window.document.createElement('input'); tagInput.placeholder = 'Add tag'; tagInput.setAttribute('aria-label', 'Add tag'); tagInput.maxLength = 64;
  const tagSave = element('button', 'secondary', 'Add tag'); tagSave.type = 'submit'; tagEditor.append(tagInput, tagSave);
  tagEditor.addEventListener('submit', event => { event.preventDefault(); const value = tagInput.value; documentMutation(document.id, 'tags', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tag: value})}); }); content.append(tagEditor);
  const attached = element('div', 'document-tag-editor');
  document.tags.forEach(tag => attached.append(tagButton(`${tag} ×`, () => documentMutation(document.id, 'tags', {method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tag})})))); content.append(attached);
  const suggestions = element('div', 'document-tag-suggestions');
  availableTags.filter(tag => !document.tags.some(attached => attached.toLocaleLowerCase() === tag.toLocaleLowerCase())).forEach(tag => suggestions.append(tagButton(tag, () => documentMutation(document.id, 'tags', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tag})}))));
  content.append(suggestions);
  if (document.error) content.append(element('p', 'index-warning', document.error));
  if (document.state === 'ready_with_warning') {
    const retry = element('button', 'secondary', 'Retry indexing'); retry.type = 'button';
    retry.addEventListener('click', async () => { try { await api(`/api/documents/${encodeURIComponent(document.id)}/retry`, {method: 'POST'}); const updated = await api(`/api/documents/${encodeURIComponent(document.id)}`); window.tomeshedReader.updateDocument(updated); await refreshLibrary(); } catch (error) { window.tomeshedReader.panelError(document.id, `Retry indexing failed: ${error.message}`); } });
    content.append(retry);
  }
  if (document.source_available) {
    const original = element('a', 'document-export', `Download original (${document.source_type.toUpperCase()})`);
    original.href = `/api/documents/${encodeURIComponent(document.id)}/export/original`;
    content.append(original);
  }
  if (document.structured_available) {
    const structured = element('a', 'document-export', 'Download Docling JSON');
    structured.href = `/api/documents/${encodeURIComponent(document.id)}/export/docling`;
    content.append(structured);
  }
  const renameForm = element('form', 'source-rename-form');
  const renameLabel = element('label', '', 'Stored filename');
  const renameInput = element('input'); renameInput.value = document.stored_filename; renameInput.maxLength = 255;
  renameLabel.append(renameInput);
  const renameButton = element('button', '', 'Rename file'); renameButton.type = 'submit';
  renameForm.append(renameLabel, renameButton);
  renameForm.addEventListener('submit', async event => { event.preventDefault(); await documentMutation(document.id, 'rename-file', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({filename: renameInput.value})}); });
  content.append(renameForm);
  if (document.can_manage_visibility) {
    const visibilityLabel = element('label', 'document-visibility', 'Visibility');
    const visibilityInput = window.document.createElement('select');
    for (const value of ['public', 'private']) { const option = window.document.createElement('option'); option.value = value; option.textContent = value; visibilityInput.append(option); }
    visibilityInput.value = document.visibility;
    visibilityInput.addEventListener('change', () => documentMutation(document.id, 'visibility', {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({visibility:visibilityInput.value})}));
    visibilityLabel.append(visibilityInput); content.append(visibilityLabel);
  }
  const removeButton = element('button', 'danger', 'Remove document'); removeButton.type = 'button';
  removeButton.addEventListener('click', async () => {
    if (!confirm(`Remove ${document.title}?`)) return;
    try { await api(`/api/documents/${encodeURIComponent(document.id)}`, {method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({confirm: document.title})}); window.tomeshedReader.close(); await refreshLibrary(); showLibraryNotice(`${document.title} was removed.`); }
    catch (error) { window.tomeshedReader.panelError(document.id, `Could not remove ${document.title}: ${error.message}`); }
  }); content.append(removeButton);
  return content;
}
function showLibraryError(message) { $('libraryError').textContent = message; $('libraryError').hidden = false; }
function showLibraryNotice(message) { $('libraryNotice').textContent = message; $('libraryNotice').hidden = false; }
function catalogKey(item) { return `${item.kind}:${item.id}`; }
function cardKey(card) { return card.dataset.bookshelfId ? `bookshelf:${card.dataset.bookshelfId}` : `document:${card.dataset.documentId}`; }
function renderCatalogItem(item) {
  if (item.kind === 'bookshelf') return window.tomeshedBookshelves.card(item);
  catalogItems.set(item.id, item);
  return renderDocument(item);
}
function updateCatalogNavigation() {
  const endless = catalogPageSize === 'endless';
  const pages = Math.max(1, Math.ceil(catalogTotal / catalogEffectivePageSize));
  $('catalogPager').hidden = endless || catalogTotal === 0;
  $('pagerInfo').textContent = `Page ${catalogPage + 1} of ${pages} · ${catalogTotal} ${catalogTotal === 1 ? 'result' : 'results'}`;
  $('pagerFirst').disabled = $('pagerPrev').disabled = catalogPage === 0;
  $('pagerNext').disabled = $('pagerLast').disabled = catalogPage >= pages - 1;
  $('catalogEndlessStatus').hidden = !endless || catalogTotal === 0;
  $('catalogSentinel').hidden = !endless || catalogLoaded >= catalogTotal;
  if (endless && catalogTotal) $('catalogEndlessStatus').textContent =
    catalogLoading ? 'Loading more results…' : catalogLoaded >= catalogTotal ? `All ${catalogTotal} results loaded.` : `${catalogLoaded} of ${catalogTotal} results loaded.`;
}
function loadVisibleEndless() {
  if (library.hidden || catalogPageSize !== 'endless' || catalogLoading || catalogLoaded >= catalogTotal) return;
  const bounds = $('catalogSentinel').getBoundingClientRect();
  if (bounds.top <= innerHeight + 400 && bounds.bottom >= -400) loadCatalog(true);
}
async function loadCatalog(append = false, preserve = false, requestedPage = null) {
  if (pendingCatalogMutation && preserve) { deferredCatalogRefresh = true; return; }
  if (append && (catalogPageSize !== 'endless' || catalogLoading || catalogLoaded >= catalogTotal)) return;
  catalogFiltersLabel();
  const generation = ++catalogGeneration;
  const signature = catalogParams(0).toString();
  const sameQuery = signature === catalogSignature;
  if (!preserve || !sameQuery) catalogPage = 0;
  if (requestedPage !== null) catalogPage = requestedPage;
  const endless = catalogPageSize === 'endless';
  const limit = endless ? 50 : Number(catalogPageSize);
  const offset = endless ? (append && sameQuery ? catalogLoaded : 0) : catalogPage * catalogEffectivePageSize;
  catalogLoading = true;
  if (endless && catalogTotal) { $('catalogEndlessStatus').hidden = false; $('catalogEndlessStatus').textContent = 'Loading more results…'; }
  try {
    let data = await api(`/api/documents?${catalogParams(offset, limit)}`);
    if (generation !== catalogGeneration) return;
    if (!endless && offset >= data.total && data.total > 0) {
      catalogPage = Math.ceil(data.total / data.limit) - 1;
      data = await api(`/api/documents?${catalogParams(catalogPage * data.limit, limit)}`);
      if (generation !== catalogGeneration) return;
    }
    let items = [...data.items];
    if (endless && preserve && sameQuery && !append) {
      const target = Math.min(data.total, Math.max(limit, catalogLoaded));
      const oldIds = [...$('documentGrid').children].map(cardKey);
      while (items.length < data.total && (items.length < target || oldIds.some(id => !items.some(item => catalogKey(item) === id)))) {
        const more = await api(`/api/documents?${catalogParams(items.length, limit)}`);
        if (generation !== catalogGeneration) return;
        if (!more.items.length) break;
        items.push(...more.items);
      }
    }
    catalogSignature = signature;
    catalogTotal = data.total;
    if (!endless) catalogEffectivePageSize = data.limit;
    if (append && sameQuery) {
      const seen = new Set([...$('documentGrid').children].map(cardKey));
      items.filter(item => !seen.has(catalogKey(item))).forEach(item => $('documentGrid').append(renderCatalogItem(item)));
      catalogLoaded = offset + data.items.length;
    } else {
      if (preserve && sameQuery) {
        const oldIds = [...$('documentGrid').children].map(cardKey);
        const byId = new Map(items.map(item => [catalogKey(item), item]));
        items = [...oldIds.filter(id => byId.has(id)).map(id => byId.get(id)),
          ...items.filter(item => !oldIds.includes(catalogKey(item)))];
      }
      const focusedId = preserve ? document.activeElement?.closest('.document-card')?.dataset.documentId : null;
      const focusedClass = document.activeElement?.className;
      window.tomeshedPreview.close(); catalogItems.clear();
      $('documentGrid').replaceChildren(...items.map(renderCatalogItem));
      if (selectedDocumentId && !$('documentGrid').querySelector(`.document-card[data-document-id="${CSS.escape(selectedDocumentId)}"]`)) selectedDocumentId = null;
      if (focusedId && focusedClass) document.querySelector(`.document-card[data-document-id="${CSS.escape(focusedId)}"] .${String(focusedClass).split(' ')[0]}`)?.focus({preventScroll: true});
      catalogLoaded = endless ? items.length : offset + items.length;
    }
    renderTagFilters(data.available_tags || []); catalogFiltersLabel();
    $('libraryCount').textContent = `${data.total} ${data.total === 1 ? 'result' : 'results'}`;
    $('libraryEmpty').hidden = data.total !== 0;
    const filtered = Boolean($('librarySearch').value.trim() || $('filterScope').value !== 'all' || $('filterType').value ||
      $('filterAuthor').value.trim() || $('filterFavorite').value || $('filterReading').value ||
      document.querySelector('#filterTags input:checked'));
    $('libraryEmptyTitle').textContent = filtered ? ($('filterScope').value === 'bookshelves' ? 'No matching bookshelves' : 'No matching documents') : 'No books or PDFs yet';
    $('libraryEmptyText').textContent = hasActiveCatalogFilters() ? 'Clear filters or try another search.' :
      filtered ? 'Try another search.' : 'Add a PDF, EPUB, or DoclingDocument JSON file to start your library.';
    $('libraryError').hidden = true;
  } catch (error) { if (generation === catalogGeneration) showLibraryError(`Could not load library: ${error.message}`); }
  finally { if (generation === catalogGeneration) { catalogLoading = false; updateCatalogNavigation(); requestAnimationFrame(loadVisibleEndless); } }
}
async function loadImportJobs() {
  try {
    const data = await api('/api/imports');
    const jobs = data.jobs.filter(job => ['pending', 'processing', 'failed'].includes(job.state));
    $('activeImportCount').textContent = data.jobs.filter(job => ['pending', 'processing'].includes(job.state)).length || '';
    const list = $('importJobList'); list.replaceChildren();
    for (const job of jobs) {
      const row = element('article', 'import-job');
      row.append(element('strong', '', job.original_filename), element('span', '', job.state));
      if (job.bytes_received) row.append(element('span', 'import-bytes', `${job.bytes_received}${job.expected_bytes == null ? '' : ` / ${job.expected_bytes}`} bytes received`));
      if (job.error) row.append(element('p', 'index-warning', job.error));
      if (job.origin === 'browser' && ['pending', 'processing'].includes(job.state)) {
        const cancel = element('button', '', 'Cancel'); cancel.type = 'button';
        cancel.addEventListener('click', async () => { try { await api(`/api/imports/${encodeURIComponent(job.id)}/cancel`, {method: 'POST'}); activeTransfers.get(job.id)?.abort(); await refreshLibrary(); } catch (error) { showImportError(`${job.original_filename}: ${error.message}`); } });
        row.append(cancel);
      }
      if (job.state === 'failed' && ['browser', 'url'].includes(job.origin)) {
        const retry = element('button', '', 'Retry'); retry.type = 'button';
        retry.addEventListener('click', async () => { try { const result = await api(`/api/imports/${encodeURIComponent(job.id)}/retry`, {method: 'POST'}); if (result.reselect) { retrySelection = job.original_filename; $('uploadFile').click(); } else await loadImportJobs(); } catch (error) { showImportError(`${job.original_filename}: ${error.message}`); } });
        row.append(retry);
      }
      list.append(row);
    }
    if (!jobs.length) list.append(element('p', '', 'No active or failed imports.'));
  } catch (error) { $('importError').textContent = `Could not load imports: ${error.message}`; $('importError').hidden = false; }
}
async function refreshLibrary(preserve = false) { await Promise.all([loadCatalog(false, preserve), loadImportJobs()]); }
$('librarySearch').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => loadCatalog(), 140); });
function closeCatalogFilters(returnFocus = false) {
  const panel = $('catalogFilters');
  if (panel.hidden) return;
  panel.hidden = true;
  $('filtersToggle').setAttribute('aria-expanded', 'false');
  if (returnFocus) $('filtersToggle').focus();
}
function closeCatalogSort(returnFocus = false) {
  const panel = $('catalogSort');
  if (panel.hidden) return;
  panel.hidden = true;
  $('sortToggle').setAttribute('aria-expanded', 'false');
  if (returnFocus) $('sortToggle').focus();
}
function updateSortLabel() {
  const favorite = $('sortField').value === 'favorite';
  $('sortDirection').options[0].textContent = favorite ? 'Favorites last' : 'Ascending';
  $('sortDirection').options[1].textContent = favorite ? 'Favorites first' : 'Descending';
  $('sortToggle').setAttribute('aria-label', `Sort: ${$('sortField').selectedOptions[0].textContent}, ${$('sortDirection').selectedOptions[0].textContent}`);
}
$('sortToggle').addEventListener('click', () => {
  const panel = $('catalogSort');
  if (!panel.hidden) { closeCatalogSort(); return; }
  closeCatalogFilters();
  panel.hidden = false;
  $('sortToggle').setAttribute('aria-expanded', 'true');
  $('sortField').focus();
});
$('filtersToggle').addEventListener('click', () => {
  const panel = $('catalogFilters');
  if (!panel.hidden) { closeCatalogFilters(); return; }
  closeCatalogSort();
  panel.hidden = false;
  $('filtersToggle').setAttribute('aria-expanded', 'true');
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !$('catalogSort').hidden) {
    event.preventDefault();
    closeCatalogSort(true);
    return;
  }
  if (event.key === 'Escape' && !$('catalogFilters').hidden) {
    event.preventDefault();
    closeCatalogFilters(true);
  }
});
document.addEventListener('click', event => {
  if (!$('catalogSort').hidden && !$('catalogSort').contains(event.target) && !$('sortToggle').contains(event.target)) {
    closeCatalogSort(!event.target.closest('button, input, select, textarea, a, [tabindex]'));
  }
  if (!$('catalogFilters').hidden && !$('catalogFilters').contains(event.target) && !$('filtersToggle').contains(event.target)) {
    closeCatalogFilters(!event.target.closest('button, input, select, textarea, a, [tabindex]'));
  }
});
for (const id of ['filterScope', 'filterType', 'filterFavorite', 'filterReading', 'filterTagMode']) $(id).addEventListener('change', () => loadCatalog());
for (const id of ['sortField', 'sortDirection']) $(id).addEventListener('change', () => { updateSortLabel(); loadCatalog(); });
updateSortLabel();
$('filterAuthor').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => loadCatalog(), 140); });
$('clearFilters').addEventListener('click', () => { clearTimeout(searchTimer); $('filterScope').value = 'all'; $('filterType').value = ''; $('filterAuthor').value = ''; $('filterFavorite').value = ''; $('filterReading').value = ''; $('filterTagMode').value = 'ALL'; document.querySelectorAll('#filterTags input').forEach(input => { input.checked = false; }); closeCatalogFilters(true); loadCatalog(); });
for (const [id, target] of [['pagerFirst', () => 0], ['pagerPrev', () => catalogPage - 1],
  ['pagerNext', () => catalogPage + 1], ['pagerLast', () => Math.ceil(catalogTotal / catalogEffectivePageSize) - 1]]) {
  $(id).addEventListener('click', () => loadCatalog(false, true, target()));
}
const catalogObserver = new IntersectionObserver(entries => {
  if (entries[0].isIntersecting && !library.hidden && !catalogLoading && catalogPageSize === 'endless' && catalogLoaded < catalogTotal) loadCatalog(true);
}, {rootMargin: '400px'});
catalogObserver.observe($('catalogSentinel'));
$('importsButton').addEventListener('click', () => { const drawer = $('importsDrawer'); drawer.hidden = !drawer.hidden; $('importsButton').setAttribute('aria-expanded', String(!drawer.hidden)); if (!drawer.hidden) $('closeImports').focus(); });
$('closeImports').addEventListener('click', () => { $('importsDrawer').hidden = true; $('importsButton').setAttribute('aria-expanded', 'false'); $('importsButton').focus(); });
const activeTransfers = new Map();
let retrySelection = null;
function showImportError(message) { $('importsDrawer').hidden = false; $('importError').textContent = message; $('importError').hidden = false; }
function showImports() { $('importsDrawer').hidden = false; $('importsButton').setAttribute('aria-expanded', 'true'); }
function transferFile(id, file) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest(); activeTransfers.set(id, xhr);
    xhr.open('PUT', `/api/imports/${encodeURIComponent(id)}/file`);
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.upload.onprogress = () => loadImportJobs();
    xhr.onload = () => { let data = {}; try { data = JSON.parse(xhr.responseText); } catch (_) {} xhr.status >= 200 && xhr.status < 300 ? resolve(data) : reject(new Error(data.error || `Transfer failed (${xhr.status})`)); };
    xhr.onerror = () => reject(new Error('Transfer connection failed'));
    xhr.onabort = () => reject(new Error('Cancelled by user'));
    xhr.onloadend = () => { activeTransfers.delete(id); refreshLibrary(true); };
    xhr.send(file);
  });
}
async function importFiles(files, openDrawer = false) {
  if (!files.length) return;
  if (openDrawer) showImports(); $('importError').hidden = true;
  await Promise.allSettled(files.map(async file => {
    try {
      const job = await api('/api/imports/register', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename:file.name,size:file.size})});
      await loadImportJobs();
      await transferFile(job.id, file);
    } catch (error) { showImportError(`${file.name}: ${error.message}`); }
  }));
  await refreshLibrary(true);
}
$('chooseFile').addEventListener('click', () => $('uploadFile').click());
$('uploadFile').addEventListener('change', event => {
  const files = [...event.target.files]; event.target.value = '';
  if (retrySelection && files.length !== 1) { showImportError('Select one local file to retry.'); retrySelection = null; return; }
  retrySelection = null; importFiles(files);
});
$('urlImportForm').addEventListener('submit', async event => {
  event.preventDefault();
  try { await api('/api/imports/url', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:$('importUrl').value})}); $('importUrl').value=''; await loadImportJobs(); }
  catch (error) { showImportError(`URL import: ${error.message}`); }
});
const dropTarget = $('fileDropTarget'); let dragDepth = 0;
function fileDrag(event) { return [...(event.dataTransfer?.types || [])].includes('Files'); }
document.addEventListener('dragenter', event => { if (!fileDrag(event)) return; event.preventDefault(); dragDepth++; dropTarget.hidden = false; });
document.addEventListener('dragover', event => { if (!fileDrag(event)) return; event.preventDefault(); event.dataTransfer.dropEffect='copy'; });
document.addEventListener('dragleave', event => { if (event.relatedTarget == null) dragDepth = 0; else dragDepth = Math.max(0, dragDepth-1); if (!dragDepth) dropTarget.hidden = true; });
document.addEventListener('drop', event => { if (!fileDrag(event)) return; event.preventDefault(); dragDepth=0; dropTarget.hidden = true; importFiles([...(event.dataTransfer.files || [])], true); });
if ($('bulkClearButton')) $('bulkClearButton').addEventListener('click', async () => {
  const button = $('bulkClearButton');
  button.disabled = true;
  try {
    const preview = await api('/api/library/clear/preview');
    if (!confirm(`Remove ${preview.document_count} documents and ${preview.file_count} managed files?`)) return;
    await api('/api/library/clear', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:preview.token})});
    await refreshLibrary();
    showSuccess(`Library cleared: ${preview.document_count} documents removed.`);
  } catch (error) { showError(`Library clear failed: ${error.message}`); }
  finally { button.disabled = false; }
});
if (window.EventSource) {
  const eventStream = new EventSource('/api/events');
  eventStream.addEventListener('ready', () => refreshLibrary(true));
  eventStream.addEventListener('change', () => { refreshLibrary(true); window.tomeshedBookshelves?.refresh(); });
}
refreshLibrary();
window.tomeshedCatalog = {readerState(id, item) { catalogItems.set(id, item); loadCatalog(false, true); }, refresh: refreshLibrary, renderDocumentInfo};
