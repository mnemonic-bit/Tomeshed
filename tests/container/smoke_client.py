"""Exercise the installed application through HTTP inside an isolated container."""
import concurrent.futures
import http.cookiejar
import io
import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile

from pypdf import PdfWriter

BASE = 'http://127.0.0.1:5000'
VERSION = sys.argv[2]
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(path, data=None, headers=None, method=None):
    request = urllib.request.Request(BASE + path, data=data, headers=headers or {}, method=method)
    with opener.open(request, timeout=30) as response:
        content = response.read()
        return json.loads(content) if response.headers.get_content_type() == 'application/json' else content


def login(setup=False):
    fields = {'username': 'admin', 'password': 'smoke-password'}
    if setup:
        fields['password_confirmation'] = fields['password']
    call('/login', urllib.parse.urlencode(fields).encode())


def import_file(name, content):
    boundary = 'tomeshed-smoke-boundary'
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
    job = call('/api/imports', body, {'Content-Type': 'multipart/form-data; boundary=' + boundary})
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        row = next(item for item in call('/api/imports')['jobs'] if item['id'] == job['id'])
        if row['state'] in ('ready', 'ready_with_warning'):
            return job['document_id']
        if row['state'] == 'failed':
            raise AssertionError(row)
        time.sleep(.3)
    raise AssertionError(f'{name} conversion timed out')


def fixtures():
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=300, height=400)
    pdf = io.BytesIO()
    writer.write(pdf)
    epub = io.BytesIO()
    with zipfile.ZipFile(epub, 'w') as archive:
        archive.writestr('mimetype', 'application/epub+zip')
        archive.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
        archive.writestr('OPS/book.opf', '<package><metadata><title>Smoke EPUB</title></metadata><manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="chapter"/></spine></package>')
        archive.writestr('OPS/chapter.xhtml', '<html><body><p>Smoke EPUB chapter.</p></body></html>')
    return pdf.getvalue(), epub.getvalue()


health = call('/api/health')
assert health['ok'] is True and health['version'] == VERSION, health
if sys.argv[1] == 'phase1':
    login(setup=True)
    pdf, epub = fixtures()
    pdf_id = import_file('smoke.pdf', pdf)
    epub_id = import_file('smoke.epub', epub)
    for document_id, source in ((pdf_id, pdf), (epub_id, epub)):
        base = f'/api/documents/{document_id}'
        assert call(base)['id'] == document_id
        assert call(base + '/source') == source
        assert call(base + '/reader')
    base = f'/api/documents/{pdf_id}'
    assert call(base + '/reader/page/1').startswith(b'\x89PNG')
    assert call(base + '/preview/page/1').startswith(b'\x89PNG')
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        paths = [base + ('/reader/page/1' if index % 2 else '/preview/page/1') for index in range(24)]
        for payload in pool.map(call, paths):
            assert payload.startswith(b'\x89PNG')
    saved = {'locator': {'page': 2, 'offset': 0.2}, 'percent': 50}
    assert call(base + '/progress', json.dumps(saved).encode(), {'Content-Type': 'application/json'}, 'PUT')
    print('phase1: non-root, health, PDF/EPUB imports and sources, reading, concurrent PDF reader/preview')
elif sys.argv[1] == 'phase2':
    login()
    rows = call('/api/documents')['documents']
    assert {row['source_type'] for row in rows} >= {'pdf', 'epub'}, rows
    pdf_id = next(row['id'] for row in rows if row['source_type'] == 'pdf')
    assert call(f'/api/documents/{pdf_id}/source').startswith(b'%PDF')
    position = call(f'/api/documents/{pdf_id}/progress')['position']
    assert position['locator']['page'] == 2, position
    print('phase2: account, catalog, source and reading position persisted after recreation')
else:
    raise SystemExit('Unknown smoke phase')
