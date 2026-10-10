"""Bookshelf order, shares, reader bookmarks, and document visibility checks."""

import importlib

from test_documents import fake_result, json_bytes, module, pdf_bytes, signed_in, upload, wait_job
from test_reader import add_document, epub_fixture


def user(module, admin, username, role='normal'):
    response=admin.post('/api/users',json={'username':username,'password':username+'-password','role':role})
    assert response.status_code==201, response.json
    client=module.app.test_client()
    assert client.post('/login',data={'username':username,'password':username+'-password'}).status_code==302
    return client,response.json['id']


def create(client,name,members=None):
    response=client.post('/api/bookshelves',json={'name':name,'members':members or []})
    assert response.status_code==201,response.json
    return response.json


def detail(client,shelf):
    return client.get('/api/bookshelves/'+shelf).json


def test_duplicate_names_order_validation_and_restart(module):
    admin=signed_in(module)
    first=create(admin,'  Same  ')
    second=create(admin,'Same')
    assert first['name']==second['name']=='Same'
    for invalid in ('',' ','A'*121,'bad\nname',None):
        assert admin.post('/api/bookshelves',json={'name':invalid}).status_code==400
    ready=add_document(module,pdf_bytes(1),'pdf','Ready')
    assert admin.post('/api/bookshelves',json={'name':'Missing member','members':['missing']}).status_code==404
    assert admin.post('/api/bookshelves',json={'name':'Duplicate member','members':[ready,ready]}).status_code==400
    listing=admin.get('/api/bookshelves').json
    assert [item['id'] for item in listing['owned']]==[first['id'],second['id']]
    assert listing['owned'][0]['continue_document_id'] is None
    changed=admin.put('/api/bookshelves/order',json={'expected_revision':listing['order_revision'],'ids':[second['id'],first['id']]})
    assert changed.status_code==200
    assert admin.put('/api/bookshelves/order',json={'expected_revision':listing['order_revision'],'ids':[first['id'],second['id']]}).status_code==409
    reloaded=importlib.reload(module)
    again=signed_in(reloaded)
    assert [item['id'] for item in again.get('/api/bookshelves').json['owned']]==[second['id'],first['id']]


def test_members_atomic_conflicts_bookmark_and_deletion(module):
    admin=signed_in(module)
    first=add_document(module,pdf_bytes(2),'pdf','First')
    second=add_document(module,pdf_bytes(2),'pdf','Second')
    one=create(admin,'One',[first])
    two=create(admin,'Two',[first])
    assert admin.post(f'/api/bookshelves/{one["id"]}/members',json={'document_id':first}).json['count']==1
    assert admin.post(f'/api/bookshelves/{one["id"]}/members',json={'document_id':second}).json['count']==2
    before=detail(admin,one['id'])
    assert admin.put(f'/api/bookshelves/{one["id"]}',json={'name':'Bad','members':[first,first],'expected_revision':before['revision']}).status_code==400
    edited=admin.put(f'/api/bookshelves/{one["id"]}',json={'name':'Renamed','members':[second,first],'expected_revision':before['revision']})
    assert edited.status_code==200 and [item['id'] for item in edited.json['members']]==[second,first]
    stale=admin.put(f'/api/bookshelves/{one["id"]}',json={'name':'Stale','members':[first],'expected_revision':before['revision']})
    assert stale.status_code==409 and stale.json['current']['name']=='Renamed'
    assert [item['id'] for item in detail(admin,one['id'])['members']]==[second,first]
    assert admin.post(f'/api/documents/{first}/reader-open',json={'bookshelf_id':one['id']}).status_code==200
    assert detail(admin,one['id'])['bookmark_document_id']==first
    assert detail(admin,two['id'])['bookmark_document_id'] is None
    admin.put(f'/api/documents/{first}/progress',json={'locator':{'page':2,'offset':0},'percent':50})
    assert admin.post(f'/api/documents/{second}/reader-open').status_code==200
    assert detail(admin,one['id'])['bookmark_document_id']==first
    assert admin.put(f'/api/bookshelves/{one["id"]}',json={'name':'Renamed','members':[second],'expected_revision':edited.json['revision']}).status_code==200
    assert admin.post(f'/api/bookshelves/{one["id"]}/continue').json['document_id']==second
    assert admin.delete(f'/api/bookshelves/{one["id"]}',json={'confirm':'Renamed'}).status_code==200
    assert admin.get(f'/api/documents/{first}').status_code==200
    assert admin.get(f'/api/documents/{first}/progress').json['position']['locator']['page']==2


