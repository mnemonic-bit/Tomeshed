"""Feature 0009 URL format, transfer, privacy, and recovery acceptance checks."""

import http.server
import importlib
import ipaddress
import threading
import time
from urllib.parse import quote, urlsplit

import pytest

from test_documents import epub_bytes, fake_result, json_bytes, pdf_bytes, signed_in, wait_job
from test_file_workflows import module, register, transfer


@pytest.fixture
def remote():
    routes, requests = {}, []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, dict(self.headers)))
            status, headers, body = routes[urlsplit(self.path).path]
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, str(value))
            self.end_headers()
            try:
                if callable(body):
                    body(self.wfile)
                else:
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_port}', routes, requests
    server.shutdown()
    server.server_close()


def allow_local(module, monkeypatch):
    module.document_library.files.allowed_cidrs = [ipaddress.ip_network('127.0.0.0/8')]
    monkeypatch.setattr(module.document_library, '_run_conversion', fake_result)
    return signed_in(module)


def submit(client, url):
    result = client.post('/api/imports/url', json={'url': url})
    assert result.status_code == 202, result.json
    return result.json


@pytest.mark.parametrize('content,kind,extension', [
    (pdf_bytes(1), 'pdf', 'pdf'), (epub_bytes(), 'epub', 'epub'), (json_bytes(), 'docling', 'json')])
@pytest.mark.parametrize('path', ['/download', '/misleading.pdf', '/source.unrelated'])
def test_detected_formats_and_url_upload_parity(module, monkeypatch, remote, content, kind, extension, path):
    client = allow_local(module, monkeypatch)
    base, routes, requests = remote
    routes[path] = (200, {'Content-Type': 'application/octet-stream'}, content)
    routes['/redirect'] = (302, {'Location': path + '?token=a%2Fb&x=1&x=2'}, b'')
    url = base + '/redirect?initial=secret#fragment'
    job = submit(client, '  ' + url + '\n')
    ready = wait_job(client, job['id'], 'ready')
    downloaded = client.get(f'/api/documents/{job["document_id"]}').json
    assert downloaded['source_type'] == kind
    assert downloaded['stored_filename'].endswith('.' + extension)
    assert downloaded['source_url'] == base + '/redirect?initial=REDACTED'
    assert client.get(f'/api/documents/{job["document_id"]}/export/original').data == content
    assert requests[-1][0] == path + '?token=a%2Fb&x=1&x=2'
    assert all('Cookie' not in headers and 'Authorization' not in headers for _, headers in requests)
    assert ready['bytes_received'] == len(content)
    local = register(client, downloaded['original_filename'], len(content)).json
    assert transfer(client, local['id'], content).status_code == 202
    wait_job(client, local['id'], 'ready')
    uploaded = client.get(f'/api/documents/{local["document_id"]}').json
    for key in ('source_type', 'title', 'author', 'owner_user_id', 'visibility', 'thumbnail_available', 'state', 'page_count', 'count_kind'):
        assert uploaded[key] == downloaded[key], key
    assert client.get('/api/documents').json['library_total'] == 2


@pytest.mark.parametrize('status,content', [(200, b'<html>not PDF</html>'), (200, b'{"ordinary":true}'),
    (200, b'%PDF-broken'), (200, b'PK\x03\x04broken'), (200, b''), (404, b'not found')])
def test_rejected_sources_leave_no_document_or_source(module, monkeypatch, remote, status, content):
    client = allow_local(module, monkeypatch)
    base, routes, _ = remote
    routes['/disguised.pdf'] = (status, {'Content-Type': 'application/pdf'}, content)
    job = submit(client, base + '/disguised.pdf?secret=hidden#fragment')
    failed = wait_job(client, job['id'], 'failed')
    assert failed['error']
    assert not list((module.document_library.root / 'sources' / job['document_id']).glob('*'))
    assert client.get('/api/documents').json['library_total'] == 0


def test_multibyte_url_filename_preserves_detected_extension_and_source(module, monkeypatch, remote):
    client = allow_local(module, monkeypatch)
    base, routes, _ = remote
    path = '/' + quote('書' * 100 + '.pdf')
    source = json_bytes()
    routes[path] = (200, {}, source)
    job = submit(client, base + path)
    wait_job(client, job['id'], 'ready')
    document = client.get(f'/api/documents/{job["document_id"]}').json
    assert document['source_type'] == 'docling'
    assert document['stored_filename'].endswith('.json')
    assert len(document['stored_filename'].encode('utf-8')) <= 255
    assert client.get(f'/api/documents/{job["document_id"]}/export/original').data == source


