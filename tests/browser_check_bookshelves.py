"""Feature 0007 browser checks for bookshelf editing, sharing, and resume."""

import importlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from test_documents import pdf_bytes
from test_reader import add_document, docling_fixture, epub_fixture

ARTIFACTS=Path('/tmp/tomeshed-feature-0007-browser')
ARTIFACTS.mkdir(exist_ok=True)


def wait_server(base):
    for _ in range(100):
        try:
            with urlopen(base+'/api/health',timeout=.2): return
        except Exception: time.sleep(.1)
    raise AssertionError('Server did not start')


def login(page,base,username,password):
    page.goto(base+'/login')
    page.locator('#username').fill(username)
    page.locator('#password').fill(password)
    page.get_by_role('button',name='Sign in').click()
    page.wait_for_url(base+'/')
    page.wait_for_function("document.querySelector('#documentGrid').children.length > 0")


def open_shelf(page, shelf_selector):
    page.locator(shelf_selector).locator('.bookshelf-card-open').click()
    page.locator('#bookshelfDialogBody').wait_for(state='visible')


def continue_shelf(page, shelf_selector):
    open_shelf(page, shelf_selector)
    page.locator('#bookshelfDialogBody').get_by_role('button', name='Continue reading').click()


def open_member(page,shelf_selector,title):
    open_shelf(page, shelf_selector)
    member=page.locator('.bookshelf-member').filter(has_text=title)
    member.wait_for()
    member.get_by_role('button',name='Open').click()
    page.wait_for_function("document.querySelector('#reader').hidden === false")
    page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Page') || document.querySelector('#readerPosition').textContent.includes('Location')")
    assert title in page.locator('#readerTitle').inner_text()


def saved_position(page,document_id):
    parts=urlsplit(page.url); base=f'{parts.scheme}://{parts.netloc}'
    for _ in range(80):
        value=page.request.get(base+f'/api/documents/{document_id}/progress').json()['position']
        if value: return value
        time.sleep(.1)
    raise AssertionError('Reading position was not saved')


def wait_bookmark(page,base,shelf_id,document_id):
    for _ in range(80):
        value=page.request.get(base+f'/api/bookshelves/{shelf_id}').json()
        if value['bookmark_document_id']==document_id: return
        time.sleep(.1)
    raise AssertionError('Bookshelf bookmark was not saved')


