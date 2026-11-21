"""File workflow checks across transfers, managed files, URLs, and inbox scans."""

import importlib
import io
import json
import os
import socket
import threading
import time
import zipfile
from pathlib import Path

import pytest

from test_documents import fake_result, pdf_bytes, signed_in, wait_job


def valid_result(source, filename, staging):
    result = fake_result(source, filename, staging)
    if result.get('artifact'):
        from docling_core.types.doc import DoclingDocument
        document = DoclingDocument(name='Structured export')
        document.add_title('Book')
        (staging / result['artifact']).write_text(json.dumps(document.export_to_dict()))
    return result


@pytest.fixture
def module(tmp_path, monkeypatch):
    monkeypatch.setenv('TOMESHED_DB', str(tmp_path / 'library.db'))
    monkeypatch.setenv('TOMESHED_LIBRARY_DIR', str(tmp_path / 'library'))
    monkeypatch.delenv('TOMESHED_INGEST_DIR', raising=False)
    monkeypatch.delenv('TOMESHED_URL_ALLOWED_CIDRS', raising=False)
    import tomeshed
    current = importlib.reload(tomeshed)
    current.app.config.update(TESTING=True)
    return current


def register(client, filename='Book.pdf', size=None):
    return client.post('/api/imports/register', json={'filename':filename,'size':size})


def transfer(client, job, data):
    return client.put(f'/api/imports/{job}/file', data=data, content_type='application/octet-stream')


def test_registered_transfer_cancel_retry_export_and_removal(module, monkeypatch):
    monkeypatch.setattr(module.document_library, '_run_conversion', valid_result)
    client = signed_in(module)
    source = pdf_bytes(1)
    pending = register(client, 'Cancelled.pdf', len(source)).json
    assert client.post(f'/api/imports/{pending["id"]}/cancel').status_code == 200
    assert transfer(client,pending['id'],source).status_code == 409
    with module.db() as conn:
        cancelled = conn.execute('SELECT state,error FROM import_jobs WHERE id=?',(pending['id'],)).fetchone()
    assert tuple(cancelled) == ('failed','Cancelled by user')
    assert not list((module.document_library.root/'sources'/pending['document_id']).glob('*'))
    retry = client.post(f'/api/imports/{pending["id"]}/retry')
    assert retry.json['reselect'] is True

    registered = register(client, 'Original.pdf', len(source)).json
    assert transfer(client,registered['id'],source).status_code == 202
    wait_job(client, registered['id'], 'ready')
    assert client.post(f'/api/imports/{registered["id"]}/cancel').status_code == 409
    document_id = registered['document_id']
    detail = client.get(f'/api/documents/{document_id}').json
    assert detail['original_filename'] == 'Original.pdf'
    assert 'stored_filename' not in detail
    original = client.get(f'/api/documents/{document_id}/export/original')
    assert original.data == source and b'Original.pdf' in original.headers['Content-Disposition'].encode()
    structured = client.get(f'/api/documents/{document_id}/export/docling')
    assert structured.status_code == 200 and structured.mimetype == 'application/json'
    with module.db() as conn:
        artifact = conn.execute('SELECT artifact_path FROM documents WHERE id=?',(document_id,)).fetchone()[0]
    (module.document_library.root / artifact).write_text('{broken')
    assert client.get(f'/api/documents/{document_id}').json['structured_available'] is False
    assert client.get(f'/api/documents/{document_id}/export/docling').status_code == 404
    assert module.app.test_client().get(f'/api/documents/{document_id}/export/original').status_code == 401
    rejected = client.post(f'/api/documents/{document_id}/rename-file', json={'filename': 'Shelf copy.pdf'})
    assert rejected.status_code == 409
    assert client.get(f'/api/documents/{document_id}').json['original_filename'] == 'Original.pdf'
    assert client.get(f'/api/documents/{document_id}/export/original').data == source
    assert 'Original.pdf' in client.get(f'/api/documents/{document_id}/export/original').headers['Content-Disposition']
    assert client.delete(f'/api/documents/{document_id}',json={'confirm':'wrong'}).status_code == 400
    assert client.delete(f'/api/documents/{document_id}',json={'confirm':detail['title']}).status_code == 200
    assert client.get(f'/api/documents/{document_id}').status_code == 404