def test_share_authorization_filtering_and_revocation(module):
    admin=signed_in(module)
    owner,owner_id=user(module,admin,'owner')
    recipient,recipient_id=user(module,admin,'recipient')
    outsider,_=user(module,admin,'outsider')
    first=add_document(module,pdf_bytes(1),'pdf','Visible')
    hidden=add_document(module,pdf_bytes(1),'pdf','Hidden')
    with module.db() as conn:
        conn.execute('UPDATE documents SET owner_user_id=?,visibility=? WHERE id=?',(owner_id,'private',hidden))
    shelf=create(owner,'Mixed',[first,hidden])
    path=f'/api/bookshelves/{shelf["id"]}'
    assert recipient.get(path).status_code==404
    assert outsider.get(path).status_code==404
    assert admin.get(path).status_code==404
    assert owner.post(path+'/shares',json={'username':'missing'}).status_code==400
    assert owner.post(path+'/shares',json={'username':'owner'}).status_code==400
    assert owner.post(path+'/shares',json={'username':'Recipient'}).status_code==400
    assert owner.post(path+'/shares',json={'username':'recipient'}).status_code==200
    assert outsider.put('/api/bookshelves/order',json={'expected_revision':0,'ids':['missing']}).status_code==404
    assert outsider.put('/api/bookshelves/order',json={'expected_revision':0,'ids':[shelf['id']]}).status_code==404
    own_recipient=create(recipient,'Recipient shelf')
    assert recipient.post(f'/api/bookshelves/{own_recipient["id"]}/members',json={'document_id':'missing'}).status_code==404
    assert recipient.post(f'/api/bookshelves/{own_recipient["id"]}/members',json={'document_id':hidden}).status_code==404
    assert recipient.post('/api/bookshelves',json={'name':'Hidden member','members':[hidden]}).status_code==404
    observed=recipient.get(path).json
    assert observed['count']==1 and [item['id'] for item in observed['members']]==[first]
    assert observed['members'][0]['position']==0 and observed['covers']==[]
    assert hidden not in str(observed)
    assert recipient.put(path,json={'name':'Wrong','members':[],'expected_revision':1}).status_code==403
    assert recipient.post(path+'/members',json={'document_id':first}).status_code==403
    assert recipient.delete(path,json={'confirm':'Mixed'}).status_code==403
    assert recipient.post(path+'/shares',json={'username':'outsider'}).status_code==403
    assert recipient.put('/api/bookshelves/order',json={'expected_revision':0,'ids':[shelf['id']]}).status_code==403
    assert recipient.post(f'/api/documents/{first}/reader-open',json={'bookshelf_id':shelf['id']}).status_code==200
    assert recipient.get(path).json['bookmark_document_id']==first
    assert owner.get(path).json['bookmark_document_id'] is None
    assert owner.delete(path+f'/shares/{recipient_id}').status_code==200
    assert recipient.get(path).status_code==404
    assert recipient.post(path+'/continue').status_code==404
    assert recipient.post(f'/api/documents/{first}/reader-open',json={'bookshelf_id':shelf['id']}).status_code==404
    assert admin.patch(f'/api/users/{recipient_id}',json={'suspended':True}).status_code==200
    assert owner.post(path+'/shares',json={'username':'recipient'}).status_code==400
    assert admin.patch(f'/api/documents/{first}/visibility',json={'visibility':'private'}).status_code==200
    assert owner.post(path+'/members',json={'document_id':first}).status_code==404
    unavailable=owner.get(path).json['editor_members'][0]
    assert unavailable['unavailable'] is True and unavailable['document'] is None
    assert 'Visible' not in str(owner.get(path).json)


