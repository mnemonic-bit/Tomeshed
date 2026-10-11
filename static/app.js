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
const selectedDocumentIds = new Set();
const selectedDocumentLabels = new Map();
let selectionBusy = false;
function updateSelectionActions() {
  const count = selectedDocumentIds.size;
  $('selectionCount').textContent = `${count} selected`;
  const picker = $('openSelectedDocument');
  const previous = picker.value;
  const previousCount = picker.options.length - 1;
  picker.replaceChildren();
  const placeholder = element('option', '', count > 1 ? 'Choose a document' : 'Selected document');
  placeholder.value = ''; picker.append(placeholder);
  const nameCounts = new Map();
  for (const id of selectedDocumentIds) {
    const name = selectedDocumentLabels.get(id) || id;
    nameCounts.set(name, (nameCounts.get(name) || 0) + 1);
  }
  for (const id of selectedDocumentIds) {
    const name = selectedDocumentLabels.get(id) || id;
    const option = element('option', '', nameCounts.get(name) > 1 ? `${name} (${id})` : name);
    option.value = id; picker.append(option);
  }
  picker.value = count === 1 ? [...selectedDocumentIds][0] : previousCount > 1 && selectedDocumentIds.has(previous) ? previous : '';
  picker.disabled = selectionBusy || !count;
  $('openSelected').disabled = selectionBusy || !picker.value;
  for (const id of ['clearSelection', 'downloadSelected', 'deleteSelected']) $(id).disabled = selectionBusy || !count;
}
function updateDocumentSelection(card) {
  const item = catalogItems.get(card.dataset.documentId);
  if (!item) return;
  const selected = selectedDocumentIds.has(item.id);
  card.classList.toggle('document-selected', selected);
  card.querySelector('.document-open').setAttribute('aria-pressed', String(selected));
  card.querySelector('.document-selection-badge, .document-new-badge')?.remove();
  if (selected) {
    const badge = element('span', 'document-selection-badge', '✓');
    badge.setAttribute('aria-hidden', 'true');
    card.append(badge);
  } else if (item.reading_state === 'unread') card.append(element('span', 'document-new-badge', 'new'));
}
function selectDocument(id) {
  if (selectedDocumentIds.has(id)) {
    selectedDocumentIds.delete(id);
    selectedDocumentLabels.delete(id);
  } else {
    if (selectedDocumentIds.size >= 1000) { showLibraryError('Select at most 1000 documents at a time.'); return; }
    selectedDocumentIds.add(id);
    selectedDocumentLabels.set(id, catalogItems.get(id)?.title || id);
  }
  const card = $('documentGrid').querySelector(`.document-card[data-document-id="${CSS.escape(id)}"]`);
  if (card) updateDocumentSelection(card);
  updateSelectionActions();
}
function removeSelectedDocuments(ids) {
  for (const id of ids) {
    selectedDocumentIds.delete(id);
    selectedDocumentLabels.delete(id);
    const card = $('documentGrid').querySelector(`.document-card[data-document-id="${CSS.escape(id)}"]`);
    if (card) updateDocumentSelection(card);
  }
  updateSelectionActions();
}
async function syncSelectionAccess() {
  if (!selectedDocumentIds.size) return;
  try {
    const status = await api('/api/documents/bulk/status', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids: [...selectedDocumentIds]})});
    removeSelectedDocuments(status.unavailable_ids);
  } catch (error) { showLibraryError(`Could not check selected documents: ${error.message}`); }
}
function selectionFailureText(failures) {
  return failures.map(item => `${selectedDocumentLabels.get(item.id) || item.id}: ${item.reason.replaceAll('_', ' ')}`).join('; ');
}
async function selectedArchiveManifest(blob) {
  const decoder = new TextDecoder();
  const number = (view, offset) => {
    const value = Number(view.getBigUint64(offset, true));
    if (!Number.isSafeInteger(value)) throw new Error('Selected archive is too large to inspect.');
    return value;
  };
  const tailStart = Math.max(0, blob.size - 65557);
  const tail = new DataView(await blob.slice(tailStart).arrayBuffer());
  let end = -1;
  for (let offset = tail.byteLength - 22; offset >= 0; offset--) {
    if (tail.getUint32(offset, true) === 0x06054b50 && offset + 22 + tail.getUint16(offset + 20, true) === tail.byteLength) {
      end = offset; break;
    }
  }
  if (end < 0) throw new Error('Selected archive has no ZIP directory.');
  let directorySize = tail.getUint32(end + 12, true);
  let directoryOffset = tail.getUint32(end + 16, true);
  if (directorySize === 0xffffffff || directoryOffset === 0xffffffff) {
    if (end < 20 || tail.getUint32(end - 20, true) !== 0x07064b50) throw new Error('Selected archive has no ZIP64 directory.');
    const zip64Offset = number(tail, end - 12);
    const zip64 = new DataView(await blob.slice(zip64Offset, zip64Offset + 56).arrayBuffer());
    if (zip64.byteLength < 56 || zip64.getUint32(0, true) !== 0x06064b50) throw new Error('Selected archive has an invalid ZIP64 directory.');
    directorySize = number(zip64, 40);
    directoryOffset = number(zip64, 48);
  }
  const directory = new DataView(await blob.slice(directoryOffset, directoryOffset + directorySize).arrayBuffer());
  for (let offset = 0; offset + 46 <= directory.byteLength;) {
    if (directory.getUint32(offset, true) !== 0x02014b50) throw new Error('Selected archive has an invalid ZIP entry.');
    const nameLength = directory.getUint16(offset + 28, true);
    const extraLength = directory.getUint16(offset + 30, true);
    const commentLength = directory.getUint16(offset + 32, true);
    const name = decoder.decode(new Uint8Array(directory.buffer, offset + 46, nameLength));
    if (name === 'manifest.json') {
      if (directory.getUint16(offset + 10, true) !== 0) throw new Error('Selected archive manifest is compressed.');
      const size = directory.getUint32(offset + 20, true);
      let localOffset = directory.getUint32(offset + 42, true);
      if (size === 0xffffffff) throw new Error('Selected archive manifest is too large.');
      if (localOffset === 0xffffffff) {
        let extra = offset + 46 + nameLength;
        const extraEnd = extra + extraLength;
        while (extra + 4 <= extraEnd) {
          const field = directory.getUint16(extra, true);
          const length = directory.getUint16(extra + 2, true);
          if (field === 0x0001) {
            let value = extra + 4;
            if (directory.getUint32(offset + 20, true) === 0xffffffff) value += 8;
            if (directory.getUint32(offset + 24, true) === 0xffffffff) value += 8;
            localOffset = number(directory, value);
            break;
          }
          extra += 4 + length;
        }
      }
      if (localOffset === 0xffffffff) throw new Error('Selected archive manifest has no location.');
      const local = new DataView(await blob.slice(localOffset, localOffset + 30).arrayBuffer());
      if (local.byteLength < 30 || local.getUint32(0, true) !== 0x04034b50) throw new Error('Selected archive manifest is invalid.');
      const contentOffset = localOffset + 30 + local.getUint16(26, true) + local.getUint16(28, true);
      return JSON.parse(await blob.slice(contentOffset, contentOffset + size).text());
    }
    offset += 46 + nameLength + extraLength + commentLength;
  }
  throw new Error('Selected archive has no manifest.');
}
function selectionBusyState(busy) { selectionBusy = busy; updateSelectionActions(); }
$('openSelectedDocument').addEventListener('change', updateSelectionActions);
$('openSelected').addEventListener('click', async () => {
  const id = $('openSelectedDocument').value;
  if (!selectedDocumentIds.has(id)) return;
  selectionBusyState(true);
  try {
    const documentItem = await api(`/api/documents/${encodeURIComponent(id)}`);
    window.tomeshedPreview.close(); window.tomeshedReader.open(documentItem, $('openSelected'));
  } catch (error) {
    await syncSelectionAccess();
    showLibraryError(`Could not open selected document: ${error.message}`);
  } finally { selectionBusyState(false); }
});
$('clearSelection').addEventListener('click', () => removeSelectedDocuments([...selectedDocumentIds]));
$('downloadSelected').addEventListener('click', async () => {
  const ids = [...selectedDocumentIds];
  if (!ids.length) return;
  selectionBusyState(true);
  try {
    const response = await fetch('/api/documents/bulk/export/original', {method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids})});
    if (!response.ok) { const error = await response.json(); throw new Error(error.error || `Request failed (${response.status})`); }
    const blob = await response.blob();
    const manifest = await selectedArchiveManifest(blob);
    const failures = manifest.failures;
    const failureCount = failures.length;
    const included = manifest.included.length;
    const url = URL.createObjectURL(blob);
    const link = element('a'); link.href = url; link.download = 'tomeshed-originals.zip';
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
    const failureText = selectionFailureText(failures);
    removeSelectedDocuments(failures.filter(item => item.reason === 'unavailable').map(item => item.id));
    if (failureCount) showLibraryError(`${included} originals included; ${failureCount} unavailable. ${failureText}`);
    else showLibraryNotice(`${included} originals included in tomeshed-originals.zip.`);
  } catch (error) { showLibraryError(`Could not download selected documents: ${error.message}`); }
  finally { selectionBusyState(false); }
});
$('deleteSelected').addEventListener('click', async () => {
  const ids = [...selectedDocumentIds];
  if (!ids.length || !confirm(`Delete ${ids.length} selected ${ids.length === 1 ? 'document' : 'documents'}?`)) return;
  selectionBusyState(true);
  try {
    const result = await api('/api/documents/bulk/delete', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ids, confirm_count: ids.length})});
    const failureText = selectionFailureText(result.failures);
    const remaining = new Set(result.remaining_document_ids);
    removeSelectedDocuments(ids.filter(id => !remaining.has(id)));
    await refreshLibrary();
    if (result.failures.length) showLibraryError(`${result.removed.length} deleted; ${result.failures.length} failed. ${failureText}`);
    else showLibraryNotice(`${result.removed.length} selected documents deleted.`);
  } catch (error) { showLibraryError(`Could not delete selected documents: ${error.message}`); }
  finally { selectionBusyState(false); }
});
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
    $('filterFavorite').value || $('filterReading').value ||
    document.querySelector('#filterTags input:checked'));
}
function updateFilterButtonState() {
  const active = hasActiveCatalogFilters();
  $('filtersToggle').classList.toggle('has-active-filters', active);
  $('filtersToggle').setAttribute('aria-label', active ? 'Filters active' : 'Filters');
  $('clearFilters').disabled = !active && $('filterTagMode').value === 'ALL';
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
    if (onSuccess) onSuccess(data.document);
    restoreCard(data.document);
    window.tomeshedReader?.updateDocument(data.document);
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
  const doubleClickWindowMs = 300;
  let pendingClick = null;
  let activationPointerType = null;
  const cancelPendingSelection = () => {
    if (pendingClick) clearTimeout(pendingClick.timer);
    window.document.removeEventListener('pointerup', finishSecondPress, true);
    window.document.removeEventListener('pointercancel', finishSecondPress, true);
    window.removeEventListener('blur', finishSecondPress);
    pendingClick = null;
  };
  const commitPendingSelection = () => {
    if (!pendingClick) return;
    cancelPendingSelection();
    selectDocument(document.id);
  };
  const finishSecondPress = event => {
    const click = pendingClick;
    if (!click || click.secondDownAt === null) return;
    if (event.type !== 'blur' && event.pointerId !== click.secondPointerId) return;
    if (event.type !== 'pointerup' || !open.contains(event.target)) { commitPendingSelection(); return; }
    setTimeout(() => { if (pendingClick === click) commitPendingSelection(); }, 50);
  };
  const openReader = () => {
    cancelPendingSelection();
    window.tomeshedPreview.close(); window.tomeshedReader.open(document, open);
  };
  let suppressTouchClick = false;
  open.addEventListener('pointerdown', event => {
    activationPointerType = event.pointerType;
    if (!pendingClick || event.pointerType === 'touch') return;
    const now = performance.now();
    if (now - pendingClick.at >= doubleClickWindowMs) { commitPendingSelection(); return; }
    clearTimeout(pendingClick.timer);
    pendingClick.timer = null;
    pendingClick.secondDownAt = now;
    pendingClick.secondPointerId = event.pointerId;
    window.document.addEventListener('pointerup', finishSecondPress, true);
    window.document.addEventListener('pointercancel', finishSecondPress, true);
    window.addEventListener('blur', finishSecondPress);
  });
  open.addEventListener('click', event => {
    if (suppressTouchClick) { event.preventDefault(); suppressTouchClick = false; return; }
    if (window.document.body.classList.contains('reader-open')) return;
    const pointerType = event.pointerType || activationPointerType;
    if (event.detail === 0 || pointerType === 'touch') {
      cancelPendingSelection(); selectDocument(document.id); return;
    }
    if (pendingClick) {
      const secondClick = event.detail > 1 && pendingClick.pointerType === pointerType &&
        pendingClick.secondDownAt !== null && pendingClick.secondDownAt - pendingClick.at < doubleClickWindowMs;
      if (secondClick) { openReader(); return; }
      commitPendingSelection();
    }
    const click = {at: performance.now(), pointerType, secondDownAt: null, timer: null};
    click.timer = setTimeout(() => { if (pendingClick === click) commitPendingSelection(); }, doubleClickWindowMs);
    pendingClick = click;
  });
  open.addEventListener('dblclick', event => event.preventDefault());
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
  card.append(preview);
  catalogItems.set(document.id, document);
  updateDocumentSelection(card);
  const star = element('button', 'document-star');
  star.type = 'button'; star.setAttribute('aria-label', document.favorite ? 'Remove from favorites' : 'Add to favorites');
  star.setAttribute('aria-pressed', String(Boolean(document.favorite)));
  const starIcon = window.document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  starIcon.setAttribute('viewBox', '0 0 16 16'); starIcon.setAttribute('aria-hidden', 'true');
  const starPath = window.document.createElementNS('http://www.w3.org/2000/svg', 'path');
  starPath.setAttribute('d', 'M8 1.6l1.85 3.76 4.15.6-3 2.93.71 4.13L8 11.07l-3.71 1.95L5 8.89 2 5.96l4.15-.6z');
  starIcon.append(starPath); star.append(starIcon);
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
const panelFieldDrafts = new Map();
const panelMetadataQueues = new Map();
async function panelSaveMetadata(item, field, nextValue, onSuccess) {
  const previous = panelMetadataQueues.get(item.id) || Promise.resolve();
  const pending = previous.catch(() => {}).then(() => {
    const confirmed = catalogItems.get(item.id) || item;
    const payload = {title: confirmed.title, author: confirmed.author};
    payload[field] = nextValue;
    return documentMutation(item.id, 'metadata', {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)}, onSuccess);
  });
  panelMetadataQueues.set(item.id, pending);
  try { await pending; }
  finally { if (panelMetadataQueues.get(item.id) === pending) panelMetadataQueues.delete(item.id); }
}
function panelInlineField(item, field, label, suffix, method, bodyKey, maxLength) {
  const key = `${item.id}:${field}`;
  const value = item[field] || '';
  const row = element('div', 'document-inline-field'); row.dataset.field = field;
  const name = element('strong', 'document-inline-label', `${label}:`);
  const editor = element('span', 'document-inline-editor');
  row.append(name, editor);
  function draw() {
    editor.replaceChildren();
    const draft = panelFieldDrafts.get(key);
    if (!draft) {
      editor.append(element('span', 'document-inline-value', value));
      const edit = element('button', 'document-inline-icon', '✎'); edit.type = 'button'; edit.setAttribute('aria-label', `Edit ${label}`);
      edit.addEventListener('click', () => { panelFieldDrafts.set(key, {value}); draw(); editor.querySelector('input').focus(); });
      editor.append(edit);
      return;
    }
    const input = window.document.createElement('input'); input.value = draft.value; input.maxLength = maxLength;
    input.setAttribute('aria-label', label); input.name = `panel-${field}`;
    input.addEventListener('input', () => { draft.value = input.value; });
    const save = element('button', 'document-inline-icon', '✓'); save.type = 'button'; save.setAttribute('aria-label', `Save ${label}`);
    const cancel = element('button', 'document-inline-icon', '×'); cancel.type = 'button'; cancel.setAttribute('aria-label', `Cancel ${label}`);
    cancel.addEventListener('click', () => { panelFieldDrafts.delete(key); draw(); editor.querySelector('button').focus(); });
    async function commit() {
      if (draft.pending) return;
      draft.value = input.value;
      if (draft.value === value) { panelFieldDrafts.delete(key); draw(); return; }
      const nextValue = draft.value;
      draft.pending = true; input.disabled = true; save.disabled = true; cancel.disabled = true;
      try {
        if (suffix === 'metadata') await panelSaveMetadata(item, field, nextValue, () => panelFieldDrafts.delete(key));
        else await documentMutation(item.id, suffix, {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify({[bodyKey]: nextValue})}, () => panelFieldDrafts.delete(key));
      } finally {
        draft.pending = false; input.disabled = false; save.disabled = false; cancel.disabled = false;
      }
    }
    save.addEventListener('click', commit);
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') { event.preventDefault(); commit(); }
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); cancel.click(); }
    });
    editor.append(input, save, cancel);
  }
  draw();
  return row;
}
function panelTagEditor(item) {
  const shell = element('div', 'document-tag-editor');
  const tokens = element('div', 'document-tag-tokens');
  for (const tag of item.tags) {
    const chip = element('span', 'tag-chip', tag);
    const remove = element('button', 'tag-remove', '×'); remove.type = 'button'; remove.setAttribute('aria-label', `Remove tag ${tag}`);
    remove.addEventListener('click', () => documentMutation(item.id, 'tags', {method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tag})}));
    chip.append(remove); tokens.append(chip);
  }
  const input = window.document.createElement('input'); input.placeholder = 'Add tag'; input.maxLength = 64;
  input.setAttribute('aria-label', 'Add tag'); input.setAttribute('aria-expanded', 'false');
  const suggestions = element('div', 'document-tag-suggestions'); suggestions.setAttribute('role', 'listbox'); suggestions.hidden = true;
  function updateSuggestions() {
    suggestions.replaceChildren();
    const query = input.value.trim().toLocaleLowerCase();
    if (query) for (const tag of availableTags) {
      if (item.tags.some(attached => attached.toLocaleLowerCase() === tag.toLocaleLowerCase()) || !tag.toLocaleLowerCase().includes(query)) continue;
      const choice = element('button', 'tag-suggestion', tag); choice.type = 'button'; choice.setAttribute('role', 'option');
      choice.addEventListener('click', () => add(tag)); suggestions.append(choice);
    }
    suggestions.hidden = !suggestions.children.length;
    input.setAttribute('aria-expanded', String(!suggestions.hidden));
  }
  async function add(tag) {
    if (!tag.trim()) return;
    await documentMutation(item.id, 'tags', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tag: tag.trim()})});
  }
  input.addEventListener('input', updateSuggestions);
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ',') { event.preventDefault(); add(input.value); }
    else if (event.key === 'ArrowDown' && !suggestions.hidden) { event.preventDefault(); suggestions.querySelector('button').focus(); }
    else if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); suggestions.hidden = true; input.setAttribute('aria-expanded', 'false'); }
    else if (event.key === 'Backspace' && !input.value) tokens.querySelector('.tag-chip:last-child button')?.click();
  });
  suggestions.addEventListener('keydown', event => {
    const choices = [...suggestions.querySelectorAll('button')], index = choices.indexOf(window.document.activeElement);
    if (event.key === 'ArrowDown') { event.preventDefault(); choices[(index + 1) % choices.length].focus(); }
    if (event.key === 'ArrowUp') { event.preventDefault(); (index ? choices[index - 1] : input).focus(); }
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); suggestions.hidden = true; input.setAttribute('aria-expanded', 'false'); input.focus(); }
  });
  tokens.append(input); shell.append(tokens, suggestions);
  return shell;
}
function panelDownloads(item) {
  const formats = [];
  if (item.source_available) formats.push({label: `Original ${item.source_type.toUpperCase()}`, button: 'Download original', suffix: 'original'});
  if (item.structured_available && item.source_type !== 'docling') formats.push({label: 'Docling JSON (converted)', button: 'Download Docling JSON', suffix: 'docling'});
  if (!formats.length) return null;
  const group = element('div', 'document-download-split');
  const href = entry => `/api/documents/${encodeURIComponent(item.id)}/export/${entry.suffix}`;
  const main = element('a', 'document-download-main', formats[0].button); main.href = href(formats[0]); group.append(main);
  if (formats.length === 1) return group;
  const toggle = element('button', 'document-download-toggle', '▾'); toggle.type = 'button';
  toggle.setAttribute('aria-label', 'Choose download format'); toggle.setAttribute('aria-expanded', 'false');
  const menu = element('div', 'document-download-menu'); menu.setAttribute('role', 'menu'); menu.hidden = true;
  for (const entry of formats) {
    const link = element('a', '', entry.label); link.href = href(entry); link.setAttribute('role', 'menuitem');
    link.addEventListener('click', () => { menu.hidden = true; toggle.setAttribute('aria-expanded', 'false'); }); menu.append(link);
  }
  function setOpen(open) { menu.hidden = !open; toggle.setAttribute('aria-expanded', String(open)); if (open) menu.querySelector('a').focus(); }
  toggle.addEventListener('click', () => setOpen(menu.hidden));
  toggle.addEventListener('keydown', event => { if (event.key === 'ArrowDown') { event.preventDefault(); setOpen(true); } });
  menu.addEventListener('keydown', event => {
    const links = [...menu.querySelectorAll('a')], index = links.indexOf(window.document.activeElement);
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setOpen(false); toggle.focus(); }
    if (event.key === 'ArrowDown') { event.preventDefault(); links[(index + 1) % links.length].focus(); }
    if (event.key === 'ArrowUp') { event.preventDefault(); links[(index - 1 + links.length) % links.length].focus(); }
  });
  group.append(toggle, menu); return group;
}
function trashIcon() {
  const namespace = 'http://www.w3.org/2000/svg';
  const svg = window.document.createElementNS(namespace, 'svg');
  for (const [name, value] of Object.entries({'viewBox': '0 0 16 16', 'aria-hidden': 'true', 'fill': 'none', 'stroke': 'currentColor', 'stroke-width': '1.6', 'stroke-linecap': 'round', 'stroke-linejoin': 'round'})) svg.setAttribute(name, value);
  for (const d of ['M2.5 4h11', 'M6 4V2.5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1V4', 'M3.5 4l.7 9a1 1 0 0 0 1 .9h5.6a1 1 0 0 0 1-.9l.7-9', 'M6.5 7v4', 'M9.5 7v4']) {
    const path = window.document.createElementNS(namespace, 'path');
    path.setAttribute('d', d);
    svg.append(path);
  }
  return svg;
}
function renderDocumentInfo(document) {
  const content = element('div', 'document-info');
  const rail = element('div', 'reader-panel-rail');
  const details = element('div', 'reader-panel-details');
  content.append(rail, details);
  function action(icon, text, compact, onClick, danger = false) {
    const button = element('button', `document-action${danger ? ' danger' : ''}`);
    button.type = 'button'; button.setAttribute('aria-label', text);
    const iconContainer = element('span', 'document-action-icon');
    iconContainer.setAttribute('aria-hidden', 'true');
    if (typeof icon === 'function') iconContainer.append(icon());
    else iconContainer.textContent = icon;
    button.append(iconContainer);
    if (!compact) button.append(element('span', 'document-action-text', text));
    button.addEventListener('click', onClick);
    return button;
  }
  const addShelf = () => window.tomeshedBookshelves?.choose(document);
  const remove = async () => {
    if (!confirm(`Remove ${document.title}?`)) return;
    try { await api(`/api/documents/${encodeURIComponent(document.id)}`, {method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({confirm: document.title})}); removeSelectedDocuments([document.id]); window.tomeshedReader.close(); await refreshLibrary(); showLibraryNotice(`${document.title} was removed.`); }
    catch (error) { window.tomeshedReader.panelError(document.id, `Could not remove ${document.title}: ${error.message}`); }
  };
  rail.append(action('▤', 'Add to bookshelf', true, addShelf), action(trashIcon, 'Remove document', true, remove, true));
  details.append(panelTagEditor(document), action('▤', 'Add to bookshelf', false, addShelf));
  details.append(panelInlineField(document, 'title', 'Title', 'metadata', 'PATCH', 'title', 300));
  details.append(panelInlineField(document, 'author', 'Author', 'metadata', 'PATCH', 'author', 300));
  for (const [name, value] of [['Original filename', document.original_filename], ...(document.source_url ? [['Source URL', document.source_url]] : []), ['Source type', document.source_type.toUpperCase()], ['Size', `${document.byte_size} bytes`], ['Page count', `${document.page_count ?? 'Unknown'} (${document.count_kind})`], ['Imported', new Date(document.created_at * 1000).toLocaleString()], ['Import state', document.state], ['Reading state', document.reading_state.replace('_', ' ')], ['Last read', document.last_read_at ? new Date(document.last_read_at * 1000).toLocaleString() : 'Never']]) {
    const line = element('p'); line.append(element('strong', '', `${name}: `));
    if (name === 'Reading state') line.dataset.readerField = 'reading-state';
    if (name === 'Last read') line.dataset.readerField = 'last-read';
    line.append(element('span', '', value)); details.append(line);
  }
  details.append(panelInlineField(document, 'stored_filename', 'Stored filename', 'rename-file', 'POST', 'filename', 255));
  if (document.error) details.append(element('p', 'index-warning', document.error));
  if (document.state === 'ready_with_warning') {
    const retry = element('button', 'secondary', 'Retry indexing'); retry.type = 'button';
    retry.addEventListener('click', async () => { try { await api(`/api/documents/${encodeURIComponent(document.id)}/retry`, {method: 'POST'}); const updated = await api(`/api/documents/${encodeURIComponent(document.id)}`); window.tomeshedReader.updateDocument(updated); await refreshLibrary(); } catch (error) { window.tomeshedReader.panelError(document.id, `Retry indexing failed: ${error.message}`); } });
    details.append(retry);
  }
  const downloads = panelDownloads(document); if (downloads) details.append(downloads);
  if (document.can_manage_visibility) {
    const visibilityLabel = element('label', 'document-visibility', 'Visibility');
    const visibilityInput = window.document.createElement('select');
    for (const value of ['public', 'private']) { const option = window.document.createElement('option'); option.value = value; option.textContent = value; visibilityInput.append(option); }
    visibilityInput.value = document.visibility;
    visibilityInput.addEventListener('change', () => documentMutation(document.id, 'visibility', {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({visibility:visibilityInput.value})}));
    visibilityLabel.append(visibilityInput); details.append(visibilityLabel);
  }
  details.append(action(trashIcon, 'Remove document', false, remove, true));
  return content;
}
function showLibraryError(message) { $('libraryNotice').hidden = true; $('libraryError').textContent = message; $('libraryError').hidden = false; }
function showLibraryNotice(message) { $('libraryError').hidden = true; $('libraryNotice').textContent = message; $('libraryNotice').hidden = false; }
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
  $('catalogPager').hidden = endless || catalogTotal <= catalogEffectivePageSize;
  $('pagerInfo').textContent = `Page ${catalogPage + 1} of ${pages} · ${catalogTotal} ${catalogTotal === 1 ? 'result' : 'results'}`;
  $('pagerFirst').hidden = $('pagerLast').hidden = pages < 4;
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
  updateFilterButtonState();
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
      if (focusedId && focusedClass) document.querySelector(`.document-card[data-document-id="${CSS.escape(focusedId)}"] .${String(focusedClass).split(' ')[0]}`)?.focus({preventScroll: true});
      catalogLoaded = endless ? items.length : offset + items.length;
    }
    renderTagFilters(data.available_tags || []); updateFilterButtonState();
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
  finally { if (generation === catalogGeneration) { catalogLoading = false; updateCatalogNavigation(); requestAnimationFrame(loadVisibleEndless); await syncSelectionAccess(); } }
}
let importJobsGeneration = 0;
async function loadImportJobs() {
  const generation = ++importJobsGeneration;
  try {
    const data = await api('/api/imports');
    if (generation !== importJobsGeneration) return;
    const jobs = data.jobs.filter(job => ['pending', 'processing', 'failed'].includes(job.state));
    const activeCount = data.jobs.filter(job => ['pending', 'processing'].includes(job.state)).length;
    $('activeImportCount').textContent = activeCount || '';
    const importsButton = $('importsButton');
    const importsHadFocus = document.activeElement === importsButton;
    importsButton.hidden = activeCount === 0;
    if (importsButton.hidden && importsHadFocus) {
      ($('importsDrawer').hidden ? $('chooseFile') : $('closeImports')).focus();
    }
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
  } catch (error) { if (generation === importJobsGeneration) { $('importError').textContent = `Could not load imports: ${error.message}`; $('importError').hidden = false; } }
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
let importsReturnFocus = $('chooseFile');
function closeImports() {
  $('importsDrawer').hidden = true;
  $('importsButton').setAttribute('aria-expanded', 'false');
  $('chooseFile').setAttribute('aria-expanded', 'false');
  (importsReturnFocus.hidden ? $('chooseFile') : importsReturnFocus).focus();
}
function showImports(opener = $('chooseFile'), focusTarget = null) {
  if ($('importsDrawer').hidden) importsReturnFocus = opener;
  $('importsDrawer').hidden = false;
  $('importsButton').setAttribute('aria-expanded', 'true');
  $('chooseFile').setAttribute('aria-expanded', 'true');
  if (focusTarget) $(focusTarget).focus();
}
$('importsButton').addEventListener('click', () => $('importsDrawer').hidden ? showImports($('importsButton'), 'closeImports') : closeImports());
$('chooseFile').addEventListener('click', () => $('importsDrawer').hidden ? showImports($('chooseFile'), 'chooseLocalFile') : closeImports());
$('closeImports').addEventListener('click', closeImports);
const activeTransfers = new Map();
let retrySelection = null;
function showImportError(message) { showImports(); $('importError').textContent = message; $('importError').hidden = false; }
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
$('chooseLocalFile').addEventListener('click', () => $('uploadFile').click());
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