def test_rejected_rename_keeps_source_and_job_references(module, monkeypatch):
    monkeypatch.setattr(module.document_library, '_run_conversion', fake_result)
    client = signed_in(module)
    source = pdf_bytes(1)
    job = register(client, 'Stable.pdf', len(source)).json
    transfer(client, job['id'], source)
    wait_job(client, job['id'], 'ready')
    with module.db() as conn:
        original_path = conn.execute('SELECT source_path FROM documents WHERE id=?', (job['document_id'],)).fetchone()[0]
    response = client.post(f'/api/documents/{job["document_id"]}/rename-file', json={'filename': 'Moved.pdf'})
    assert response.status_code == 409
    assert (module.document_library.root / original_path).read_bytes() == source
    with module.db() as conn:
        assert conn.execute('SELECT source_path FROM documents WHERE id=?', (job['document_id'],)).fetchone()[0] == original_path
        assert conn.execute('SELECT source_path FROM import_jobs WHERE id=?', (job['id'],)).fetchone()[0] == original_path


def test_processing_cancel_survives_restart_without_card_or_temp(module, monkeypatch):
    client=signed_in(module); source=pdf_bytes(1)
    started=threading.Event(); release=threading.Event()
    def slow_conversion(path,filename,staging):
        started.set(); assert release.wait(5)
        return fake_result(path,filename,staging)
    monkeypatch.setattr(module.document_library,'_run_conversion',slow_conversion)
    job=register(client,'Slow.pdf',len(source)).json
    assert transfer(client,job['id'],source).status_code==202
    assert started.wait(5)
    assert client.post(f'/api/imports/{job["id"]}/cancel').status_code==200
    release.set()
    for _ in range(100):
        if not list((module.document_library.root/'staging').glob(job['id']+'-*')):
            break
        time.sleep(.02)
    assert not list((module.document_library.root/'staging').glob(job['id']+'-*'))
    assert not list((module.document_library.root/'sources'/job['document_id']).glob('*'))
    assert client.get(f'/api/documents/{job["document_id"]}').status_code==404
    reloaded=importlib.reload(module)
    new_client=signed_in(reloaded)
    with reloaded.db() as conn:
        row=conn.execute('SELECT state,error FROM import_jobs WHERE id=?',(job['id'],)).fetchone()
    assert tuple(row)==('failed','Cancelled by user')
    assert new_client.get(f'/api/documents/{job["document_id"]}').status_code==404


def test_restart_rejects_valid_partial_prefix_and_cleans_cancelled_leftover(module):
    client=signed_in(module)
    short=pdf_bytes(1)
    expected=len(short)+100
    job=register(client,'Partial.pdf',expected).json
    source=module.document_library.root/'sources'/job['document_id']/(job['document_id']+'.source')
    source.write_bytes(short)
    with module.db() as conn:
        conn.execute('UPDATE import_jobs SET bytes_received=? WHERE id=?',(len(short),job['id']))
    no_size_id, no_size_doc, no_size_stored=module.document_library.files.register('No size.pdf')
    no_size_path=module.document_library.root/no_size_stored
    no_size_path.write_bytes(short)
    cancelled=register(client,'Cancelled leftover.pdf',len(short)).json
    leftover=module.document_library.root/'sources'/cancelled['document_id']/(cancelled['document_id']+'.source')
    leftover.write_bytes(short)
    with module.db() as conn:
        conn.execute("UPDATE import_jobs SET state='failed',cancel_requested=1,error='Cancelled by user' WHERE id=?",(cancelled['id'],))
    reloaded=importlib.reload(module)
    with reloaded.db() as conn:
        partial=conn.execute('SELECT state,error FROM import_jobs WHERE id=?',(job['id'],)).fetchone()
        no_size=conn.execute('SELECT state,error FROM import_jobs WHERE id=?',(no_size_id,)).fetchone()
        canceled_row=conn.execute('SELECT state,error FROM import_jobs WHERE id=?',(cancelled['id'],)).fetchone()
    assert tuple(partial)==('failed','Transfer interrupted by restart')
    assert tuple(no_size)==('failed','Transfer interrupted by restart')
    assert tuple(canceled_row)==('failed','Cancelled by user')
    assert not source.exists() and not no_size_path.exists() and not leftover.exists()
    assert signed_in(reloaded).get('/api/documents').json['library_total']==0


