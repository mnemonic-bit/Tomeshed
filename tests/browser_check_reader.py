"""Feature 0003 Chromium checks against a restartable Tomeshed process."""

import json
import io
import os
import socket
import sqlite3
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.request import urlopen
import sys

from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path('/tmp/tomeshed-feature-0003-browser')
ARTIFACTS.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
from test_documents import pdf_bytes
from test_reader import docling_fixture, epub_fixture
from pypdf import PdfWriter


def port_number():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def start_server(folder, port):
    environment = dict(os.environ, TOMESHED_DB=str(folder / 'library.db'), TOMESHED_LIBRARY_DIR=str(folder / 'storage'),
                       HOST='127.0.0.1', PORT=str(port), PYTHONDONTWRITEBYTECODE='1')
    process = subprocess.Popen([sys.executable, 'tomeshed.py'], cwd=ROOT, env=environment,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=.2):
                return process
        except Exception:
            time.sleep(.1)
    process.terminate(); raise AssertionError('Server did not start')


def seed(folder, content, kind, title, state='ready'):
    document_id = uuid.uuid4().hex
    path = folder / 'storage' / 'sources' / f'{document_id}.source'
    path.write_bytes(content)
    with sqlite3.connect(folder / 'library.db') as conn:
        conn.execute('''INSERT INTO documents(id,original_filename,source_path,source_type,title,author,byte_size,
            search_key,count_kind,state,error,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (document_id, f'{title}.{kind}', f'sources/{document_id}.source', kind, title, 'Fixture author', len(content),
             title.casefold(), 'exact' if kind == 'pdf' else 'unknown', state,
             'Indexing warning: fixture' if state == 'ready_with_warning' else None, time.time()))
    return document_id, path


def replace_zip_member(path, member, replacement):
    import zipfile
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as original, zipfile.ZipFile(output, 'w') as changed:
        for name in original.namelist():
            changed.writestr(name, replacement if name == member else original.read(name))
    path.write_bytes(output.getvalue())


def mixed_pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=500)
    writer.add_blank_page(width=600, height=500)
    data = io.BytesIO(); writer.write(data)
    return data.getvalue()


def open_card(page, title):
    card = page.locator('.document-card').filter(has_text=title)
    card.locator('.document-open').dblclick()
    page.locator('#reader').wait_for(state='visible')
    page.wait_for_function("document.querySelector('#readerPosition').textContent !== 'Opening…'")
    return card


def sign_out(page, base):
    page.locator('#accountMenuButton').click()
    page.locator('#logoutMenuItem').click()
    page.wait_for_url(base + '/login')


def sign_in(page, base, username, password):
    page.locator('#username').fill(username)
    page.locator('#password').fill(password)
    page.get_by_role('button', name='Sign in').click()
    page.wait_for_url(base + '/')
    page.wait_for_function("document.querySelectorAll('.document-card').length > 0")


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number(); base = f'http://127.0.0.1:{port}'
        process = start_server(folder, port)
        try:
            pdf_id, pdf_path = seed(folder, pdf_bytes(12), 'pdf', 'Reader PDF')
            mixed_id, _ = seed(folder, mixed_pdf_bytes(), 'pdf', 'Mixed PDF')
            warning_id, _ = seed(folder, pdf_bytes(2), 'pdf', 'Warning PDF', 'ready_with_warning')
            epub_id, epub_path = seed(folder, epub_fixture(text='Paragraph one ' * 500), 'epub', 'Reader EPUB')
            marker_id, marker_path = seed(folder, epub_fixture(), 'epub', 'Marker EPUB')
            replace_zip_member(marker_path, 'OPS/chapter.xhtml', '<html><body><h1>Chapter</h1><span role="doc-pagebreak" aria-label="12"></span><p>' + ('Marker paragraph ' * 300) + '</p></body></html>')
            chapters = ''.join(f'<p id="paragraph-{number}">Paragraph {number} ' + ('word ' * 80) + '</p>' for number in range(1, 31))
            replace_zip_member(epub_path, 'OPS/chapter.xhtml', f'<html><body><h1 id="first">Chapter</h1>{chapters}<img src="image.png" alt="Reading illustration"/></body></html>')
            json_id, json_path = seed(folder, docling_fixture(), 'docling', 'Reader Docling')
            missing_id, missing_path = seed(folder, pdf_bytes(1), 'pdf', 'Missing PDF')
            missing_path.unlink()
            broken_id, broken_path = seed(folder, b'{broken', 'docling', 'Broken Docling')
            unsupported_id, unsupported_path = seed(folder, epub_fixture(), 'epub', 'Unsupported EPUB')
            # Replace the EPUB spine with a valid empty XHTML section.
            replace_zip_member(unsupported_path, 'OPS/chapter.xhtml', '<html><body></body></html>')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(viewport={'width': 900, 'height': 750}, has_touch=True)
                page = context.new_page()
                page.goto(base + '/login')
                page.locator('#password').fill('reader-password')
                page.locator('#password_confirmation').fill('reader-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_url(base + '/')
                page.wait_for_function("document.querySelectorAll('.document-card').length >= 9")
                # Search, focus, warning state, and both close methods.
                page.set_viewport_size({'width': 390, 'height': 300})
                page.locator('#librarySearch').fill('PDF')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 4")
                page.locator('.document-card').filter(has_text='Warning PDF').locator('.document-open').scroll_into_view_if_needed()
                page.evaluate("""() => document.addEventListener('dblclick', event => {
                    if (event.target.closest('.document-card')) window.libraryScrollAtOpen = window.scrollY;
                }, {capture: true, once: true})""")
                warning = open_card(page, 'Warning PDF')
                library_scroll = page.evaluate('window.libraryScrollAtOpen')
                assert library_scroll > 0
                assert page.locator('#readerTitle').inner_text() == 'Warning PDF'
                page.locator('#readerClose').click()
                assert page.locator('#librarySearch').input_value() == 'PDF'
                assert abs(page.evaluate('window.scrollY') - library_scroll) <= 2
                assert page.evaluate("document.activeElement.closest('.document-card')?.dataset.documentId") == warning_id
                warning.locator('.document-open').dblclick()
                page.keyboard.press('Escape')
                assert page.evaluate("document.activeElement.closest('.document-card')?.dataset.documentId") == warning_id
                page.set_viewport_size({'width': 900, 'height': 750})
                page.locator('#librarySearch').fill('Reader PDF')
                card = open_card(page, 'Reader PDF')
                assert page.locator('.pdf-page').count() == 12
                page.locator('#readerClose').focus()
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement.id') == 'readerPrevious'
                assert page.locator('#readerPrevious').evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement.id') == 'readerNext'
                page.keyboard.press('Enter')
                page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Page 2')")
                page.locator('#readerScroll').focus()
                assert page.locator('#readerScroll').evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement.id') == 'readerClose'
                page.keyboard.press('Shift+Tab')
                assert page.evaluate('document.activeElement.id') == 'readerScroll'
                page.evaluate("document.querySelector('#librarySearch').focus()")
                assert page.evaluate('document.activeElement.id') == 'readerClose'
                page.locator('[data-page="7"]').scroll_into_view_if_needed()
                page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Page 7')")
                page.screenshot(path=str(ARTIFACTS / 'pdf-page-7.png'))
                page.wait_for_timeout(700)
                before = page.evaluate("({top: document.querySelector('[data-page=\"7\"]').getBoundingClientRect().top, view: document.querySelector('#readerScroll').getBoundingClientRect().top})")
                width_before_zoom = page.locator('[data-page="7"]').evaluate('el => el.getBoundingClientRect().width')
                page.locator('#readerZoomIn').tap()
                assert page.locator('#readerContent').evaluate("el => Number(getComputedStyle(el).getPropertyValue('--reader-zoom'))") > 1
                assert page.locator('[data-page="7"]').evaluate('el => el.getBoundingClientRect().width') > width_before_zoom
                page.locator('#readerClose').click()
                assert page.evaluate("document.activeElement.closest('.document-card')?.dataset.documentId") == pdf_id
                open_card(page, 'Reader PDF')
                assert 'Page 7' in page.locator('#readerPosition').inner_text()
                after = page.evaluate("({top: document.querySelector('[data-page=\"7\"]').getBoundingClientRect().top, view: document.querySelector('#readerScroll').getBoundingClientRect().top, height: document.querySelector('[data-page=\"7\"]').offsetHeight})")
                assert abs((before['top']-before['view']) - (after['top']-after['view'])) <= after['height'] * .05 + 15, (before, after)
                page.reload()
                page.wait_for_function("document.querySelectorAll('.document-card').length > 0")
                open_card(page, 'Reader PDF')
                assert 'Page 7' in page.locator('#readerPosition').inner_text()
                page.locator('#readerClose').click()
                process.terminate(); process.wait(timeout=10)
                process = start_server(folder, port)
                page.reload()
                page.wait_for_function("document.querySelectorAll('.document-card').length > 0")
                open_card(page, 'Reader PDF')
                assert 'Page 7' in page.locator('#readerPosition').inner_text()
                page.locator('#readerClose').click()
                # Backend completion and positions are independent for two browser accounts.
                created = page.request.post(base + '/api/users', data={'username': 'reader2', 'password': 'second-password', 'role': 'normal'})
                assert created.status == 201
                open_card(page, 'Reader PDF')
                assert page.locator('#readerFinished, #readerStartOver').count() == 0
                assert page.request.post(base + f'/api/documents/{pdf_id}/finish').json()['completed'] is True
                assert page.request.get(base + f'/api/documents/{pdf_id}/progress').json()['position']['locator']['page'] == 7
                page.locator('#readerClose').click()
                assert pdf_path.exists()
                sign_out(page, base)
                sign_in(page, base, 'reader2', 'second-password')
                page.locator('#librarySearch').fill('Reader PDF')
                open_card(page, 'Reader PDF')
                assert 'Page 1' in page.locator('#readerPosition').inner_text()
                assert page.request.get(base + f'/api/documents/{pdf_id}/progress').json()['completed'] is False
                page.locator('[data-page="2"]').scroll_into_view_if_needed()
                page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Page 2')")
                page.wait_for_timeout(650)
                page.locator('#readerClose').click()
                sign_out(page, base)
                sign_in(page, base, 'admin', 'reader-password')
                page.locator('#librarySearch').fill('Reader PDF')
                open_card(page, 'Reader PDF')
                assert 'Page 7' in page.locator('#readerPosition').inner_text()
                assert page.request.get(base + f'/api/documents/{pdf_id}/progress').json()['completed'] is True
                page.locator('#readerClose').click()
                assert page.request.post(base + f'/api/documents/{pdf_id}/start-over').json() == {'position': None, 'completed': False}
                open_card(page, 'Reader PDF')
                assert 'Page 1' in page.locator('#readerPosition').inner_text()
                assert page.request.get(base + f'/api/documents/{pdf_id}/progress').json() == {'position': None, 'completed': False}
                page.locator('[data-page="7"]').scroll_into_view_if_needed()
                page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Page 7')")
                page.wait_for_timeout(650)
                page.locator('#readerClose').click()
                pdf_path.write_bytes(pdf_bytes(4))
                open_card(page, 'Reader PDF')
                assert 'Page 4' in page.locator('#readerPosition').inner_text()
                assert 'approximate' in page.locator('#readerPosition').inner_text()
                page.locator('#readerClose').click()
                page.locator('#librarySearch').fill('Mixed PDF')
                open_card(page, 'Mixed PDF')
                page.evaluate('''() => {
                    const s=document.querySelector('#readerScroll');
                    const one=document.querySelector('[data-page="1"]');
                    const two=document.querySelector('[data-page="2"]');
                    const top=one.getBoundingClientRect().top-s.getBoundingClientRect().top+s.scrollTop;
                    s.scrollTop=top+one.offsetHeight-240;
                }''')
                page.wait_for_timeout(160)
                expected_page = page.evaluate('''() => {
                    const s=document.querySelector('#readerScroll').getBoundingClientRect();
                    return [...document.querySelectorAll('.pdf-page')].map((node,index) => {
                        const r=node.getBoundingClientRect();
                        return {page:index+1,area:Math.max(0,Math.min(r.bottom,s.bottom)-Math.max(r.top,s.top))*Math.max(0,Math.min(r.right,s.right)-Math.max(r.left,s.left))};
                    }).sort((a,b)=>b.area-a.area)[0].page;
                }''')
                assert f'Page {expected_page}' in page.locator('#readerPosition').inner_text()
                page.locator('#readerClose').click()
                # EPUB source order, reflow, TOC, saved locator and fallback.
                page.locator('#librarySearch').fill('Reader EPUB')
                open_card(page, 'Reader EPUB')
                assert page.locator('.epub-section').count() == 1
                assert page.locator('.epub-section img').count() == 1
                assert page.locator('#readerToc button').count() == 1
                assert 'Page ' not in page.locator('#readerPosition').inner_text()
                paragraph = page.locator('.epub-section p').nth(20)
                width_before = paragraph.evaluate('el => el.getBoundingClientRect().width')
                page.set_viewport_size({'width': 390, 'height': 750})
                width_after = paragraph.evaluate('el => el.getBoundingClientRect().width')
                assert width_after < width_before
                paragraph.scroll_into_view_if_needed()
                page.wait_for_timeout(700)
                saved_epub = page.request.get(base + f'/api/documents/{epub_id}/progress').json()['position']
                assert saved_epub['locator']['section'] == 'OPS/chapter.xhtml'
                assert saved_epub['locator']['element'] >= 20
                page.screenshot(path=str(ARTIFACTS / 'epub-paragraph-390.png'))
                page.locator('#readerClose').click()
                open_card(page, 'Reader EPUB')
                assert page.locator('#readerPosition').inner_text().startswith('Location')
                epub_restore = page.evaluate('''locator => {
                    const s=document.querySelector('#readerScroll');
                    const n=[...document.querySelectorAll('[data-locator]')].find(el=>el.dataset.section===locator.section && Number(el.dataset.element)===locator.element);
                    const top=n.getBoundingClientRect().top-s.getBoundingClientRect().top+s.scrollTop;
                    return {visible:n.getBoundingClientRect().bottom>s.getBoundingClientRect().top && n.getBoundingClientRect().top<s.getBoundingClientRect().bottom,
                            offset:Math.max(0,Math.min(1,(s.scrollTop-top)/n.offsetHeight))};
                }''', saved_epub['locator'])
                assert epub_restore['visible'] and abs(epub_restore['offset'] - saved_epub['locator']['offset']) < .12
                page.locator('#readerZoomIn').click()
                page.locator('#readerClose').click()
                open_card(page, 'Reader EPUB')
                assert page.locator('.epub-section p').nth(20).is_visible()
                page.locator('#readerToc button').first.tap()
                assert page.locator('#readerScroll').evaluate('el => el.scrollTop') < 100
                page.locator('#readerClose').click()
                # Set an invalidated locator directly, then replace the source.
                page.wait_for_timeout(700)
                assert page.request.put(base + f'/api/documents/{epub_id}/progress', data={'locator': {'section': 'OPS/chapter.xhtml', 'element': 3, 'offset': .4}, 'percent': 70}).status == 200
                replace_zip_member(epub_path, 'OPS/chapter.xhtml', '<html><body><h1>Short replacement</h1></body></html>')
                open_card(page, 'Reader EPUB')
                assert 'approximate' in page.locator('#readerPosition').inner_text()
                page.locator('#readerClose').click()
                page.locator('#librarySearch').fill('Marker EPUB')
                open_card(page, 'Marker EPUB')
                page.locator('.epub-section p').scroll_into_view_if_needed()
                page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Page 12')")
                page.locator('#readerClose').click()
                # Docling structured HTML sanitization, exact/unknown labels, and changed locator.
                page.locator('#librarySearch').fill('Reader Docling')
                open_card(page, 'Reader Docling')
                assert page.locator('#readerContent h1').count() == 2
                assert page.evaluate('window.doclingAttack') is None
                assert page.locator('#readerContent script').count() == 0
                assert 'Page 1' in page.locator('#readerPosition').inner_text()
                page.screenshot(path=str(ARTIFACTS / 'docling-structured-390.png'))
                docling_paragraph = page.locator('#readerContent p').nth(18)
                docling_paragraph.evaluate('el => {const s=document.querySelector("#readerScroll");s.scrollTop += el.getBoundingClientRect().top-s.getBoundingClientRect().top+el.offsetHeight*.4}')
                page.wait_for_timeout(700)
                saved_docling = page.request.get(base + f'/api/documents/{json_id}/progress').json()['position']
                assert int(saved_docling['locator']['element'].split('/')[-1]) >= 18
                assert 0 <= saved_docling['locator']['offset'] <= 1
                page.locator('#readerClose').click()
                open_card(page, 'Reader Docling')
                assert saved_docling['locator']['element'] in page.locator('#readerContent [data-locator]').evaluate_all('(nodes) => nodes.filter(n => n.getBoundingClientRect().bottom > document.querySelector("#readerScroll").getBoundingClientRect().top).slice(0,1).map(n => n.dataset.locator)')
                docling_offset = page.evaluate('''ref => {
                    const s=document.querySelector('#readerScroll');const n=[...document.querySelectorAll('[data-locator]')].find(el=>el.dataset.locator===ref);
                    const top=n.getBoundingClientRect().top-s.getBoundingClientRect().top+s.scrollTop;
                    return Math.max(0,Math.min(1,(s.scrollTop-top)/n.offsetHeight));
                }''', saved_docling['locator']['element'])
                assert abs(docling_offset - saved_docling['locator']['offset']) < .12
                page.locator('#readerClose').click()
                json_path.write_bytes(docling_fixture('Replacement heading', extra=0))
                open_card(page, 'Reader Docling')
                assert 'approximate' in page.locator('#readerPosition').inner_text()
                page.locator('#readerClose').click()
                # Page conditions, no progress writes on open failure.
                for title, document_id, kind in [('Missing PDF', missing_id, 'Source missing'),
                                                  ('Broken Docling', broken_id, 'Rendering error'),
                                                  ('Unsupported EPUB', unsupported_id, 'Unsupported content')]:
                    page.locator('#librarySearch').fill(title)
                    open_card(page, title)
                    assert kind in page.locator('#readerError').inner_text()
                    if title == 'Missing PDF':
                        page.screenshot(path=str(ARTIFACTS / 'source-missing.png'))
                    assert page.request.get(base + f'/api/documents/{document_id}/progress').json()['position'] is None
                    page.locator('#readerClose').click()
                # One write after 500 ms of rapid scrolling; hidden and Close flush
                # the latest position while a delayed progress request is in flight.
                page.set_viewport_size({'width': 900, 'height': 750})
                page.locator('#librarySearch').fill('Reader PDF')
                open_card(page, 'Reader PDF')
                page.evaluate('''id => {
                    window.readerWrites = 0;
                    const original = window.fetch.bind(window);
                    window.fetch = (resource, options) => {
                        if (String(resource).endsWith(`/api/documents/${id}/progress`) && options?.method === 'PUT') {
                            window.readerWrites += 1;
                            return new Promise(resolve => setTimeout(() => resolve(original(resource, options)), 900));
                        }
                        return original(resource, options);
                    };
                }''', pdf_id)
                for number in (1, 2, 3):
                    page.locator(f'[data-page="{number}"]').evaluate('el => {const s=document.querySelector("#readerScroll");s.scrollTop += el.getBoundingClientRect().top-s.getBoundingClientRect().top}')
                    page.wait_for_timeout(90)
                page.wait_for_timeout(560)
                assert page.evaluate('window.readerWrites') == 1
                before_scroll = page.locator('#readerScroll').evaluate('el => el.scrollTop')
                page.locator('[data-page="4"]').evaluate('el => {const s=document.querySelector("#readerScroll");s.scrollTop += el.getBoundingClientRect().top-s.getBoundingClientRect().top}')
                assert page.locator('#readerScroll').evaluate('el => el.scrollTop') > before_scroll
                page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true, get:()=>true}); document.dispatchEvent(new Event('visibilitychange'))")
                page.wait_for_timeout(1900)
                assert page.evaluate('window.readerWrites') == 2
                page.locator('[data-page="3"]').evaluate('el => {const s=document.querySelector("#readerScroll");s.scrollTop += el.getBoundingClientRect().top-s.getBoundingClientRect().top}')
                page.locator('#readerClose').click()
                open_card(page, 'Reader PDF')
                assert 'Page 3' in page.locator('#readerPosition').inner_text()
                page.locator('#readerClose').click()
                browser.close()
            report = {'result': 'passed', 'pdf_id': pdf_id, 'epub_id': epub_id, 'docling_id': json_id,
                      'checks': ['card focus and search', 'PDF page 7 close/reload/restart', 'shorter PDF fallback',
                                 'two user progress and completion API', 'EPUB text image TOC and reflow',
                                 'EPUB invalidated locator fallback', 'Docling escaping and element fallback',
                                 'missing rendering and unsupported states', '500 ms coalescing and hidden/Close saves']}
            (ARTIFACTS / 'report.json').write_text(json.dumps(report, indent=2))
            print(json.dumps(report))
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == '__main__':
    main()