@pytest.mark.parametrize('value', ['http://', 'https://[broken/', 'https://u:p@example.com/book',
    'http://example.com:99999/a', 'http://example.com/' + 'a' * 4096, 'https://bad host/a',
    'http://example.com/book?token=secret\x7f'])
def test_invalid_http_urls_create_no_job(module, value):
    client = signed_in(module)
    assert client.post('/api/imports/url', json={'url': value}).status_code == 400
    assert client.get('/api/imports').json['jobs'] == []


@pytest.mark.parametrize('known_total', [True, False])
def test_transfer_progress_precedes_processing_and_sse(module, monkeypatch, remote, known_total):
    client = allow_local(module, monkeypatch)
    base, routes, _ = remote
    source = pdf_bytes(1)
    first_sent, release, processing, finish = (threading.Event() for _ in range(4))

    def body(stream):
        stream.write(source[:100]); stream.flush(); first_sent.set()
        assert release.wait(5)
        stream.write(source[100:]); stream.flush()

    def conversion(path, filename, staging):
        processing.set()
        assert finish.wait(5)
        return fake_result(path, filename, staging)

    monkeypatch.setattr(module.document_library, '_run_conversion', conversion)
    routes['/slow'] = (200, {'Content-Length': len(source)} if known_total else {}, body)
    events = client.get('/api/events', buffered=False)
    assert b'event: ready' in next(events.response)
    job = submit(client, base + '/slow')
    try:
        assert first_sent.wait(5)
        for _ in range(100):
            pending = next(row for row in client.get('/api/imports').json['jobs'] if row['id'] == job['id'])
            if pending['bytes_received'] == 100:
                break
            time.sleep(.01)
        assert pending['state'] == 'pending' and pending['bytes_received'] == 100
        assert pending['expected_bytes'] == (len(source) if known_total else None)
        assert client.get('/api/documents').json['library_total'] == 0
        assert next(events.response) == b'event: change\ndata: {}\n\n'
        release.set()
        assert processing.wait(5)
        row = next(row for row in client.get('/api/imports').json['jobs'] if row['id'] == job['id'])
        assert row['state'] == 'processing' and row['bytes_received'] == len(source)
    finally:
        release.set(); finish.set(); events.close()
    wait_job(client, job['id'], 'ready')


@pytest.mark.parametrize('kind,source', [('pdf', pdf_bytes(1)), ('epub', epub_bytes())])
def test_extraction_warning_retry_preserves_downloaded_source_and_id(module, monkeypatch, remote, kind, source):
    client = allow_local(module, monkeypatch)
    base, routes, _ = remote
    routes['/source'] = (200, {}, source)
    import document_processing

    def failed_extraction(path):
        raise RuntimeError('forced extraction failure')

    monkeypatch.setattr(document_processing, 'extract_docling', failed_extraction)
    monkeypatch.setattr(module.document_library, '_run_conversion', document_processing.process_document)
    job = submit(client, base + '/source')
    wait_job(client, job['id'], 'ready_with_warning')
    document_id = job['document_id']
    assert client.get(f'/api/documents/{document_id}/export/original').data == source
    assert client.get(f'/api/documents/{document_id}').json['source_type'] == kind
    monkeypatch.setattr(module.document_library, '_run_conversion', fake_result)
    retry = client.post(f'/api/documents/{document_id}/retry')
    assert retry.status_code == 202 and retry.json['document_id'] == document_id
    wait_job(client, retry.json['id'], 'ready')
    assert client.get('/api/documents').json['library_total'] == 1
    assert client.get(f'/api/documents/{document_id}/export/original').data == source


def test_download_retry_and_restart_reconciliation(module, monkeypatch, remote):
    client = allow_local(module, monkeypatch)
    base, routes, _ = remote
    routes['/retry'] = (503, {}, b'')
    failed = submit(client, base + '/retry?token=retained#hidden')
    wait_job(client, failed['id'], 'failed')
    routes['/retry'] = (200, {}, json_bytes())
    retried = client.post(f'/api/imports/{failed["id"]}/retry')
    assert retried.status_code == 202 and retried.json['id'] != failed['id']
    wait_job(client, retried.json['id'], 'ready')
    library = module.document_library
    pending, pending_doc, pending_path = library.files.register('Incomplete', 'url', base + '/retry')
    (library.root / pending_path).write_bytes(b'partial')
    resumed, resumed_doc, resumed_path = library.files.register('Recoverable', 'url', base + '/retry')
    (library.root / resumed_path).write_bytes(json_bytes())
    with module.db() as conn:
        conn.execute("UPDATE import_jobs SET state='processing', transfer_complete=1 WHERE id=?", (resumed,))
    library.pool.shutdown(wait=True)
    monkeypatch.setattr(module.DocumentLibrary, '_run_conversion', lambda self, source, filename, staging: fake_result(source, filename, staging))
    reloaded = importlib.reload(module)
    library = reloaded.document_library
    client = signed_in(reloaded)
    wait_job(client, pending, 'failed')
    wait_job(client, resumed, 'ready')
    assert not (library.root / pending_path).exists()
    assert client.get('/api/documents').json['library_total'] == 2
    library.reconcile()
    assert client.get('/api/documents').json['library_total'] == 2