def test_bulk_stale_cleanup_retry_and_path_boundary(module, monkeypatch, tmp_path):
    monkeypatch.setattr(module.document_library,'_run_conversion',fake_result)
    client=signed_in(module); source=pdf_bytes(1)
    ids=[]
    for name in ('One.pdf','Two.pdf'):
        job=register(client,name,len(source)).json
        transfer(client,job['id'],source); wait_job(client,job['id'],'ready'); ids.append(job['document_id'])
    preview=client.get('/api/library/clear/preview').json
    assert preview['document_count']==2 and preview['file_count']>=2
    job=register(client,'Three.pdf',len(source)).json
    transfer(client,job['id'],source); wait_job(client,job['id'],'ready')
    assert client.post('/api/library/clear',json={'token':preview['token']}).status_code==409
    with module.db() as conn:
        stored=conn.execute('SELECT source_path FROM documents WHERE id=?',(ids[0],)).fetchone()[0]
    target=module.document_library.safe_path(stored)
    real_unlink=Path.unlink
    def fail_unlink(path,*args,**kwargs):
        if path==target:
            raise OSError('injected cleanup failure')
        return real_unlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',fail_unlink)
    title=client.get(f'/api/documents/{ids[0]}').json['title']
    failed=client.delete(f'/api/documents/{ids[0]}',json={'confirm':title})
    assert failed.status_code==500 and ids[0] in failed.json['remaining_document_ids']
    monkeypatch.setattr(Path,'unlink',real_unlink)
    assert client.post('/api/library/cleanup/retry').status_code==200
    assert client.get(f'/api/documents/{ids[1]}').status_code==200
    external=tmp_path/'external-secret'; external.write_text('secret')
    with module.db() as conn:
        conn.execute('UPDATE documents SET source_path=? WHERE id=?',(str(external),ids[1]))
    title=client.get(f'/api/documents/{ids[1]}').json['title']
    failed=client.delete(f'/api/documents/{ids[1]}',json={'confirm':title})
    assert failed.status_code==500 and external.read_text()=='secret'


def test_selected_bulk_originals_and_delete_report_each_result(module, monkeypatch):
    monkeypatch.setattr(module.document_library, '_run_conversion', fake_result)
    admin = signed_in(module)
    source = pdf_bytes(1)
    ids = []
    for _ in range(2):
        job = register(admin, 'Same.pdf', len(source)).json
        transfer(admin, job['id'], source)
        wait_job(admin, job['id'], 'ready')
        ids.append(job['document_id'])

    response = admin.post('/api/documents/bulk/export/original', json={'ids': ids})
    assert response.status_code == 200
    assert response.headers['X-Tomeshed-Bulk-Included'] == '2'
    assert admin.post('/api/documents/bulk/export/original', json={'ids': ids * 2}).status_code == 400
    assert admin.post('/api/documents/bulk/delete', json={'ids': [], 'confirm_count': 0}).status_code == 400
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        names = [item['filename'] for item in manifest['included']]
        assert len(set(names)) == 2 and all(name.endswith('.pdf') for name in names)
        assert manifest['failures'] == []
        assert all(archive.read(name) == source for name in names)

    missing_ids = [f'missing_{index:03d}' for index in range(200)]
    response = admin.post('/api/documents/bulk/export/original', json={'ids': missing_ids})
    assert response.status_code == 200
    assert response.headers['X-Tomeshed-Bulk-Failure-Count'] == '200'
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['failures'] == [{'id': document_id, 'reason': 'unavailable'} for document_id in missing_ids]

    with module.db() as conn:
        missing_path = module.document_library.root / conn.execute(
            'SELECT source_path FROM documents WHERE id=?', (ids[1],)).fetchone()[0]
    missing_path.unlink()
    response = admin.post('/api/documents/bulk/export/original', json={'ids': ids})
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert [item['id'] for item in manifest['included']] == ids[:1]
        assert manifest['failures'] == [{'id': ids[1], 'reason': 'source_unavailable'}]

    assert admin.post('/api/users', json={
        'username': 'reader', 'name': 'Reader', 'password': 'reader-password', 'role': 'normal'}).status_code == 201
    with module.db() as conn:
        conn.execute("UPDATE documents SET visibility='private' WHERE id=?", (ids[1],))
    reader = module.app.test_client()
    assert reader.post('/login', data={'username': 'reader', 'password': 'reader-password'}).status_code == 302
    status = reader.post('/api/documents/bulk/status', json={'ids': ids}).json
    assert status == {'accessible_ids': ids[:1], 'unavailable_ids': ids[1:]}
    response = reader.post('/api/documents/bulk/export/original', json={'ids': ids})
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert [item['id'] for item in manifest['included']] == ids[:1]
        assert manifest['failures'] == [{'id': ids[1], 'reason': 'unavailable'}]
    denied = reader.post('/api/documents/bulk/delete', json={'ids': ids, 'confirm_count': 2})
    assert denied.status_code == 207
    assert denied.json['removed'] == []
    assert {item['id'] for item in denied.json['failures']} == set(ids)
    assert denied.json['failures'] == [
        {'id': ids[0], 'reason': 'not_manageable'}, {'id': ids[1], 'reason': 'unavailable'}]
    assert denied.json['remaining_document_ids'] == ids[:1]
    own_job = register(reader, 'Own.pdf', len(source)).json
    transfer(reader, own_job['id'], source)
    wait_job(reader, own_job['id'], 'ready')
    own_id = own_job['document_id']
    assert reader.post('/api/documents/bulk/delete', json={'ids': [own_id], 'confirm_count': 1}).json['removed'] == [own_id]
    assert admin.post('/api/documents/bulk/delete', json={'ids': ids, 'confirm_count': 1}).status_code == 400
    assert admin.post('/api/documents/bulk/delete', json={'ids': ids[:1], 'confirm_count': True}).status_code == 400

    with module.db() as conn:
        blocked_path = module.document_library.root / conn.execute(
            'SELECT source_path FROM documents WHERE id=?', (ids[0],)).fetchone()[0]
    real_unlink = Path.unlink
    def block_first(path, *args, **kwargs):
        if path == blocked_path:
            raise OSError('injected cleanup failure')
        return real_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', block_first)
    result = admin.post('/api/documents/bulk/delete', json={'ids': ids, 'confirm_count': 2})
    assert result.status_code == 207
    assert result.json['removed'] == ids[1:]
    assert result.json['remaining_document_ids'] == ids[:1]
    assert result.json['failures'] == [{'id': ids[0], 'reason': 'cleanup_failed'}]
    monkeypatch.setattr(Path, 'unlink', real_unlink)
    assert admin.get(f'/api/documents/{ids[0]}').status_code == 200
    assert admin.get(f'/api/documents/{ids[1]}').status_code == 404