def test_url_watch_and_legacy_ownership(module,monkeypatch,tmp_path):
    admin=signed_in(module)
    owner,owner_id=user(module,admin,'owner')
    monkeypatch.setattr(module.document_library.files,'fetch_url',lambda job_id: None)
    monkeypatch.setattr(module.document_library,'_run_conversion',fake_result)
    queued=owner.post('/api/imports/url',json={'url':'https://example.com/download?id=42'})
    assert queued.status_code==202
    with module.db() as conn:
        url_row=conn.execute('SELECT owner_user_id,source_path FROM import_jobs WHERE id=?',(queued.json['id'],)).fetchone()
        assert url_row['owner_user_id']==owner_id
        (module.document_library.root/url_row['source_path']).write_bytes(pdf_bytes(1))
        conn.execute('UPDATE import_jobs SET transfer_complete=1 WHERE id=?',(queued.json['id'],))
    module.document_library._process_job(queued.json['id'])
    assert wait_job(owner,queued.json['id'],'ready')['state']=='ready'
    with module.db() as conn:
        assert conn.execute('SELECT owner_user_id FROM documents WHERE id=?',(queued.json['document_id'],)).fetchone()[0]==owner_id
    watched=module.document_library.files.register('Inbox.pdf',origin='watch',watch_path=str(tmp_path/'Inbox.pdf'),watch_signature=[1,2,3])
    with module.db() as conn:
        watch_row=conn.execute('SELECT owner_user_id,source_path FROM import_jobs WHERE id=?',(watched[0],)).fetchone()
        assert watch_row['owner_user_id'] is None
        (module.document_library.root/watch_row['source_path']).write_bytes(pdf_bytes(1))
        conn.execute('UPDATE import_jobs SET transfer_complete=1 WHERE id=?',(watched[0],))
    module.document_library._process_job(watched[0])
    assert wait_job(admin,watched[0],'ready')['state']=='ready'
    with module.db() as conn:
        assert conn.execute('SELECT owner_user_id FROM documents WHERE id=?',(watched[1],)).fetchone()[0] is None
    import sqlite3
    legacy_db=tmp_path/'legacy.sqlite'
    with sqlite3.connect(legacy_db) as conn:
        conn.execute('''CREATE TABLE documents(id TEXT PRIMARY KEY,original_filename TEXT NOT NULL,source_path TEXT NOT NULL,
            source_type TEXT NOT NULL,title TEXT NOT NULL,author TEXT NOT NULL,byte_size INTEGER NOT NULL,
            search_key TEXT NOT NULL,text_content TEXT NOT NULL DEFAULT '',page_count INTEGER,count_kind TEXT NOT NULL,
            thumbnail_path TEXT,artifact_path TEXT,state TEXT NOT NULL,error TEXT,created_at REAL NOT NULL)''')
        conn.execute('''INSERT INTO documents(id,original_filename,source_path,source_type,title,author,byte_size,search_key,
            count_kind,state,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            ('legacy','Legacy.pdf','sources/legacy.source','pdf','Legacy','Unknown',10,'legacy','exact','ready',1))
    monkeypatch.setenv('TOMESHED_DB',str(legacy_db))
    monkeypatch.setenv('TOMESHED_LIBRARY_DIR',str(tmp_path/'legacy-storage'))
    migrated=importlib.reload(module)
    with migrated.db() as conn:
        assert tuple(conn.execute("SELECT owner_user_id,visibility FROM documents WHERE id='legacy'").fetchone())==(None,'public')


def test_privacy_routes_catalog_tags_jobs_and_owner_transfer(module,monkeypatch):
    monkeypatch.setattr(module.document_library,'_run_conversion',fake_result)
    admin=signed_in(module)
    owner,owner_id=user(module,admin,'owner')
    other,_=user(module,admin,'other')
    pending=upload(owner,pdf_bytes(1),'Owner.pdf')
    assert pending.status_code==202
    wait_job(owner,pending.json['id'],'ready')
    doc=pending.json['document_id']
    with module.db() as conn:
        assert tuple(conn.execute('SELECT owner_user_id,visibility FROM documents WHERE id=?',(doc,)).fetchone())==(owner_id,'public')
        assert conn.execute('SELECT owner_user_id FROM import_jobs WHERE id=?',(pending.json['id'],)).fetchone()[0]==owner_id
    assert owner.post(f'/api/documents/{doc}/tags',json={'tag':'Secret'}).status_code==200
    assert other.patch(f'/api/documents/{doc}/visibility',json={'visibility':'private'}).status_code==403
    events=other.get('/api/events',buffered=False)
    assert b'event: ready' in next(events.response)
    assert owner.patch(f'/api/documents/{doc}/visibility',json={'visibility':'private'}).status_code==200
    change=next(events.response)
    assert b'event: change' in change and doc.encode() not in change and b'data: {}' in change
    events.close()
    assert other.get('/api/documents?q=Owner').json['total']==0
    assert other.get('/api/documents').json['library_total']==0
    assert other.get('/api/tags').json['tags']==[]
    assert other.get('/api/imports').json['jobs']==[]
    base=f'/api/documents/{doc}'
    for path in (base,f'/documents/{doc}',base+'/source',base+'/thumbnail',base+'/reader',base+'/reader/page/1',base+'/reader/resource?path=x.png',base+'/preview',base+'/preview/location/0',base+'/preview/page/1',base+'/preview/resource?path=x.png',base+'/progress',base+'/export/original',base+'/export/docling'):
        assert other.get(path).status_code==404,path
    for path in (base+'/retry',base+'/reader-open',base+'/finish',base+'/start-over'):
        assert other.post(path).status_code==404,path
    assert other.post(f'/api/imports/{pending.json["id"]}/cancel').status_code==404
    assert other.post(f'/api/imports/{pending.json["id"]}/retry').status_code==404
    assert other.put(f'/api/imports/{pending.json["id"]}/file',data=b'x').status_code==404
    assert admin.get(base).status_code==200
    assert admin.delete(f'/api/users/{owner_id}').status_code==200
    with module.db() as conn:
        row=conn.execute('SELECT owner_user_id,visibility FROM documents WHERE id=?',(doc,)).fetchone()
        assert tuple(row)==(None,'private')
    assert other.get(base).status_code==404
    assert admin.patch(base+'/visibility',json={'visibility':'public'}).status_code==200
    assert other.get(base).status_code==200


def test_document_removal_compacts_members_and_bookmarks(module):
    admin=signed_in(module)
    ids=[add_document(module,pdf_bytes(1),'pdf',f'Volume {index}') for index in range(3)]
    one=create(admin,'One',ids)
    two=create(admin,'Two',[ids[1],ids[2]])
    assert admin.post(f'/api/documents/{ids[1]}/reader-open',json={'bookshelf_id':one['id']}).status_code==200
    assert admin.post(f'/api/documents/{ids[1]}/reader-open',json={'bookshelf_id':two['id']}).status_code==200
    assert admin.delete(f'/api/documents/{ids[1]}',json={'confirm':'Volume 1'}).status_code==200
    assert [item['id'] for item in detail(admin,one['id'])['members']]==[ids[0],ids[2]]
    assert [item['position'] for item in detail(admin,one['id'])['members']]==[0,1]
    assert detail(admin,one['id'])['bookmark_document_id'] is None
    assert detail(admin,two['id'])['bookmark_document_id'] is None
    with module.db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM bookshelf_bookmarks WHERE document_id=?',(ids[1],)).fetchone()[0]==0


def test_resume_fallback_missing_and_private_source(module):
    admin=signed_in(module)
    owner,owner_id=user(module,admin,'owner')
    recipient,_=user(module,admin,'recipient')
    ids=[add_document(module,pdf_bytes(1),'pdf',f'Resume {index}') for index in range(2)]
    shelf=create(owner,'Resume',ids)
    owner.post(f'/api/bookshelves/{shelf["id"]}/shares',json={'username':'recipient'})
    assert recipient.post(f'/api/documents/{ids[1]}/reader-open',json={'bookshelf_id':shelf['id']}).status_code==200
    assert recipient.post(f'/api/bookshelves/{shelf["id"]}/continue').json['document_id']==ids[1]
    with module.db() as conn:
        conn.execute('UPDATE documents SET owner_user_id=?,visibility=? WHERE id=?',(owner_id,'private',ids[1]))
    assert recipient.post(f'/api/bookshelves/{shelf["id"]}/continue').json['document_id']==ids[0]
    assert recipient.get(f'/api/bookshelves/{shelf["id"]}').json['bookmark_document_id'] is None
    (module.document_library.root/f'sources/{ids[0]}.source').unlink()
    assert recipient.post(f'/api/bookshelves/{shelf["id"]}/continue').status_code==409
    assert recipient.get(f'/api/bookshelves/{shelf["id"]}').json['continue_document_id'] is None


def test_owner_editor_uses_opaque_placeholder_after_access_loss(module):
    admin=signed_in(module)
    owner,_=user(module,admin,'owner')
    document_id=add_document(module,pdf_bytes(1),'pdf','Hidden title')
    shelf=create(owner,'Access changes',[document_id])
    assert admin.patch(f'/api/documents/{document_id}/visibility',json={'visibility':'private'}).status_code==200
    shown=detail(owner,shelf['id'])
    assert shown['count']==0 and shown['members']==[] and shown['covers']==[]
    assert len(shown['editor_members'])==1
    placeholder=shown['editor_members'][0]
    assert placeholder['unavailable'] is True and placeholder['document'] is None
    assert document_id not in str(shown) and 'Hidden title' not in str(shown)
    changed=owner.put(f'/api/bookshelves/{shelf["id"]}',json={'name':'Still here','members':[{'member_id':placeholder['member_id']}],
                                                             'expected_revision':shown['revision']})
    assert changed.status_code==200 and changed.json['count']==0
    with module.db() as conn:
        assert conn.execute('SELECT document_id FROM bookshelf_members WHERE bookshelf_id=?',(shelf['id'],)).fetchone()[0]==document_id
