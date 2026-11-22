"""Verify Feature 0009 paste, URL formats, progress, focus, and retry in Chromium."""

import http.server
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_documents import epub_bytes, json_bytes, pdf_bytes

ARTIFACTS = Path('/tmp/tomeshed-feature-0009-browser')


def paste(page, text='', target='body', extra=None, repeat=False):
    return page.evaluate('''({text,target,extra,repeat}) => {
      const data = new DataTransfer();
      if (text) data.setData('text/plain', text);
      if (extra === 'html') data.setData('text/html', '<a href="https://example.com/file.pdf">Book</a>');
      if (extra === 'file') data.items.add(new File(['image'], 'image.png', {type:'image/png'}));
      const event = new ClipboardEvent('paste', {clipboardData:data,bubbles:true,cancelable:true});
      document.querySelector(target).dispatchEvent(event);
      if (repeat) document.querySelector(target).dispatchEvent(event);
      return event.defaultPrevented;
    }''', dict(text=text, target=target, extra=extra, repeat=repeat))


def jobs(page):
    return page.request.get('/api/imports').json()['jobs']


def finished(page, job_id):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        job = next(row for row in jobs(page) if row['id'] == job_id)
        if job['state'] in ('ready', 'ready_with_warning', 'failed'):
            return job
        page.wait_for_timeout(50)
    raise AssertionError(f'Job did not finish: {job}')


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        fixtures = {'pdf': pdf_bytes(8), 'epub': epub_bytes(40), 'json': json_bytes()}
        captures = []
        slow_gates = {path: threading.Event() for path in ('/slowknown', '/slowunknown')}
        flaky_count = 0

        class Remote(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                nonlocal flaky_count
                captures.append({'path': self.path, 'headers': dict(self.headers)})
                path = urlsplit(self.path).path
                if path == '/flaky':
                    flaky_count += 1
                    content = b'bad source' if flaky_count == 1 else fixtures['json']
                elif path == '/bad.pdf':
                    content = b'<html>not PDF</html>'
                elif path.startswith('/slow'):
                    content = fixtures['pdf'] + b'\n%' + b' ' * 240000
                else:
                    content = fixtures[path.rsplit('/', 1)[-1].split('.')[0]]
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                if path != '/slowunknown':
                    self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                try:
                    if path.startswith('/slow'):
                        for offset in range(0, len(content), 8192):
                            self.wfile.write(content[offset:offset + 8192])
                            self.wfile.flush()
                            if offset == 0:
                                slow_gates[path].wait(timeout=20)
                            time.sleep(.10)
                    else:
                        self.wfile.write(content)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        remote = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Remote)
        threading.Thread(target=remote.serve_forever, daemon=True).start()
        remote_base = f'http://127.0.0.1:{remote.server_port}'
        env = dict(os.environ, TOMESHED_DB=str(folder / 'library.db'),
                   TOMESHED_LIBRARY_DIR=str(folder / 'library'), HOST='127.0.0.1', PORT=str(port),
                   TOMESHED_URL_ALLOWED_CIDRS='127.0.0.0/8')
        log = (ARTIFACTS / 'server.log').open('w')
        server = subprocess.Popen([sys.executable, 'tomeshed.py'], cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            for _ in range(300):
                try:
                    with urlopen(base + '/api/health', timeout=.2):
                        break
                except Exception:
                    time.sleep(.1)
            else:
                raise AssertionError('Server did not start')
            checks = []
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(base_url=base, viewport={'width': 1280, 'height': 850},
                                              permissions=['clipboard-read', 'clipboard-write'])
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                registrations = []
                page.on('request', lambda request: registrations.append(request.post_data_json)
                        if request.method == 'POST' and request.url == base + '/api/imports/url' else None)
                page.goto(base + '/login')
                page.locator('#password').fill('paste-password')
                page.locator('#password_confirmation').fill('paste-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_url(base + '/')
                page.wait_for_function('importJobsLoaded')

                # A real OS clipboard paste registers one job and preserves keyboard focus.
                url = remote_base + '/pdf?token=secret%2Bvalue&part=two#private-fragment'
                page.evaluate('(url) => navigator.clipboard.writeText(url)', url)
                page.locator('#chooseFile').focus()
                page.keyboard.press('Control+V')
                page.wait_for_function('!document.querySelector("#importsDrawer").hidden')
                page.wait_for_function('importJobStates.size === 1')
                assert len(registrations) == 1
                first = jobs(page)[0]
                assert finished(page, first['id'])['state'] in ('ready', 'ready_with_warning')
                page.wait_for_function('document.querySelector("#libraryCount").textContent === "1 result"')
                assert page.locator('#chooseFile').evaluate('(node) => document.activeElement === node')
                assert captures[0]['path'] == '/pdf?token=secret%2Bvalue&part=two'
                assert all('Cookie' not in capture['headers'] and 'Authorization' not in capture['headers'] for capture in captures)
                checks.append('AC-01,03: actual Control-V, one request/job/card, focus, unchanged query')

                # Native text editing retains clipboard input without URL registrations.
                before = len(registrations)
                for selector in ('#librarySearch', '#importUrl'):
                    page.locator(selector).fill('')
                    page.locator(selector).focus()
                    page.keyboard.press('Control+V')
                    assert page.locator(selector).input_value() == url
                page.locator('#librarySearch').fill('')
                page.evaluate('''() => {
                  const area=document.createElement('textarea');area.id='pasteArea';document.body.append(area);
                  const editor=document.createElement('div');editor.id='pasteEditor';editor.contentEditable='true';document.body.append(editor);
                  const owned=document.createElement('div');owned.id='pasteOwned';owned.setAttribute('role','textbox');document.body.append(owned);
                }''')
                for selector in ('#pasteArea', '#pasteEditor'):
                    page.locator(selector).focus()
                    page.keyboard.press('Control+V')
                    value = page.locator(selector).input_value() if selector == '#pasteArea' else page.locator(selector).inner_text()
                    assert value == url
                assert not paste(page, url, '#pasteOwned')
                page.evaluate('''() => {const dialog=document.createElement('dialog');dialog.id='pasteModal';document.body.append(dialog);dialog.showModal()}''')
                assert not paste(page, url)
                page.evaluate('document.querySelector("#pasteModal").remove()')
                page.evaluate('document.querySelectorAll("#pasteArea,#pasteEditor,#pasteOwned").forEach(node=>node.remove())')
                for text, extra in [('ordinary prose', None), (url + '\n' + url, None),
                                    ('Read ' + url, None), ('ftp://example.com/a.pdf', None),
                                    ('', 'html'), (url, 'file')]:
                    assert not paste(page, text, extra=extra)
                page.wait_for_timeout(250)
                assert len(registrations) == before
                checks.append('AC-02: native inputs, textarea/contenteditable/editor, modal, rejected clipboard payloads')

                # Server validation errors are announced; repeated dispatch of one event submits once.
                for invalid in ('https://', 'http:/example.com/book.pdf', 'https://user:password@example.com/file.pdf', 'https://example.com/' + 'x' * 4100):
                    count = len(jobs(page))
                    assert paste(page, invalid, repeat=True)
                    page.wait_for_function('document.querySelector("#importError").hidden === false')
                    page.wait_for_function('urlRegistrations === 0')
                    assert len(jobs(page)) == count
                    assert page.locator('#importError').get_attribute('role') == 'alert'
                    assert 'failed' in page.locator('#importAnnouncement').inner_text()
                checks.append('AC-03,12: credential/malformed/length validation and accessible feedback')

                # Slow known/unknown totals expose one pending job before download completes.
                snapshots = []
                for path in ('/slowknown', '/slowunknown'):
                    count = len(registrations)
                    assert paste(page, '  \n' + remote_base + path + '\n  ', repeat=True)
                    page.wait_for_function('urlRegistrations === 0')
                    assert len(registrations) == count + 1
                    job = jobs(page)[0]
                    selector = f'.import-job[data-job-id="{job["id"]}"]'
                    page.wait_for_timeout(200)
                    page.wait_for_function('''id => [...document.querySelectorAll('.import-job')].some(row=>row.dataset.jobId===id && row.textContent.includes('Downloading') && /[1-9][0-9]*.*bytes received/.test(row.textContent))''', arg=job['id'])
                    first_bytes = next(row for row in jobs(page) if row['id'] == job['id'])['bytes_received']
                    assert first_bytes > 0
                    text = page.locator(selector).inner_text()
                    assert (' / ' in text) == (path == '/slowknown')
                    assert '%' not in text
                    slow_gates[path].set()
                    page.wait_for_function('''async ({id,bytes}) => (await (await fetch('/api/imports')).json()).jobs.some(job=>job.id===id && job.bytes_received>bytes)''', arg={'id': job['id'], 'bytes': first_bytes})
                    page.screenshot(path=str(ARTIFACTS / (path[1:] + '.png')))
                    deadline = time.monotonic() + 90
                    states = set()
                    while time.monotonic() < deadline:
                        current = next(row for row in jobs(page) if row['id'] == job['id'])
                        states.add(current['state'])
                        if current['state'] in ('ready', 'ready_with_warning', 'failed'):
                            break
                        page.wait_for_timeout(20)
                    assert current['state'] in ('ready', 'ready_with_warning'), current
                    assert 'processing' in states, states
                    snapshots.append({'path': path, 'states': sorted(states), 'first_bytes': first_bytes})
                checks.append('AC-04: known/unknown totals, increasing bytes, pending then processing')

                # URL form and paste both accept all supported types despite misleading extensions.
                for mode in ('paste', 'form'):
                    for kind in ('pdf', 'epub', 'json'):
                        prior = {job['id'] for job in jobs(page)}
                        value = remote_base + '/' + kind + '.unrelated?download=yes'
                        if mode == 'paste':
                            assert paste(page, value)
                        else:
                            page.locator('#importUrl').fill(value)
                            page.locator('#urlImportForm button').click()
                        page.wait_for_function('urlRegistrations === 0')
                        result = next(job for job in jobs(page) if job['id'] not in prior)
                        result = finished(page, result['id'])
                        assert result['state'] in ('ready', 'ready_with_warning'), result
                        detail = page.request.get('/api/documents/' + result['document_id']).json()
                        assert detail['source_type'] == ('docling' if kind == 'json' else kind)
                        assert detail['original_filename'].endswith('.' + kind)
                        assert page.request.get('/api/documents/' + result['document_id'] + '/source').body() == fixtures[kind]
                checks.append('AC-05,07,12: paste/form PDF, EPUB, JSON parity and original bytes')

                # Catalog refresh preserves the focused bookshelf control as well as document controls.
                shelf = page.request.post('/api/bookshelves', data={'name': 'Paste focus shelf'}, headers={'Origin': base}).json()
                page.evaluate("() => {const select=document.querySelector('#filterScope');select.value='bookshelves';select.dispatchEvent(new Event('change'));}")
                page.wait_for_function('!catalogLoading && document.querySelectorAll(".bookshelf-card-open").length > 0')
                page.locator('#closeImports').click()
                focus_selector = f'.bookshelf-card[data-bookshelf-id="{shelf["id"]}"] .bookshelf-card-open'
                page.locator(focus_selector).focus()
                prior = {job['id'] for job in jobs(page)}
                assert paste(page, remote_base + '/json', target=focus_selector)
                page.wait_for_function('urlRegistrations === 0')
                focused_import = next(job for job in jobs(page) if job['id'] not in prior)
                assert finished(page, focused_import['id'])['state'] == 'ready'
                page.wait_for_function('!catalogLoading')
                page.wait_for_timeout(1000)
                assert page.locator(focus_selector).evaluate('(node) => document.activeElement === node')
                assert page.locator('#filterScope').input_value() == 'bookshelves'
                page.evaluate("() => {const select=document.querySelector('#filterScope');select.value='all';select.dispatchEvent(new Event('change'));}")
                checks.append('AC-08: bookshelf focus survives paste and subsequent SSE catalog refresh')

                page.wait_for_function('!catalogLoading && document.querySelectorAll(".document-card").length > 0')
                page.locator('#closeImports').click()
                focused_document = page.locator('.document-card').first.get_attribute('data-document-id')
                focus_selector = f'.document-card[data-document-id="{focused_document}"] .document-open'
                page.locator(focus_selector).focus()
                prior = {job['id'] for job in jobs(page)}
                assert paste(page, remote_base + '/json', target=focus_selector)
                page.wait_for_function('urlRegistrations === 0')
                focused_import = next(job for job in jobs(page) if job['id'] not in prior)
                assert finished(page, focused_import['id'])['state'] == 'ready'
                page.wait_for_function('!catalogLoading')
                page.wait_for_timeout(1000)
                assert page.locator(focus_selector).evaluate('(node) => document.activeElement === node')
                checks.append('AC-08: document focus survives paste, SSE refresh, and preview timer')

                # Read a PDF while a filtered-out JSON import completes; preserve reader position.
                page.locator('#closeImports').click()
                page.locator('#librarySearch').fill('pdf')
                page.locator('#sortToggle').click()
                page.select_option('#sortField', 'title')
                page.select_option('#sortDirection', 'asc')
                page.locator('#sortToggle').click()
                page.wait_for_function('!catalogLoading && document.querySelectorAll(".document-card").length > 0')
                page.locator('.document-card .document-open').first.dblclick()
                page.locator('#readerContent .pdf-page').first.wait_for()
                page.locator('#readerNext').click()
                page.wait_for_timeout(200)
                page.locator('#readerScroll').focus()
                position = page.locator('#readerScroll').evaluate('(node) => node.scrollTop')
                page.evaluate('(url) => navigator.clipboard.writeText(url)', remote_base + '/json?token=private#omit')
                prior = {job['id'] for job in jobs(page)}
                page.keyboard.press('ControlOrMeta+V')
                page.wait_for_function('urlRegistrations === 0')
                result = next(job for job in jobs(page) if job['id'] not in prior)
                assert finished(page, result['id'])['state'] == 'ready'
                page.wait_for_function('document.querySelector("#importStatus").textContent.includes("Imported")')
                assert page.locator('#readerScroll').evaluate('(node) => document.activeElement === node')
                assert page.locator('#readerScroll').evaluate('(node) => node.scrollTop') == position
                assert page.locator('#librarySearch').input_value() == 'pdf'
                assert page.locator('#sortField').input_value() == 'title'
                assert page.locator('#sortDirection').input_value() == 'asc'
                assert 'filters remain applied' in page.locator('#importStatus').inner_text()
                assert page.locator(f'.import-job[data-job-id="{result["id"]}"]').count() == 0
                assert page.locator('#importsDrawer').is_visible()
                assert page.locator('#importsDrawer').evaluate('(node) => getComputedStyle(node).zIndex') == '130'
                page.locator('#importUrl').focus()
                assert page.locator('#importUrl').evaluate('(node) => document.activeElement === node')
                page.locator('#closeImports').click()
                page.locator('#readerDocumentPanel').get_by_role('button', name='Edit Title', exact=True).click()
                page.locator('input[name="panel-title"]').fill('')
                count = len(registrations)
                page.keyboard.press('Control+V')
                assert page.locator('input[name="panel-title"]').input_value().endswith('/json?token=private#omit')
                assert len(registrations) == count
                page.get_by_role('button', name='Cancel Title', exact=True).click()
                page.locator('#readerClose').click()
                page.locator('#librarySearch').fill('')
                page.wait_for_function('!catalogLoading')
                page.locator(f'.document-card[data-document-id="{first["document_id"]}"] .document-open').dblclick()
                source_text = page.locator('#readerPanelContent').inner_text()
                assert 'REDACTED' in source_text and 'secret' not in source_text and 'private-fragment' not in source_text
                page.locator('#readerClose').click()
                checks.append('AC-01,02,08,10: reader paste, metadata editing, focus/position/filter/sort preservation, redacted panel')

                # A failed URL remains reachable and retries through a new job.
                prior = {job['id'] for job in jobs(page)}
                assert paste(page, remote_base + '/flaky?token=retry-secret#private')
                page.wait_for_function('urlRegistrations === 0')
                failure = next(job for job in jobs(page) if job['id'] not in prior)
                assert finished(page, failure['id'])['state'] == 'failed'
                page.wait_for_function('document.querySelector("#importsButton").hidden')
                page.locator('#closeImports').click()
                page.locator('#chooseFile').click()
                row = page.locator(f'.import-job[data-job-id="{failure["id"]}"]')
                assert row.is_visible()
                assert 'retry-secret' not in row.inner_text() and '#private' not in row.inner_text()
                prior = {job['id'] for job in jobs(page)}
                row.get_by_role('button', name='Retry').click()
                page.wait_for_function('''ids => fetch('/api/imports').then(r=>r.json()).then(data=>data.jobs.some(job=>!ids.includes(job.id)))''', arg=list(prior))
                retry = next(job for job in jobs(page) if job['id'] not in prior)
                assert finished(page, retry['id'])['state'] == 'ready'
                assert retry['document_id'] != failure['document_id']
                assert 'Ctrl-V' in page.locator('#pasteImportHelp').inner_text()
                assert 'text fields' in page.locator('#pasteImportHelp').inner_text()
                checks.append('AC-06,08,11,12: retained failed details, Retry new attempt, paste help')

                # Exercise a real SSE reconnection and reconcile a missed import.
                page.locator('#closeImports').click()
                stream_requests = []
                page.on('request', lambda request: stream_requests.append(request.url) if request.url.endswith('/api/events') else None)
                context.set_offline(True)
                server.terminate()
                server.wait(timeout=10)
                page.wait_for_timeout(200)
                server = subprocess.Popen([sys.executable, 'tomeshed.py'], cwd=ROOT, env=env, stdout=log, stderr=log)
                for _ in range(300):
                    try:
                        with urlopen(base + '/api/health', timeout=.2):
                            break
                    except Exception:
                        page.wait_for_timeout(100)
                else:
                    raise AssertionError('Server did not restart')
                # Register while the browser is offline; reconnect must reconcile the missed job.
                from urllib.request import Request
                cookie = '; '.join(cookie['name'] + '=' + cookie['value'] for cookie in context.cookies())
                request = Request(base + '/api/imports/url', data=json.dumps({'url': remote_base + '/json'}).encode(),
                                  headers={'Cookie': cookie, 'Content-Type': 'application/json', 'Origin': base})
                with urlopen(request) as response:
                    disconnected = json.load(response)
                context.set_offline(False)
                assert finished(page, disconnected['id'])['state'] == 'ready'
                page.wait_for_function('''id => importJobStates.get(id) === 'ready' ''', arg=disconnected['id'], timeout=20000)
                assert stream_requests
                checks.append('AC-11: actual EventSource disconnect/reconnect refreshes missed job')
                assert not errors, errors
                page.screenshot(path=str(ARTIFACTS / 'completed.png'))
                (ARTIFACTS / 'report.json').write_text(json.dumps({'checks': checks, 'progress': snapshots, 'registrations': len(registrations), 'jobs': len(jobs(page)), 'page_errors': errors}, indent=2))
                browser.close()
            print(json.dumps({'result': 'passed', 'checks': checks, 'artifacts': str(ARTIFACTS)}, indent=2))
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
            log.close()
            remote.shutdown()
            remote.server_close()


if __name__ == '__main__':
    main()