def test_url_validation_policy_pin_and_redaction(module, monkeypatch):
    client=signed_in(module)
    before=len(client.get('/api/imports').json['jobs'])
    for value in ('file:///etc/passwd','ftp://example.com/a.pdf','http://u:p@example.com/a.pdf','http://bad host/a.pdf',''):
        assert client.post('/api/imports/url',json={'url':value}).status_code==400
    assert len(client.get('/api/imports').json['jobs'])==before
    from file_workflows import display_url
    assert display_url('https://example.com/a.pdf?token=secret&x=2#fragment')=='https://example.com/a.pdf?token=REDACTED&x=REDACTED'
    files=module.document_library.files
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(socket.AF_INET,socket.SOCK_STREAM,0,'',('127.0.0.1',80))])
    with pytest.raises(ValueError,match='not public'):
        files.checked_addresses('example.com',80)
    files.allowed_cidrs=[__import__('ipaddress').ip_network('127.0.0.0/8')]
    assert files.checked_addresses('example.com',80)=='127.0.0.1'


def test_watcher_settle_dedupe_failure_and_receipt(tmp_path, monkeypatch, caplog):
    inbox=tmp_path/'inbox'; inbox.mkdir()
    monkeypatch.setenv('TOMESHED_DB',str(tmp_path/'library.db'))
    monkeypatch.setenv('TOMESHED_LIBRARY_DIR',str(tmp_path/'library'))
    monkeypatch.setenv('TOMESHED_INGEST_DIR',str(inbox))
    monkeypatch.setenv('TOMESHED_INGEST_SCAN_SECONDS','100')
    monkeypatch.setenv('TOMESHED_INGEST_SETTLE_SECONDS','1')
    import tomeshed
    current=importlib.reload(tomeshed); current.app.config.update(TESTING=True)
    watcher=current.document_library.files
    watcher.stop_event.set(); watcher.watcher_thread.join(timeout=5); watcher.candidates.clear()
    client=signed_in(current)
    source=pdf_bytes(1)
    (inbox/'hidden.tmp').write_bytes(source)
    (inbox/'.hidden.pdf').write_bytes(source)
    (inbox/'folder.pdf').mkdir()
    (inbox/'link.pdf').symlink_to(inbox/'hidden.tmp')
    path=inbox/'Watched.pdf'; path.write_bytes(source)
    watcher.scan_once(0); watcher.scan_once(.5)
    assert not client.get('/api/imports').json['jobs']
    started=threading.Event(); release=threading.Event()
    def slow_convert(source,filename,staging):
        started.set(); assert release.wait(5)
        return fake_result(source,filename,staging)
    monkeypatch.setattr(current.document_library,'_run_conversion',slow_convert)
    watcher.scan_once(1.1)
    assert started.wait(5)
    for tick in (2.2,3.3,4.4): watcher.scan_once(tick)
    assert len(client.get('/api/imports').json['jobs'])==1
    release.set()
    job=client.get('/api/imports').json['jobs'][0]
    wait_job(client,job['id'],'ready')
    assert path.read_bytes()==source
    with current.db() as conn:
        stored = conn.execute('SELECT source_path FROM documents WHERE id=?', (job['document_id'],)).fetchone()[0]
        assert Path(stored).name == job['document_id'] + '.source'
        assert (watcher.root / stored).read_bytes() == source
        assert conn.execute('SELECT original_filename FROM documents WHERE id=?', (job['document_id'],)).fetchone()[0] == 'Watched.pdf'
        assert conn.execute('SELECT source_path FROM import_jobs WHERE id=?', (job['id'],)).fetchone()[0] == stored
        assert conn.execute('SELECT COUNT(*) FROM ingest_receipts').fetchone()[0]==1
    watcher.scan_once(6)
    assert len(client.get('/api/imports').json['jobs'])==1
    title=client.get(f'/api/documents/{job["document_id"]}').json['title']
    assert client.delete(f'/api/documents/{job["document_id"]}',json={'confirm':title}).status_code==200
    watcher.scan_once(7)
    assert len(client.get('/api/imports').json['jobs'])==0
    restarted=importlib.reload(tomeshed)
    watcher=restarted.document_library.files
    watcher.stop_event.set(); watcher.watcher_thread.join(timeout=5); watcher.candidates.clear()
    after_restart=signed_in(restarted)
    watcher.scan_once(8); watcher.scan_once(9.2); watcher.scan_once(10.4)
    assert len(after_restart.get('/api/imports').json['jobs'])==0
    assert after_restart.get('/api/documents').json['library_total']==0
    path.unlink(); watcher.scan_once(11)
    with restarted.db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM ingest_receipts').fetchone()[0]==0
    bad=inbox/'Bad.pdf'; bad.write_bytes(b'invalid')
    watcher.scan_once(12); watcher.scan_once(12.5); watcher.scan_once(13.1); watcher.scan_once(14)
    assert bad.read_bytes()==b'invalid'
    assert 'Bad.pdf' in caplog.text
    assert caplog.text.count('Bad.pdf')==1


