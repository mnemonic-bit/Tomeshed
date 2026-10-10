const $ = id => document.getElementById(id);
const menuButton = $('accountMenuButton');
const menu = $('accountMenu');
const settings = $('settingsPage');
const library = $('libraryPage');
const themeControl = $('prefTheme');
let healthInFlight = false;

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
  try { const data = await api('/api/preferences'); themeControl.value = data.theme; applyTheme(data.theme); }
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
function openSettings() {
  closeMenu(); library.hidden = true; settings.hidden = false; document.body.classList.add('settings-open');
  $('settingsSearchInput').value = ''; filterSettings(); loadPreferences();
  if ($('userList')) loadUsers();
  $('settingsSearchInput').focus();
}
function closeSettings() { settings.hidden = true; library.hidden = false; document.body.classList.remove('settings-open'); menuButton.focus(); }
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

let catalogOffset = 0;
let catalogSignature = '';
let catalogGeneration = 0;
let searchTimer;
let availableTags = [];
let pendingCatalogMutation = 0;
let deferredCatalogRefresh = false;
const catalogItems = new Map();
function catalogParams(offset = 0) {
  const params = new URLSearchParams({
    q: $('librarySearch').value.trim(), offset: String(offset),
    type: $('filterType').value, author: $('filterAuthor').value.trim(),
    favorite: $('filterFavorite').value, reading_state: $('filterReading').value,
    tag_mode: $('filterTagMode').value, sort: $('catalogSort').value
  });
  document.querySelectorAll('#filterTags input:checked').forEach(input => params.append('tag', input.value));
  return params;
}
function catalogFiltersLabel() {
  const labels = [];
  const q = $('librarySearch').value.trim(); if (q) labels.push(`Search: ${q}`);
  if ($('filterType').value) labels.push(`Type: ${$('filterType').value.toUpperCase()}`);
  if ($('filterAuthor').value.trim()) labels.push(`Author: ${$('filterAuthor').value.trim()}`);
  if ($('filterFavorite').value) labels.push(`Favorite: ${$('filterFavorite').value === 'true' ? 'yes' : 'no'}`);
  if ($('filterReading').value) labels.push(`Reading: ${$('filterReading').selectedOptions[0].textContent}`);
  const tags = [...document.querySelectorAll('#filterTags input:checked')].map(input => input.value);
  if (tags.length) labels.push(`Tags (${ $('filterTagMode').value }): ${tags.join(', ')}`);
  $('activeFilters').textContent = labels.length ? labels.join(' · ') : 'No active filters';
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
    const openInfo = !card.querySelector('.document-info').hidden;
    const focusedClass = card.contains(document.activeElement) ? document.activeElement.classList[0] : null;
    card.replaceWith(renderDocument(item));
    const next = document.querySelector(`.document-card[data-document-id="${CSS.escape(id)}"]`);
    if (openInfo) {
      next.querySelector('.document-info').hidden = false;
      next.querySelector('.document-info-button').setAttribute('aria-expanded', 'true');
    }
    if (focusedClass) next.querySelector(`.${CSS.escape(focusedClass)}`)?.focus({preventScroll: true});
  }
  pendingCatalogMutation++;
  let failure = null;
  try {
    const data = await api(`/api/documents/${encodeURIComponent(id)}/${suffix}`, options);
    catalogItems.set(id, data.document);
    if (data.available_tags) renderTagFilters(data.available_tags);
    restoreCard(data.document);
    if (onSuccess) onSuccess(data.document);
  } catch (error) { restoreCard(confirmed); failure = `Change was not saved: ${error.message}`; }
  finally {
    pendingCatalogMutation--;
    if (!pendingCatalogMutation) { deferredCatalogRefresh = false; await loadCatalog(false, true); }
    if (failure) showLibraryError(failure);
  }
}
function pageBadge(document) {
  const type = document.source_type === 'docling' ? 'DOCLING' : document.source_type.toUpperCase();
  if (document.count_kind === 'estimated') return {text: `${type} · ~${document.page_count} pages`, label: `${type}, approximately ${document.page_count} pages, estimated`};
  if (document.count_kind === 'exact') return {text: `${type} · ${document.page_count} pages`, label: `${type}, ${document.page_count} pages`};
  return {text: `${type} · pages unknown`, label: `${type}, page count unknown`};
}
function renderDocument(document) {
  const card = element('article', 'document-card');
  card.dataset.documentId = document.id;
  const preview = element('div', 'document-preview');
  const open = element('button', 'document-open');
  open.type = 'button'; open.setAttribute('aria-label', `Open ${document.title}`);
  open.addEventListener('click', () => { window.tomeshedPreview.close(); window.tomeshedReader.open(document, open); });
  const fallback = element('span', 'document-fallback', document.source_type.toUpperCase());
  open.append(fallback);
  if (document.thumbnail_available) {
    const img = element('img', 'document-art'); img.alt = ''; img.loading = 'lazy';
    img.src = `/api/documents/${encodeURIComponent(document.id)}/thumbnail`;
    img.addEventListener('error', () => img.remove()); open.append(img);
  }
  const badge = pageBadge(document);
  const badgeNode = element('span', 'document-page-badge', badge.text);
  badgeNode.setAttribute('aria-label', badge.label);
  open.append(badgeNode); preview.append(open); card.append(preview);
  if (document.reading_state === 'unread') card.append(element('span', 'document-new-badge', 'new'));
  const star = element('button', 'document-star', document.favorite ? '★' : '☆');
  star.type = 'button'; star.setAttribute('aria-label', document.favorite ? 'Remove from favorites' : 'Add to favorites');
  star.setAttribute('aria-pressed', String(Boolean(document.favorite)));
  star.addEventListener('click', () => documentMutation(document.id, 'favorite', {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({favorite: !document.favorite})}));
  card.append(star);
  const addShelf = element('button', 'document-bookshelf-action', 'Add to bookshelf');
  addShelf.type = 'button'; addShelf.addEventListener('click', () => window.tomeshedBookshelves?.choose(document));
  card.append(addShelf);
  if (document.state === 'ready' || document.state === 'ready_with_warning') {
    const previewAction = element('button', 'document-preview-action', 'Preview');
    previewAction.type = 'button'; previewAction.setAttribute('aria-label', `Preview ${document.title}`);
    previewAction.setAttribute('aria-controls', 'previewBubble'); previewAction.setAttribute('aria-expanded', 'false');
    previewAction.addEventListener('click', () => window.tomeshedPreview.open(document.id, card, preview, previewAction, true));
    preview.addEventListener('pointermove', event => { if (event.pointerType === 'mouse' || event.pointerType === 'pen') window.tomeshedPreview.open(document.id, card, preview, previewAction, false, event); });
    card.append(previewAction);
  }
  const copy = element('div', 'document-copy');
  copy.append(element('h3', '', document.title), element('p', '', document.author));
  const chips = element('div', 'document-tags'); document.tags.forEach(tag => chips.append(element('span', 'tag-chip', tag))); copy.append(chips);
  if (document.state === 'ready_with_warning') copy.append(element('span', 'index-warning', 'Indexing warning'));
  card.append(copy);
  const info = element('button', 'document-info-button', '⋮');
  info.type = 'button'; info.setAttribute('aria-label', `Info for ${document.title}`);
  info.setAttribute('aria-expanded', 'false');
  const panel = element('div', 'document-info'); panel.hidden = true;
  for (const [name, value] of [['Original filename', document.original_filename], ['Stored filename', document.stored_filename], ...(document.source_url ? [['Source URL', document.source_url]] : []), ['Source type', document.source_type.toUpperCase()], ['Size', `${document.byte_size} bytes`], ['Page count', `${document.page_count ?? 'Unknown'} (${document.count_kind})`], ['Imported', new Date(document.created_at * 1000).toLocaleString()], ['Import state', document.state], ['Reading state', document.reading_state.replace('_', ' ')], ['Last read', document.last_read_at ? new Date(document.last_read_at * 1000).toLocaleString() : 'Never']]) {
    const line = element('p'); line.append(element('strong', '', `${name}: `));
    line.append(documentNode(value)); panel.append(line);
  }
  const edit = element('form', 'document-metadata-edit');
  const titleLabel = element('label', '', 'Title'); const titleInput = window.document.createElement('input'); titleInput.name = 'title'; titleInput.value = document.title; titleInput.maxLength = 300; titleLabel.append(titleInput);
  const authorLabel = element('label', '', 'Author'); const authorInput = window.document.createElement('input'); authorInput.name = 'author'; authorInput.value = document.author; authorInput.maxLength = 300; authorLabel.append(authorInput);
  const save = element('button', 'secondary', 'Save metadata'); save.type = 'submit'; edit.append(titleLabel, authorLabel, save);
  edit.addEventListener('submit', event => { event.preventDefault(); documentMutation(document.id, 'metadata', {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({title: titleInput.value, author: authorInput.value})}); }); panel.append(edit);
  const tagEditor = element('form', 'document-tag-editor'); const tagInput = window.document.createElement('input'); tagInput.placeholder = 'Add tag'; tagInput.setAttribute('aria-label', 'Add tag'); tagInput.maxLength = 64;
  const tagSave = element('button', 'secondary', 'Add tag'); tagSave.type = 'submit'; tagEditor.append(tagInput, tagSave);
  tagEditor.addEventListener('submit', event => { event.preventDefault(); const value = tagInput.value; documentMutation(document.id, 'tags', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tag: value})}); }); panel.append(tagEditor);
  const attached = element('div', 'document-tag-editor');
  document.tags.forEach(tag => attached.append(tagButton(`${tag} ×`, () => documentMutation(document.id, 'tags', {method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tag})})))); panel.append(attached);
  const suggestions = element('div', 'document-tag-suggestions');
  availableTags.filter(tag => !document.tags.some(attached => attached.toLocaleLowerCase() === tag.toLocaleLowerCase())).forEach(tag => suggestions.append(tagButton(tag, () => documentMutation(document.id, 'tags', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tag})}))));
  panel.append(suggestions);
  if (document.error) panel.append(element('p', 'index-warning', document.error));
  if (document.state === 'ready_with_warning') {
    const retry = element('button', 'secondary', 'Retry indexing'); retry.type = 'button';
    retry.addEventListener('click', async () => { try { await api(`/api/documents/${encodeURIComponent(document.id)}/retry`, {method: 'POST'}); await refreshLibrary(); await loadImportJobs(); } catch (error) { showLibraryError(error.message); } });
    panel.append(retry);
  }
  if (document.source_available) {
    const original = element('a', 'document-export', `Download original (${document.source_type.toUpperCase()})`);
    original.href = `/api/documents/${encodeURIComponent(document.id)}/export/original`;
    panel.append(original);
  }
  if (document.structured_available) {
    const structured = element('a', 'document-export', 'Download Docling JSON');
    structured.href = `/api/documents/${encodeURIComponent(document.id)}/export/docling`;
    panel.append(structured);
  }
  const renameForm = element('form', 'source-rename-form');
  const renameLabel = element('label', '', 'Stored filename');
  const renameInput = element('input'); renameInput.value = document.stored_filename; renameInput.maxLength = 255;
  renameLabel.append(renameInput);
  const renameButton = element('button', '', 'Rename file'); renameButton.type = 'submit';
  renameForm.append(renameLabel, renameButton);
  renameForm.addEventListener('submit', async event => { event.preventDefault(); await documentMutation(document.id, 'rename-file', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({filename: renameInput.value})}); });
  panel.append(renameForm);
  if (document.can_manage_visibility) {
    const visibilityLabel = element('label', 'document-visibility', 'Visibility');
    const visibilityInput = window.document.createElement('select');
    for (const value of ['public', 'private']) { const option = window.document.createElement('option'); option.value = value; option.textContent = value; visibilityInput.append(option); }
    visibilityInput.value = document.visibility;
    visibilityInput.addEventListener('change', () => documentMutation(document.id, 'visibility', {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({visibility:visibilityInput.value})}));
    visibilityLabel.append(visibilityInput); panel.append(visibilityLabel);
  }
  const removeButton = element('button', 'danger', 'Remove document'); removeButton.type = 'button';
  removeButton.addEventListener('click', async () => {
    if (!confirm(`Remove ${document.title}?`)) return;
    try { await api(`/api/documents/${encodeURIComponent(document.id)}`, {method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({confirm: document.title})}); await refreshLibrary(); }
    catch (error) { showLibraryError(`Could not remove ${document.title}: ${error.message}`); }
  }); panel.append(removeButton);
  info.addEventListener('click', () => { panel.hidden = !panel.hidden; info.setAttribute('aria-expanded', String(!panel.hidden)); });
  panel.addEventListener('keydown', event => { if (event.key === 'Escape') { panel.hidden = true; info.setAttribute('aria-expanded', 'false'); info.focus(); } });
  card.append(info, panel);
  return card;
}
function documentNode(value) { return window.document.createTextNode(String(value)); }
function showLibraryError(message) { $('libraryError').textContent = message; $('libraryError').hidden = false; }
async function loadCatalog(append = false, preserve = false) {
  if (pendingCatalogMutation && preserve) { deferredCatalogRefresh = true; return; }
  const generation = ++catalogGeneration;
  const signature = catalogParams(0).toString();
  const offset = append && signature === catalogSignature ? catalogOffset : 0;
  try {
    let data = await api(`/api/documents?${catalogParams(preserve || append ? 0 : offset)}`);
    if (generation !== catalogGeneration) return;
    catalogSignature = signature;
    if (append && offset > 0) {
      const seen = new Set([...$('documentGrid').children].map(card => card.dataset.documentId));
      const additions = data.documents.filter(item => !seen.has(item.id));
      let nextOffset = data.documents.length;
      while (additions.length < data.limit && nextOffset < data.total) {
        const page = await api(`/api/documents?${catalogParams(nextOffset)}`);
        if (generation !== catalogGeneration) return;
        additions.push(...page.documents.filter(item => !seen.has(item.id)));
        nextOffset += page.documents.length;
        if (!page.documents.length) break;
      }
      additions.slice(0, data.limit).forEach(item => { catalogItems.set(item.id, item); $('documentGrid').append(renderDocument(item)); });
      catalogOffset = $('documentGrid').children.length;
    } else if (preserve && $('documentGrid').children.length) {
      const oldIds = [...$('documentGrid').children].map(card => card.dataset.documentId);
      const all = [...data.documents]; let nextOffset = all.length;
      while (nextOffset < data.total && oldIds.some(id => !all.some(item => item.id === id))) {
        const page = await api(`/api/documents?${catalogParams(nextOffset)}`);
        if (generation !== catalogGeneration) return;
        all.push(...page.documents); nextOffset += page.documents.length;
        if (!page.documents.length) break;
      }
      const byId = new Map(all.map(item => [item.id, item]));
      const ordered = oldIds.filter(id => byId.has(id)).map(id => byId.get(id));
      const newItems = all.filter(item => !oldIds.includes(item.id)).slice(0, Math.max(1, catalogOffset - ordered.length + 1));
      const focusedId = document.activeElement?.closest('.document-card')?.dataset.documentId;
      const focusedClass = document.activeElement?.className;
      const openInfoIds = [...$('documentGrid').querySelectorAll('.document-card')].filter(card => !card.querySelector('.document-info').hidden).map(card => card.dataset.documentId);
      window.tomeshedPreview.close(); $('documentGrid').replaceChildren(...[...ordered, ...newItems].map(item => { catalogItems.set(item.id, item); return renderDocument(item); }));
      openInfoIds.forEach(id => { const card = document.querySelector(`.document-card[data-document-id="${CSS.escape(id)}"]`); if (card) { card.querySelector('.document-info').hidden = false; card.querySelector('.document-info-button').setAttribute('aria-expanded', 'true'); } });
      if (focusedId && focusedClass) document.querySelector(`.document-card[data-document-id="${CSS.escape(focusedId)}"] .${String(focusedClass).split(' ')[0]}`)?.focus();
      catalogOffset = Math.min(data.total, ordered.length + newItems.length);
    } else {
      if (!append || offset === 0) { window.tomeshedPreview.close(); $('documentGrid').replaceChildren(); catalogItems.clear(); }
      data.documents.forEach(item => { catalogItems.set(item.id, item); $('documentGrid').append(renderDocument(item)); });
      catalogOffset = offset + data.documents.length;
    }
    renderTagFilters(data.available_tags || []); catalogFiltersLabel();
    $('libraryCount').textContent = `${data.library_total} ${data.library_total === 1 ? 'document' : 'documents'}`;
    $('loadMoreDocuments').hidden = catalogOffset >= data.total;
    $('libraryEmpty').hidden = data.total !== 0;
    const filtered = signature !== new URLSearchParams({q: '', offset: '0', type: '', author: '', favorite: '', reading_state: '', tag_mode: 'ALL', sort: 'newest'}).toString();
    $('libraryEmptyTitle').textContent = filtered ? 'No matching documents' : 'No books or PDFs yet';
    $('libraryEmptyText').textContent = filtered ? 'Clear filters or try another search.' : 'Add a PDF, EPUB, or DoclingDocument JSON file to start your library.';
    $('libraryError').hidden = true;
  } catch (error) { showLibraryError(`Could not load library: ${error.message}`); }
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
$('filtersToggle').addEventListener('click', () => { const panel = $('catalogFilters'); panel.hidden = !panel.hidden; $('filtersToggle').setAttribute('aria-expanded', String(!panel.hidden)); });
for (const id of ['filterType', 'filterFavorite', 'filterReading', 'filterTagMode', 'catalogSort']) $(id).addEventListener('change', () => loadCatalog());
$('filterAuthor').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => loadCatalog(), 140); });
$('clearFilters').addEventListener('click', () => { $('librarySearch').value = ''; $('filterType').value = ''; $('filterAuthor').value = ''; $('filterFavorite').value = ''; $('filterReading').value = ''; $('filterTagMode').value = 'ALL'; document.querySelectorAll('#filterTags input').forEach(input => { input.checked = false; }); loadCatalog(); });
$('loadMoreDocuments').addEventListener('click', () => loadCatalog(true));
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
  try {
    const preview = await api('/api/library/clear/preview');
    if (!confirm(`Remove ${preview.document_count} documents and ${preview.file_count} managed files?`)) return;
    await api('/api/library/clear', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:preview.token})});
    await refreshLibrary();
  } catch (error) { showLibraryError(`Library clear failed: ${error.message}`); }
});
if (window.EventSource) {
  const eventStream = new EventSource('/api/events');
  eventStream.addEventListener('ready', () => refreshLibrary(true));
  eventStream.addEventListener('change', () => { refreshLibrary(true); window.tomeshedBookshelves?.refresh(); });
}
refreshLibrary();
window.tomeshedCatalog = {readerState(id, item) { catalogItems.set(id, item); loadCatalog(false, true); }, refresh: refreshLibrary};