@pytest.mark.parametrize('limit', ['stream_size', 'connection', 'total', 'truncated'])
def test_transfer_limit_failures_remove_source(module, monkeypatch, remote, limit):
    client = allow_local(module, monkeypatch)
    base, routes, _ = remote
    source = pdf_bytes(1)
    files = module.document_library.files
    release = threading.Event()
    if limit == 'stream_size':
        module.app.config['MAX_UPLOAD_BYTES'] = 100
        routes['/limited'] = (200, {}, source)
    elif limit == 'truncated':
        routes['/limited'] = (200, {'Content-Length': len(source) + 20}, source)
    else:
        files.connect_timeout = .05 if limit == 'connection' else 1
        files.total_timeout = .05 if limit == 'total' else 5
        def slow(stream):
            release.wait(5)
            stream.write(source)
        routes['/limited'] = (200, {}, slow)
    job = submit(client, base + '/limited')
    try:
        assert wait_job(client, job['id'], 'failed')['error']
    finally:
        release.set()
    assert not list((files.root / 'sources' / job['document_id']).glob('*'))
    assert client.get('/api/documents').json['library_total'] == 0


def test_account_job_document_event_access_and_url_redaction(module, monkeypatch, remote):
    admin = allow_local(module, monkeypatch)
    base, routes, _ = remote
    routes['/private'] = (200, {}, json_bytes())
    routes['/failed'] = (503, {}, b'')
    users = []
    for username in ('owner', 'other'):
        result = admin.post('/api/users', json={'username': username, 'name': username, 'password': 'reader-password', 'role': 'normal'})
        assert result.status_code == 201
        client = module.app.test_client()
        assert client.post('/login', data={'username': username, 'password': 'reader-password'}).status_code == 302
        users.append((client, result.json['id']))
    (owner, owner_id), (other, _) = users
    job = submit(owner, base + '/private?token=secret#hidden')
    wait_job(owner, job['id'], 'ready')
    with module.db() as conn:
        conn.execute("UPDATE documents SET visibility='private' WHERE id=?", (job['document_id'],))
    assert not other.get('/api/imports').json['jobs']
    for suffix in ('', '/source', '/export/original'):
        assert other.get(f'/api/documents/{job["document_id"]}' + suffix).status_code == 404
    assert other.post(f'/api/imports/{job["id"]}/retry').status_code == 404
    assert other.get('/api/documents').json['total'] == 0
    events = other.get('/api/events', buffered=False)
    assert next(events.response) == b'retry: 1000\nevent: ready\ndata: {}\n\n'
    module.document_library.publish()
    assert next(events.response) == b'event: change\ndata: {}\n\n'
    events.close()
    failed = submit(owner, base + '/failed?token=secret#hidden')
    wait_job(owner, failed['id'], 'failed')
    anonymous = module.app.test_client()
    assert anonymous.post('/api/imports/url', json={'url': base + '/private'}).status_code == 401
    assert anonymous.post(f'/api/imports/{failed["id"]}/retry').status_code == 401
    assert admin.patch(f'/api/users/{owner_id}', json={'suspended': True}).status_code == 200
    assert owner.post('/api/imports/url', json={'url': base + '/private'}).status_code == 401
    assert owner.post(f'/api/imports/{failed["id"]}/retry').status_code == 401
    assert admin.post('/api/imports/url', json={'url': base + '/private'}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert admin.post(f'/api/imports/{failed["id"]}/retry', headers={'Origin': 'https://evil.example'}).status_code == 403
    detail = admin.get(f'/api/documents/{job["document_id"]}').json
    assert detail['source_url'] == base + '/private?token=REDACTED'
    monkeypatch.setattr(module.document_library.files, 'checked_addresses', lambda *args: (_ for _ in ()).throw(ValueError(base + '/error?token=secret#fragment')))
    error_job = submit(admin, base + '/private')
    error = wait_job(admin, error_job['id'], 'failed')['error']
    assert 'token=REDACTED' in error and 'secret' not in error and 'fragment' not in error