def test_url_controlled_http_redirect_size_timeout_and_pinned_address(module, monkeypatch):
    import http.server
    from ipaddress import ip_network
    source = pdf_bytes(1)
    from test_documents import epub_bytes
    epub = epub_bytes()
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/epub.pdf'):
                self.send_response(200); self.end_headers(); self.wfile.write(epub); return
            if self.path.startswith('/redirect-private'):
                self.send_response(302); self.send_header('Location','http://169.254.169.254/private.pdf'); self.end_headers(); return
            if self.path.startswith('/redirect-loop'):
                self.send_response(302); self.send_header('Location','/redirect-loop'); self.end_headers(); return
            if self.path.startswith('/oversize'):
                self.send_response(200); self.send_header('Content-Length','1000000'); self.end_headers(); return
            if self.path.startswith('/slow'):
                self.send_response(200); self.end_headers(); time.sleep(.3)
                try: self.wfile.write(source)
                except BrokenPipeError: pass
                return
            self.send_response(200); self.send_header('Content-Type','application/pdf'); self.end_headers(); self.wfile.write(source)
        def log_message(self,*args): pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        files=module.document_library.files
        files.allowed_cidrs=[ip_network('127.0.0.0/8')]
        monkeypatch.setattr(module.document_library,'_run_conversion',valid_result)
        client=signed_in(module)
        base=f'http://127.0.0.1:{server.server_port}'
        accepted=client.post('/api/imports/url',json={'url':base+'/download?secret=abc#hidden'})
        assert accepted.status_code==202
        ready=wait_job(client,accepted.json['id'],'ready')
        detail=client.get(f'/api/documents/{ready["document_id"]}').json
        assert detail['source_type']=='pdf' and detail['source_url']==base+'/download?secret=REDACTED'
        assert client.get(f'/api/documents/{ready["document_id"]}/export/original').data==source
        original_lookup=socket.getaddrinfo
        lookups=[]
        def changing_dns(host,port,*args,**kwargs):
            lookups.append(host)
            if host=='book.example':
                return [(socket.AF_INET,socket.SOCK_STREAM,0,'',('127.0.0.1',port))] if lookups.count(host)==1 else [(socket.AF_INET,socket.SOCK_STREAM,0,'',('203.0.113.9',port))]
            return original_lookup(host,port,*args,**kwargs)
        monkeypatch.setattr(socket,'getaddrinfo',changing_dns)
        pinned=client.post('/api/imports/url',json={'url':f'http://book.example:{server.server_port}/download'})
        assert pinned.status_code==202
        wait_job(client,pinned.json['id'],'ready')
        assert lookups.count('book.example')==1 and '127.0.0.1' in lookups
        epub_job = client.post('/api/imports/url', json={'url': base + '/epub.pdf'}).json
        wait_job(client, epub_job['id'], 'ready')
        with module.db() as conn:
            epub_row = conn.execute('SELECT original_filename,source_path FROM documents WHERE id=?', (epub_job['document_id'],)).fetchone()
            assert epub_row['original_filename'] == 'epub.epub'
            assert Path(epub_row['source_path']).name == epub_job['document_id'] + '.source'
            assert conn.execute('SELECT source_path FROM import_jobs WHERE id=?', (epub_job['id'],)).fetchone()[0] == epub_row['source_path']
        assert client.get(f'/api/documents/{epub_job["document_id"]}/export/original').data == epub
        module.app.config['MAX_UPLOAD_BYTES']=len(source)+1
        for route,reason in (('/redirect-private','not public'),('/redirect-loop','five redirects'),('/oversize','size limit')):
            result=client.post('/api/imports/url',json={'url':base+route})
            assert result.status_code==202
            failed=wait_job(client,result.json['id'],'failed')
            assert reason in failed['error']
            assert not list((files.root/'sources'/result.json['document_id']).glob('*'))
        files.total_timeout=.1
        result=client.post('/api/imports/url',json={'url':base+'/slow'})
        failed=wait_job(client,result.json['id'],'failed')
        assert 'timed out' in failed['error'] or 'timeout' in failed['error']
        assert client.get('/api/documents').json['library_total']==3
    finally:
        server.shutdown(); server.server_close()