def main():
    checks={}
    with tempfile.TemporaryDirectory() as folder:
        folder=Path(folder)
        os.environ['TOMESHED_DB']=str(folder/'books.db')
        os.environ['TOMESHED_LIBRARY_DIR']=str(folder/'storage')
        os.environ['TOMESHED_CATALOG_PAGE_SIZE']='2'
        import tomeshed
        module=importlib.reload(tomeshed)
        setup=module.app.test_client()
        assert setup.post('/login',data={'username':'admin','password':'secret-password','password_confirmation':'secret-password'}).status_code==302
        owner=setup.post('/api/users',json={'username':'owner','password':'owner-password'}).json
        recipient=setup.post('/api/users',json={'username':'recipient','password':'recipient-password'}).json
        docs=[add_document(module,pdf_bytes(3),'pdf','PDF Book'),
              add_document(module,epub_fixture(text='many words '*400),'epub','EPUB Book'),
              add_document(module,docling_fixture(extra=5),'docling','Docling Book'),
              add_document(module,pdf_bytes(1),'pdf','Extra Book')]
        with module.db() as conn:
            for index,doc in enumerate(docs):
                output=io.BytesIO(); Image.new('RGB',(50,70),('#305947','#5b6996','#ac7c4e','#71558b')[index]).save(output,'PNG')
                stored=f'thumbnails/{doc}.png'; (module.document_library.root/stored).write_bytes(output.getvalue())
                conn.execute('UPDATE documents SET owner_user_id=?,thumbnail_path=? WHERE id=?',(owner['id'],stored,doc))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        env=dict(os.environ,HOST='127.0.0.1',PORT=str(port),PYTHONDONTWRITEBYTECODE='1')
        def start():
            process=subprocess.Popen([sys.executable,'tomeshed.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            wait_server(base)
            return process
        server=start()
        try:
            with sync_playwright() as playwright:
                browser=playwright.chromium.launch(headless=True)
                context=browser.new_context(viewport={'width':1280,'height':850})
                page=context.new_page()
                page_errors=[]; page.on('pageerror',lambda error: page_errors.append(str(error)))
                login(page,base,'owner','owner-password')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 2")
                assert page.locator('.document-card').count()==2
                page.evaluate("""async () => {
                    await fetch('/api/preferences', {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({page_size:'endless'})});
                    catalogPageSize = 'endless'; await loadCatalog();
                }""")
                page.locator('#createBookshelf').click()
                page.locator('#bookshelfName').fill('Reading')
                page.get_by_role('button',name='Save bookshelf').click()
                page.wait_for_function("document.querySelectorAll('#documentGrid .bookshelf-card[data-owned=true]').length === 1")
                assert page.locator('#documentGrid .bookshelf-card[data-owned=true] .bookshelf-actions').count() == 0
                assert page.locator('#bookshelfDialogBody').get_by_role('button',name='Continue reading').is_disabled()
                page.locator('#closeBookshelfDialog').click()
                empty_shelf = page.locator('#documentGrid .bookshelf-card[data-owned=true]')
                assert empty_shelf.locator('h3').inner_text() == 'Reading'
                assert empty_shelf.locator('p').count() == 0
                assert empty_shelf.locator('.bookshelf-cover').count() == 0
                assert empty_shelf.locator('.bookshelf-card-open').get_attribute('aria-label') == 'Open bookshelf Reading, 0 visible documents'
                empty_shelf.locator('.bookshelf-card-open').focus()
                page.keyboard.press('Enter')
                page.locator('#bookshelfDialog').wait_for(state='visible')
                page.locator('#closeBookshelfDialog').click()
                page.set_viewport_size({'width':390,'height':800})
                page.screenshot(path=str(ARTIFACTS/'mixed-grid-390-light.png'),full_page=True)
                page.evaluate("document.documentElement.dataset.theme = 'dark'")
                page.screenshot(path=str(ARTIFACTS/'mixed-grid-390-dark.png'),full_page=True)
                page.evaluate("document.documentElement.dataset.theme = 'light'")
                page.set_viewport_size({'width':1280,'height':850})
                touch_context=browser.new_context(viewport={'width':390,'height':800},has_touch=True,
                                                  is_mobile=True,storage_state=context.storage_state())
                touch_page=touch_context.new_page()
                touch_page.goto(base+'/')
                touch_page.wait_for_function("document.querySelector('#documentGrid .bookshelf-card-open')")
                touch_page.locator('#documentGrid .bookshelf-card-open').tap()
                touch_page.locator('#bookshelfDialog').wait_for(state='visible')
                touch_context.close()
                page.evaluate("() => loadCatalog(true)")
                page.wait_for_function("document.querySelectorAll('.document-card').length >= 3")
                if page.locator('.document-card').count() < 4:
                    page.evaluate("() => loadCatalog(true)")
                page.wait_for_function("document.querySelectorAll('.document-card').length === 4")
                checks['empty_and_grid']='passed'
                page.locator('.document-card').filter(has=page.get_by_role('heading',name='PDF Book')).locator('.document-open').dblclick()
                page.locator('#readerDocumentPanel').get_by_role('button',name='Add to bookshelf').click()
                page.locator('#bookshelfDialogBody').get_by_role('button',name='Reading').click()
                page.locator('#readerClose').click()
                page.wait_for_function("document.querySelector('#documentGrid .bookshelf-card[data-owned=true] .bookshelf-card-open')?.getAttribute('aria-label')?.includes('1 visible document')")
                page.locator('#documentGrid .bookshelf-card').first.locator('.bookshelf-card-open').click()
                page.locator('.bookshelf-member').first.wait_for()
                assert page.locator('.bookshelf-member').count()==1
                assert 'PDF Book' in page.locator('.bookshelf-member').inner_text()
                assert 'in progress' in page.locator('.bookshelf-member').inner_text()
                page.get_by_role('button',name='Edit bookshelf').click()
                page.locator('#bookshelfSearch').fill('EPUB')
                page.get_by_role('button',name='Add EPUB Book').click()
                assert page.locator('.bookshelf-editor-member').count()==2
                page.locator('.bookshelf-editor-member').nth(1).get_by_role('button',name='Move member up').focus()
                page.keyboard.press('Enter')
                assert 'EPUB Book' in page.locator('.bookshelf-editor-member').first.inner_text()
                page.locator('#bookshelfName').fill('Reading shelf')
                page.get_by_role('button',name='Save bookshelf').click()
                page.wait_for_function("document.querySelector('#bookshelfDialogTitle').textContent === 'Reading shelf'")
                assert 'EPUB Book' in page.locator('.bookshelf-member').first.inner_text()
                checks['quick_add_keyboard_atomic_edit']='passed'
                shelf_id=page.locator('#documentGrid .bookshelf-card[data-owned=true]').get_attribute('data-bookshelf-id')
                page.locator('#closeBookshelfDialog').click()
                continue_shelf(page, '#documentGrid .bookshelf-card[data-owned=true]')
                page.wait_for_function("document.querySelector('#reader').hidden === false")
                page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Location') || document.querySelector('#readerPosition').textContent.includes('Page')")
                assert 'EPUB Book' in page.locator('#readerTitle').inner_text()
                page.locator('#readerClose').click()
                checks['owner_continue']='passed'
                page.locator('#documentGrid .bookshelf-card[data-owned=true]').locator('.bookshelf-card-open').click()
                page.get_by_role('button',name='Edit bookshelf').click()
                page.locator('#bookshelfSearch').fill('Docling')
                page.get_by_role('button',name='Add Docling Book').click()
                page.get_by_role('button',name='Save bookshelf').click()
                page.wait_for_function("document.querySelectorAll('.bookshelf-member').length === 3")
                assert page.locator('.bookshelf-member .bookshelf-cover').count()==3
                page.locator('#closeBookshelfDialog').click()
                checks['cover_detail']='passed'
                page.locator('#documentGrid .bookshelf-card[data-owned=true]').locator('.bookshelf-card-open').click()
                page.get_by_role('button',name='Edit bookshelf').click()
                current=page.request.get(base+f'/api/bookshelves/{shelf_id}').json()
                changed=page.request.put(base+f'/api/bookshelves/{shelf_id}',data={'name':'Server edit','members':[item['id'] for item in current['members']],'expected_revision':current['revision']})
                assert changed.status==200
                page.locator('#bookshelfName').fill('Stale edit')
                page.get_by_role('button',name='Save bookshelf').click()
                page.get_by_text('Another session changed this bookshelf').wait_for()
                page.get_by_role('button',name='Load latest version').click()
                page.wait_for_function("document.querySelector('#bookshelfName')?.value === 'Server edit'")
                assert page.locator('#bookshelfName').input_value()=='Server edit'
                page.locator('#bookshelfName').fill('Reading shelf')
                page.get_by_role('button',name='Save bookshelf').click()
                page.wait_for_function("document.querySelector('#bookshelfDialogTitle').textContent === 'Reading shelf'")
                checks['browser_conflict']='passed'
                page.get_by_role('button',name='Edit bookshelf').click()
                page.get_by_role('textbox',name='Exact username').fill('recipient')
                page.get_by_role('button',name='Add recipient').click()
                page.wait_for_function("document.querySelector('.bookshelf-recipients').textContent.includes('recipient')")
                page.locator('#closeBookshelfDialog').click()
                owner_labels={}
                for title,document_id in zip(('PDF Book','EPUB Book','Docling Book'),docs[:3]):
                    open_member(page,'#documentGrid .bookshelf-card[data-owned=true]',title)
                    if title=='PDF Book':
                        page.locator('#readerNext').click()
                        page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Page 2')")
                    elif title=='EPUB Book':
                        page.locator('#readerScroll').evaluate('(element) => { element.scrollTop = Math.min(800, element.scrollHeight - element.clientHeight); element.dispatchEvent(new Event("scroll")); }')
                    else:
                        page.locator('#readerNext').click()
                    page.wait_for_timeout(700)
                    owner_labels[title]=page.locator('#readerPosition').inner_text()
                    page.locator('#readerClose').click()
                    value=saved_position(page,document_id)
                    assert value['locator']
                assert saved_position(page,docs[0])['locator']['page']==2
                for title in ('PDF Book','EPUB Book','Docling Book'):
                    open_member(page,'#documentGrid .bookshelf-card[data-owned=true]',title)
                    assert page.locator('#readerPosition').inner_text()==owner_labels[title]
                    page.locator('#readerClose').click()
                checks['owner_positions']='passed'
                page.screenshot(path=str(ARTIFACTS/'owner-bookshelves.png'),full_page=True)
                page.reload()
                page.wait_for_function("document.querySelectorAll('#documentGrid .bookshelf-card[data-owned=true]').length === 1")
                continue_shelf(page, '#documentGrid .bookshelf-card[data-owned=true]')
                page.wait_for_function("document.querySelector('#reader').hidden === false")
                assert 'Docling Book' in page.locator('#readerTitle').inner_text()
                page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Location') || document.querySelector('#readerPosition').textContent.includes('Page')")
                assert page.locator('#readerPosition').inner_text()==owner_labels['Docling Book']
                page.locator('#readerClose').click()
                checks['owner_reload_resume']='passed'
                server.terminate(); server.wait(timeout=5)
                server=start()
                page.reload()
                page.wait_for_function("document.querySelectorAll('#documentGrid .bookshelf-card[data-owned=true]').length === 1")
                for title in ('PDF Book','EPUB Book','Docling Book'):
                    open_member(page,'#documentGrid .bookshelf-card[data-owned=true]',title)
                    assert page.locator('#readerPosition').inner_text()==owner_labels[title]
                    page.locator('#readerClose').click()
                checks['all_formats_restart_resume']='passed'
                for title,document_id in zip(('PDF Book','EPUB Book'),docs[:2]):
                    open_member(page,'#documentGrid .bookshelf-card[data-owned=true]',title)
                    wait_bookmark(page,base,shelf_id,document_id)
                    page.locator('#readerClose').click()
                    continue_shelf(page, '#documentGrid .bookshelf-card[data-owned=true]')
                    page.wait_for_function("document.querySelector('#reader').hidden === false")
                    page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Page') || document.querySelector('#readerPosition').textContent.includes('Location')")
                    assert title in page.locator('#readerTitle').inner_text()
                    assert page.locator('#readerPosition').inner_text()==owner_labels[title]
                    page.locator('#readerClose').click()
                checks['continue_pdf_epub_restart']='passed'
                open_member(page,'#documentGrid .bookshelf-card[data-owned=true]','Docling Book')
                wait_bookmark(page,base,shelf_id,docs[2])
                page.locator('#readerClose').click()
                page.locator('#logoutMenuItem').evaluate('(button) => button.click()')
                page.wait_for_url(base+'/login')
                login(page,base,'recipient','recipient-password')
                page.wait_for_function("document.querySelectorAll('#documentGrid .bookshelf-card[data-owned=false]').length === 1")
                assert page.locator('#bookshelfArea').count()==0
                assert page.locator('#documentGrid').locator(':scope > *').count()==2
                assert page.locator('#documentGrid .document-card').count()==1
                page.locator('#librarySearch').fill('Reading shelf')
                page.wait_for_function("document.querySelector('#documentGrid').children.length === 1 && document.querySelector('#documentGrid .bookshelf-card')")
                page.locator('#filtersToggle').click()
                page.locator('#filterScope').select_option('documents')
                page.get_by_text('No matching documents').wait_for()
                page.locator('#filterScope').select_option('bookshelves')
                page.wait_for_function("document.querySelectorAll('#documentGrid .bookshelf-card').length === 1")
                assert page.get_by_role('button', name='Filters active', exact=True).count() == 1
                assert page.locator('#filterScope').input_value() == 'bookshelves'
                page.locator('#librarySearch').fill('PDF Book')
                page.get_by_text('No matching bookshelves').wait_for()
                if page.locator('#catalogFilters').is_hidden(): page.locator('#filtersToggle').click()
                page.locator('#clearFilters').click()
                page.wait_for_function("document.querySelectorAll('#documentGrid .document-card').length === 1")
                assert page.locator('#librarySearch').input_value() == 'PDF Book'
                page.locator('#librarySearch').fill('')
                page.wait_for_function("document.querySelectorAll('#documentGrid .bookshelf-card').length === 1")
                checks['unified_grid_search_scope']='passed'
                assert page.locator('#documentGrid .bookshelf-card[data-owned=true]').count()==0
                assert page.locator('#documentGrid .bookshelf-card[data-owned=false]').count()==1
                page.locator('#documentGrid .bookshelf-card[data-owned=false]').locator('.bookshelf-card-open').click()
                page.locator('.bookshelf-member').first.wait_for()
                assert page.locator('.bookshelf-order-manager').count()==0
                assert page.locator('.bookshelf-member').count()==3
                page.screenshot(path=str(ARTIFACTS/'shared-bookshelf.png'),full_page=True)
                checks['shared_section']='passed'
                page.locator('#closeBookshelfDialog').click()
                for title,document_id in zip(('PDF Book','EPUB Book','Docling Book'),docs[:3]):
                    assert page.request.get(base+f'/api/documents/{document_id}/progress').json()['position'] is None
                    open_member(page,'#documentGrid .bookshelf-card[data-owned=false]',title)
                    if title=='PDF Book':
                        page.locator('#readerNext').click(); page.locator('#readerNext').click()
                        page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Page 3')")
                    elif title=='EPUB Book':
                        page.locator('#readerScroll').evaluate('(element) => { element.scrollTop = Math.min(350, element.scrollHeight - element.clientHeight); element.dispatchEvent(new Event("scroll")); }')
                    else:
                        page.locator('#readerNext').click(); page.locator('#readerNext').click()
                    page.wait_for_timeout(700)
                    page.locator('#readerClose').click()
                    assert saved_position(page,document_id)['locator']
                assert saved_position(page,docs[0])['locator']['page']==3
                open_member(page,'#documentGrid .bookshelf-card[data-owned=false]','PDF Book')
                page.locator('#readerClose').click()
                with module.db() as conn:
                    owner_bookmark=conn.execute('SELECT document_id FROM bookshelf_bookmarks WHERE user_id=? AND bookshelf_id=?',(owner['id'],shelf_id)).fetchone()[0]
                    recipient_bookmark=conn.execute('SELECT document_id FROM bookshelf_bookmarks WHERE user_id=? AND bookshelf_id=?',(recipient['id'],shelf_id)).fetchone()[0]
                    assert owner_bookmark==docs[2] and recipient_bookmark==docs[0]
                    assert conn.execute('SELECT COUNT(*) FROM reading_positions WHERE document_id IN (?,?,?)',(docs[0],docs[1],docs[2])).fetchone()[0]==6
                checks['independent_positions']='passed'
                open_member(page,'#documentGrid .bookshelf-card[data-owned=false]','Docling Book')
                page.locator('#readerClose').click()
                assert setup.patch(f'/api/documents/{docs[1]}/visibility',json={'visibility':'private'}).status_code==200
                page.reload()
                page.wait_for_function("document.querySelector('#documentGrid .bookshelf-card[data-owned=false] .bookshelf-card-open')?.getAttribute('aria-label')?.includes('2 visible documents')")
                assert page.locator('#documentGrid .bookshelf-card[data-owned=false] .bookshelf-cover').count()==2
                assert all(docs[1] not in source for source in page.locator('#documentGrid .bookshelf-card[data-owned=false] .bookshelf-cover').evaluate_all('(images) => images.map(image => image.src)'))
                page.locator('#documentGrid .bookshelf-card[data-owned=false]').locator('.bookshelf-card-open').click()
                page.locator('.bookshelf-member').first.wait_for()
                assert page.locator('.bookshelf-member').count()==2
                assert 'EPUB Book' not in page.locator('#bookshelfDialogBody').inner_text()
                assert page.locator('.bookshelf-member .bookshelf-cover').count()==2
                page.screenshot(path=str(ARTIFACTS/'mixed-access.png'),full_page=True)
                page.locator('#closeBookshelfDialog').click()
                checks['mixed_visibility']='passed'
                assert setup.patch(f'/api/documents/{docs[2]}/visibility',json={'visibility':'private'}).status_code==200
                page.reload()
                page.wait_for_function("document.querySelector('#documentGrid .bookshelf-card[data-owned=false] .bookshelf-card-open')?.getAttribute('aria-label')?.includes('1 visible document')")
                continue_shelf(page, '#documentGrid .bookshelf-card[data-owned=false]')
                page.wait_for_function("document.querySelector('#reader').hidden === false")
                assert 'PDF Book' in page.locator('#readerTitle').inner_text()
                page.locator('#readerClose').click()
                (module.document_library.root/f'sources/{docs[0]}.source').unlink()
                page.reload()
                page.wait_for_function("document.querySelectorAll('#documentGrid .bookshelf-card[data-owned=false]').length === 1")
                open_shelf(page, '#documentGrid .bookshelf-card[data-owned=false]')
                assert page.locator('#bookshelfDialogBody').get_by_role('button',name='Continue reading').is_disabled()
                checks['fallback_and_disabled']='passed'
                assert page_errors==[],page_errors
                browser.close()
            server.terminate(); server.wait(timeout=5)
            server=start()
            with sync_playwright() as playwright:
                browser=playwright.chromium.launch(headless=True)
                page=browser.new_page()
                login(page,base,'owner','owner-password')
                assert page.locator('#documentGrid .bookshelf-card[data-owned=true]').count()==1
                assert 'Reading shelf' in page.locator('#documentGrid .bookshelf-card[data-owned=true]').inner_text()
                assert page.request.get(base+f'/api/documents/{docs[1]}/progress').json()['position']
                assert page.request.get(base+f'/api/documents/{docs[2]}/progress').json()['position']
                continue_shelf(page, '#documentGrid .bookshelf-card[data-owned=true]')
                page.wait_for_function("document.querySelector('#reader').hidden === false")
                assert 'Docling Book' in page.locator('#readerTitle').inner_text()
                checks['restart']='passed'
                page.locator('#readerClose').click()
                created=page.request.post(base+'/api/bookshelves',data={'name':'Arrange next'})
                assert created.status==201
                second_shelf_id=created.json()['id']
                page.reload()
                page.wait_for_function("document.querySelectorAll('#documentGrid .bookshelf-card').length === 2")
                assert page.locator('#documentGrid .bookshelf-card').evaluate_all('(cards) => cards.map(card => card.dataset.bookshelfId)')==[second_shelf_id,shelf_id]
                first_card=page.locator(f'#documentGrid .bookshelf-card[data-bookshelf-id="{shelf_id}"]')
                first_card.locator('.bookshelf-card-open').click()
                manager=page.locator('.bookshelf-order-manager')
                manager.wait_for()
                assert manager.is_visible()
                assert manager.locator('.bookshelf-order-item span').all_inner_texts()==['Reading shelf','Arrange next']
                manager.locator('.bookshelf-order-item').nth(1).get_by_role('button',name='Move bookshelf up').focus()
                page.keyboard.press('Enter')
                page.wait_for_function("[...document.querySelectorAll('.bookshelf-order-item span')].map(node => node.textContent).join('|') === 'Arrange next|Reading shelf'")
                assert page.request.get(base+'/api/bookshelves').json()['owned'][0]['id']==second_shelf_id
                assert page.locator('#documentGrid .bookshelf-card').evaluate_all('(cards) => cards.map(card => card.dataset.bookshelfId)')==[second_shelf_id,shelf_id]
                page.reload()
                first_card.locator('.bookshelf-card-open').click()
                page.locator('.bookshelf-order-manager').wait_for()
                assert page.locator('.bookshelf-order-item span').all_inner_texts()==['Arrange next','Reading shelf']
                page.locator('#closeBookshelfDialog').click()
                assert page.request.delete(base+f'/api/bookshelves/{second_shelf_id}',data={'confirm':'Arrange next'}).status==200
                page.reload()
                checks['owner_order_manager']='passed'
                removed=page.request.delete(base+f'/api/documents/{docs[1]}',data={'confirm':'EPUB Book'})
                assert removed.status==200
                page.reload()
                page.wait_for_function("document.querySelector('#documentGrid .bookshelf-card[data-owned=true] .bookshelf-card-open')?.getAttribute('aria-label')?.includes('2 visible documents')")
                page.locator('#documentGrid .bookshelf-card[data-owned=true]').locator('.bookshelf-card-open').click()
                page.wait_for_function("document.querySelectorAll('.bookshelf-member').length === 2")
                assert page.locator('.bookshelf-member').count()==2
                assert 'EPUB Book' not in page.locator('#bookshelfDialogBody').inner_text()
                page.screenshot(path=str(ARTIFACTS/'after-removal.png'),full_page=True)
                checks['browser_removal']='passed'
                browser.close()
        finally:
            server.terminate(); server.wait(timeout=5)
    (ARTIFACTS/'report.json').write_text(json.dumps(checks,indent=2))
    print(json.dumps(checks,sort_keys=True))


if __name__=='__main__': main()
