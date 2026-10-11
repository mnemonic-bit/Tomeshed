"""Check document controls in the reader panel in Chromium."""

import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check_reader import port_number, seed, start_server
from test_documents import pdf_bytes


def open_document(page, document_id):
    page.locator(f'.document-card[data-document-id="{document_id}"] .document-open').dblclick()
    panel = page.locator('#readerDocumentPanel')
    panel.wait_for(state='visible')
    return panel


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        process = start_server(folder, port)
        try:
            document_id, _ = seed(folder, pdf_bytes(8), 'pdf', 'Panel PDF', 'ready_with_warning')
            base = f'http://127.0.0.1:{port}'
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                admin = browser.new_context(viewport={'width': 1280, 'height': 800})
                page = admin.new_page()
                page.goto(base + '/login')
                page.locator('#password').fill('reader-password')
                page.locator('#password_confirmation').fill('reader-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_url(base + '/')
                page.locator(f'.document-card[data-document-id="{document_id}"]').wait_for()
                assert page.locator('.document-info-button').count() == 0
                page.evaluate("""() => { const originalFetch = window.fetch;
                    window.fetch = (...args) => {
                        const response = originalFetch(...args);
                        return String(args[0]).endsWith('/reader-open')
                            ? response.then(value => new Promise(resolve => setTimeout(() => resolve(value), 450)))
                            : response;
                    };
                }""")
                panel = open_document(page, document_id)
                title = panel.get_by_label('Title')
                title.fill('Unsaved before reader open')
                title.focus()
                panel.evaluate('el => el.scrollTop = 220')
                before_state_scroll = panel.evaluate('el => el.scrollTop')
                page.wait_for_function("document.querySelector('#readerDocumentPanel').textContent.includes('Reading state: in progress')")
                assert 'Last read: Never' not in panel.inner_text()
                assert title.input_value() == 'Unsaved before reader open'
                assert title.evaluate('el => document.activeElement === el')
                assert panel.evaluate('el => el.scrollTop') == before_state_scroll
                assert 500 <= panel.bounding_box()['width'] <= 580
                assert 'Author' in panel.inner_text()
                assert 'Original filename:' in panel.inner_text()
                assert panel.get_by_role('button', name='Add to bookshelf').is_visible()
                assert panel.get_by_role('button', name='Retry indexing').is_visible()
                assert panel.get_by_label('Visibility').is_visible()
                title.fill('Unsaved title')
                title.focus()
                panel.evaluate('el => el.scrollTop = 220')
                panel_scroll = panel.evaluate('el => el.scrollTop')
                reader_scroll = page.locator('#readerScroll')
                page.locator('#readerPanelMinimize').click()
                assert panel.is_hidden()
                assert page.locator('#readerPanelRestore').is_visible()
                page.locator('#readerPanelRestore').click()
                assert panel.is_visible() and title.input_value() == 'Unsaved title'
                assert panel.evaluate('el => el.scrollTop') == panel_scroll, (panel_scroll, panel.evaluate('el => el.scrollTop'))
                assert title.evaluate('el => document.activeElement === el')
                reader_scroll.evaluate('el => el.scrollTop = 500')
                before = reader_scroll.evaluate('el => el.scrollTop')
                page.locator('#readerPanelMinimize').click()
                assert reader_scroll.evaluate('el => el.scrollTop') > 0
                page.locator('#readerPanelRestore').click()
                assert abs(reader_scroll.evaluate('el => el.scrollTop') - before) < 150
                title.focus()
                panel.evaluate('el => el.scrollTop = 200')
                before_state_scroll = panel.evaluate('el => el.scrollTop')
                page.evaluate("document.querySelector('#readerFinished').click()")
                page.wait_for_function("document.querySelector('#readerDocumentPanel').textContent.includes('Reading state: finished')")
                assert title.input_value() == 'Unsaved title'
                assert title.evaluate('el => document.activeElement === el')
                assert panel.evaluate('el => el.scrollTop') == before_state_scroll
                page.evaluate("document.querySelector('#readerStartOver').click()")
                page.wait_for_function("document.querySelector('#readerDocumentPanel').textContent.includes('Reading state: in progress')")
                assert title.input_value() == 'Unsaved title'
                assert title.evaluate('el => document.activeElement === el')
                assert panel.evaluate('el => el.scrollTop') == before_state_scroll
                page.route(f'**/api/documents/{document_id}/metadata', lambda route: route.fulfill(status=503, content_type='application/json', body=json.dumps({'error': 'controlled rejection'})))
                title.fill('Rejected title')
                panel.get_by_role('button', name='Save metadata').click()
                panel.get_by_role('alert').get_by_text('controlled rejection', exact=False).wait_for()
                assert page.locator('#reader').is_visible()
                page.unroute(f'**/api/documents/{document_id}/metadata')
                title.fill('Saved title')
                panel.get_by_role('button', name='Save metadata').click()
                panel.get_by_label('Title').wait_for()
                page.wait_for_function("document.querySelector('#readerTitle').textContent === 'Saved title'")
                page.locator('#readerClose').click()

                page.evaluate("async () => (await fetch('/api/users', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:'reader-normal',password:'normal-password',role:'normal'})})).ok")
                normal = browser.new_context(viewport={'width': 390, 'height': 740}, has_touch=True)
                phone = normal.new_page()
                phone.goto(base + '/login')
                phone.locator('#username').fill('reader-normal')
                phone.locator('#password').fill('normal-password')
                phone.get_by_role('button', name='Sign in').click()
                phone.wait_for_url(base + '/')
                phone.locator(f'.document-card[data-document-id="{document_id}"]').wait_for()
                mobile_panel = open_document(phone, document_id)
                assert not mobile_panel.get_by_label('Visibility').count()
                assert mobile_panel.get_by_role('button', name='Add to bookshelf').is_visible()
                bounds = mobile_panel.bounding_box()
                assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= 390
                reader_bounds = phone.locator('#readerScroll').bounding_box()
                assert reader_bounds['height'] >= 120 and reader_bounds['y'] >= bounds['y'] + bounds['height']
                phone.locator('#readerPanelMinimize').tap()
                assert phone.locator('#readerPanelRestore').is_visible()
                assert phone.locator('#readerScroll').is_visible()
                browser.close()
            print('passed: reader document panel')
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == '__main__':
    main()