def test_watcher_source_change_during_validation_restarts_settle(tmp_path, monkeypatch):
    inbox=tmp_path/'inbox'; inbox.mkdir()
    monkeypatch.setenv('TOMESHED_DB',str(tmp_path/'library.db'))
    monkeypatch.setenv('TOMESHED_LIBRARY_DIR',str(tmp_path/'library'))
    monkeypatch.setenv('TOMESHED_INGEST_DIR',str(inbox))
    monkeypatch.setenv('TOMESHED_INGEST_SCAN_SECONDS','100')
    monkeypatch.setenv('TOMESHED_INGEST_SETTLE_SECONDS','1')
    import tomeshed
    current=importlib.reload(tomeshed)
    watcher=current.document_library.files; watcher.stop_event.set(); watcher.watcher_thread.join(timeout=5); watcher.candidates.clear()
    source=inbox/'Changing.pdf'; source.write_bytes(pdf_bytes(1))
    watcher.scan_once(0); watcher.scan_once(.5)
    from file_workflows import detect_source as original_detect
    def mutate(path):
        source.write_bytes(pdf_bytes(2))
        return original_detect(path)
    monkeypatch.setattr('file_workflows.detect_source',mutate)
    watcher.scan_once(1.1)
    assert not list((watcher.root/'staging').glob('.watch-*.part'))
    assert not list((watcher.root/'sources').rglob('*.pdf'))
    assert watcher.candidates.get(str(source)) is None
    watcher.scan_once(2); assert watcher.candidates[str(source)]['observations']==1


def test_watcher_source_change_during_copy_removes_unpublished_copy(tmp_path, monkeypatch):
    inbox=tmp_path/'inbox'; inbox.mkdir()
    monkeypatch.setenv('TOMESHED_DB',str(tmp_path/'library.db'))
    monkeypatch.setenv('TOMESHED_LIBRARY_DIR',str(tmp_path/'library'))
    monkeypatch.setenv('TOMESHED_INGEST_DIR',str(inbox))
    monkeypatch.setenv('TOMESHED_INGEST_SCAN_SECONDS','100')
    monkeypatch.setenv('TOMESHED_INGEST_SETTLE_SECONDS','1')
    import tomeshed, file_workflows
    current=importlib.reload(tomeshed)
    watcher=current.document_library.files; watcher.stop_event.set(); watcher.watcher_thread.join(timeout=5); watcher.candidates.clear()
    source=inbox/'Changing.pdf'; source.write_bytes(pdf_bytes(1))
    watcher.scan_once(0); watcher.scan_once(.5)
    original_copy=file_workflows.shutil.copyfileobj
    def mutate_copy(input_file, output_file, length):
        original_copy(input_file,output_file,length)
        source.write_bytes(pdf_bytes(2))
    monkeypatch.setattr(file_workflows.shutil,'copyfileobj',mutate_copy)
    watcher.scan_once(1.1)
    assert not list((watcher.root/'staging').glob('.watch-*.part'))
    assert not list((watcher.root/'sources').rglob('*.pdf'))
    assert watcher.candidates.get(str(source)) is None
    watcher.scan_once(2)
    assert watcher.candidates[str(source)]['observations']==1


def test_watcher_observed_temporary_handoff_imports_after_rename(tmp_path, monkeypatch):
    inbox=tmp_path/'inbox'; inbox.mkdir()
    monkeypatch.setenv('TOMESHED_DB',str(tmp_path/'library.db'))
    monkeypatch.setenv('TOMESHED_LIBRARY_DIR',str(tmp_path/'library'))
    monkeypatch.setenv('TOMESHED_INGEST_DIR',str(inbox))
    monkeypatch.setenv('TOMESHED_INGEST_SCAN_SECONDS','100')
    monkeypatch.setenv('TOMESHED_INGEST_SETTLE_SECONDS','60')
    import tomeshed
    current=importlib.reload(tomeshed)
    watcher=current.document_library.files; watcher.stop_event.set(); watcher.watcher_thread.join(timeout=5); watcher.candidates.clear()
    monkeypatch.setattr(current.document_library,'_run_conversion',fake_result)
    client=signed_in(current)
    temporary=inbox/'.Producer.pdf.part'; temporary.write_bytes(pdf_bytes(1))
    watcher.scan_once(0)
    assert not client.get('/api/imports').json['jobs']
    final=inbox/'Producer.pdf'; temporary.rename(final)
    watcher.scan_once(1)
    jobs=client.get('/api/imports').json['jobs']
    assert len(jobs)==1
    wait_job(client,jobs[0]['id'],'ready')
    assert final.read_bytes()==pdf_bytes(1)


def test_internal_source_names_preserve_user_download_name(module, monkeypatch):
    """Imports keep server names internal and reject the former rename action."""
    import uuid

    monkeypatch.setattr(module.document_library, '_run_conversion', fake_result)
    client = signed_in(module)
    source = pdf_bytes(1)
    job = register(client, 'My original.pdf', len(source)).json
    assert transfer(client, job['id'], source).status_code == 202
    wait_job(client, job['id'], 'ready')
    with module.db() as conn:
        stored = conn.execute('SELECT source_path FROM documents WHERE id=?', (job['document_id'],)).fetchone()[0]
    assert uuid.UUID(Path(stored).stem).hex == Path(stored).stem
    detail = client.get(f'/api/documents/{job["document_id"]}').json
    assert detail['original_filename'] == 'My original.pdf'
    assert 'stored_filename' not in detail
    for endpoint in ('source', 'export/original'):
        response = client.get(f'/api/documents/{job["document_id"]}/{endpoint}')
        assert response.status_code == 200 and response.data == source
        assert 'My original.pdf' in response.headers['Content-Disposition']
    response = client.post(f'/api/documents/{job["document_id"]}/rename-file', json={'filename': 'Changed.pdf'})
    assert response.status_code == 409
    with module.db() as conn:
        assert conn.execute('SELECT source_path FROM documents WHERE id=?', (job['document_id'],)).fetchone()[0] == stored
    assert (module.document_library.root / stored).read_bytes() == source


@pytest.mark.parametrize('kind', ['pdf', 'epub'])
def test_concurrent_originals_use_uuid_names_and_readable_archive_entries(module, monkeypatch, kind):
    from concurrent.futures import ThreadPoolExecutor
    from urllib.parse import unquote
    import uuid
    from test_documents import epub_bytes

    from reader_service import PDFIUM_LOCK

    def locked_conversion(source, filename, staging):
        with PDFIUM_LOCK:
            return fake_result(source, filename, staging)

    monkeypatch.setattr(module.document_library, '_run_conversion', locked_conversion)
    clients = [signed_in(module), signed_in(module)]
    filename = f'Étagère book.{kind}'
    sources = [pdf_bytes(1), pdf_bytes(2)] if kind == 'pdf' else [epub_bytes(2), epub_bytes(3)]
    barrier = threading.Barrier(2)

    def import_one(index):
        barrier.wait(timeout=5)
        job = register(clients[index], filename, len(sources[index])).json
        assert transfer(clients[index], job['id'], sources[index]).status_code == 202
        wait_job(clients[index], job['id'], 'ready')
        return job

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(import_one, range(2)))
    client = clients[0]
    with module.db() as conn:
        paths = [conn.execute('SELECT source_path FROM documents WHERE id=?', (job['document_id'],)).fetchone()[0] for job in jobs]
        assert len(set(paths)) == 2
        for job, path in zip(jobs, paths):
            assert uuid.UUID(Path(path).stem).hex == Path(path).stem
            assert conn.execute('SELECT source_path FROM import_jobs WHERE id=?', (job['id'],)).fetchone()[0] == path
    for job, path, source in zip(jobs, paths, sources):
        document_id = job['document_id']
        assert (module.document_library.root / path).read_bytes() == source
        for endpoint in ('source?download=1', 'export/original'):
            response = client.get(f'/api/documents/{document_id}/{endpoint}')
            assert response.data == source
            assert filename in unquote(response.headers['Content-Disposition'])
            assert Path(path).name not in response.headers['Content-Disposition']
        assert client.get(f'/api/documents/{document_id}/preview').status_code == 200
        assert client.get(f'/api/documents/{document_id}/reader').status_code == 200
        assert client.patch(f'/api/documents/{document_id}/metadata', json={'title': 'Changed title', 'author': 'Changed author'}).status_code == 200
        with module.db() as conn:
            assert conn.execute('SELECT source_path FROM documents WHERE id=?', (document_id,)).fetchone()[0] == path
    response = client.post('/api/documents/bulk/export/original', json={'ids': [job['document_id'] for job in jobs]})
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert archive.namelist() == [filename, f'Étagère book (2).{kind}', 'manifest.json']
        assert archive.read(filename) == sources[0]
        assert archive.read(f'Étagère book (2).{kind}') == sources[1]


def test_legacy_filename_sources_remain_readable_retryable_and_removable(module, monkeypatch):
    monkeypatch.setattr(module.document_library, '_run_conversion', fake_result)
    client = signed_in(module)
    source = pdf_bytes(2)
    job = register(client, 'Original filename.pdf', len(source)).json
    transfer(client, job['id'], source)
    wait_job(client, job['id'], 'ready')
    with module.db() as conn:
        current = conn.execute('SELECT source_path FROM documents WHERE id=?', (job['document_id'],)).fetchone()[0]
        legacy = str(Path(current).with_name('Historically renamed.pdf'))
        (module.document_library.root / current).rename(module.document_library.root / legacy)
        conn.execute("UPDATE documents SET source_path=?,state='ready_with_warning' WHERE id=?", (legacy, job['document_id']))
    reloaded = importlib.reload(module)
    monkeypatch.setattr(reloaded.document_library, '_run_conversion', fake_result)
    client = signed_in(reloaded)
    document_id = job['document_id']
    with reloaded.db() as conn:
        assert conn.execute('SELECT source_path FROM import_jobs WHERE id=?', (job['id'],)).fetchone()[0] == legacy
    for endpoint in ('source?download=1', 'export/original'):
        response = client.get(f'/api/documents/{document_id}/{endpoint}')
        assert response.data == source
        assert 'Original filename.pdf' in response.headers['Content-Disposition']
    assert client.get(f'/api/documents/{document_id}/preview').status_code == 200
    assert client.get(f'/api/documents/{document_id}/reader').status_code == 200
    retry = client.post(f'/api/documents/{document_id}/retry')
    assert retry.status_code == 202
    wait_job(client, retry.json['id'], 'ready')
    with reloaded.db() as conn:
        assert conn.execute('SELECT source_path FROM documents WHERE id=?', (document_id,)).fetchone()[0] == legacy
        assert conn.execute('SELECT source_path FROM import_jobs WHERE id=?', (retry.json['id'],)).fetchone()[0] == legacy
    assert (reloaded.document_library.root / legacy).read_bytes() == source
    title = client.get(f'/api/documents/{document_id}').json['title']
    assert client.delete(f'/api/documents/{document_id}', json={'confirm': title}).status_code == 200
    assert not (reloaded.document_library.root / legacy).exists()


def test_legacy_original_names_are_safe_for_headers_and_archives(module, monkeypatch):
    monkeypatch.setattr(module.document_library, '_run_conversion', fake_result)
    client = signed_in(module)
    source = pdf_bytes(1)
    jobs = []
    for metadata, safe_name in (('../unsafe.pdf', 'unsafe.pdf'), ('C:\\folder\\notes.pdf', 'notes.pdf'), ('line\r\nbad.pdf', 'line__bad.pdf'), ('manifest.json', 'manifest (2).json')):
        job = register(client, 'Safe.pdf', len(source)).json
        transfer(client, job['id'], source)
        wait_job(client, job['id'], 'ready')
        with module.db() as conn:
            conn.execute('UPDATE documents SET original_filename=? WHERE id=?', (metadata, job['document_id']))
        response = client.get(f'/api/documents/{job["document_id"]}/source?download=1')
        assert response.status_code == 200 and response.data == source
        assert '\r' not in response.headers['Content-Disposition'] and '\n' not in response.headers['Content-Disposition']
        jobs.append((job['document_id'], safe_name))
    response = client.post('/api/documents/bulk/export/original', json={'ids': [document_id for document_id, _ in jobs]})
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert archive.namelist() == [name for _, name in jobs] + ['manifest.json']
        assert all(archive.read(name) == source for _, name in jobs)
    assert module.app.test_client().post(f'/api/documents/{jobs[0][0]}/rename-file', json={'filename': 'Changed.pdf'}).status_code == 401
