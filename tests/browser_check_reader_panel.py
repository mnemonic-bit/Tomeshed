"""Check the reader document panel in Chromium."""

import json
import sqlite3
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check_reader import port_number, seed, start_server
from test_documents import pdf_bytes
from test_reader import docling_fixture


TRASH_PATHS = [
    'M2.5 4h11',
    'M6 4V2.5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1V4',
    'M3.5 4l.7 9a1 1 0 0 0 1 .9h5.6a1 1 0 0 0 1-.9l.7-9',
    'M6.5 7v4',
    'M9.5 7v4',
]


def check_trash_action(page, panel, section):
    button = panel.locator(f'{section} .document-action.danger')
    assert button.get_attribute('aria-label') == 'Remove document'
    assert button.locator('.document-action-icon').inner_text() == ''
    svg = button.locator('svg')
    assert svg.get_attribute('viewBox') == '0 0 16 16'
    assert svg.get_attribute('aria-hidden') == 'true'
    assert [path.get_attribute('d') for path in svg.locator('path').all()] == TRASH_PATHS
    assert svg.get_attribute('stroke') == 'currentColor'
    assert svg.get_attribute('stroke-width') == '1.6'
    assert svg.bounding_box()['width'] == 20
    theme_colors = []
    for theme in ('light', 'dark'):
        page.evaluate('(theme) => document.documentElement.dataset.theme = theme', theme)
        page.mouse.move(0, 0)
        normal = button.evaluate('el => ({color: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor, icon: getComputedStyle(el.querySelector("svg")).stroke})')
        assert normal['color'] == normal['icon']
        button.hover()
        hover = button.evaluate('el => ({color: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor})')
        assert hover['color'] == normal['color'] and hover['background'] != normal['background']
        button.focus()
        page.keyboard.press('Tab')
        page.keyboard.press('Shift+Tab')
        assert button.evaluate('el => el.matches(":focus-visible") && getComputedStyle(el).outlineStyle !== "none"')
        theme_colors.append(normal['color'])
    assert theme_colors[0] != theme_colors[1]


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
            other_id, _ = seed(folder, pdf_bytes(2), 'pdf', 'Other panel PDF')
            artifact = folder / 'storage' / 'panel.json'
            artifact.write_bytes(docling_fixture())
            with sqlite3.connect(folder / 'library.db') as conn:
                conn.execute('UPDATE documents SET artifact_path=? WHERE id=?', ('panel.json', document_id))
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
                panel = open_document(page, document_id)
                check_trash_action(page, panel, '.reader-panel-details')
                confirmation = []
                page.once('dialog', lambda dialog: (confirmation.append(dialog.message), dialog.dismiss()))
                panel.locator('.reader-panel-details').get_by_role('button', name='Remove document').click()
                assert confirmation == ['Remove Panel PDF?']
                assert panel.is_visible()
                assert panel.get_by_text('Document info', exact=True).count() == 0
                assert panel.locator('h3').count() == 0
                assert page.locator('#readerTitle').inner_text() == 'Panel PDF'
                assert panel.locator('.document-inline-field[data-field="title"]').count() == 1
                assert panel.get_by_text('Original filename:').is_visible()
                assert panel.get_by_role('button', name='Retry indexing').is_visible()
                downloads = panel.locator('.document-download-split')
                assert downloads.get_by_role('link', name='Download original').get_attribute('href').endswith('/export/original')
                downloads.get_by_role('button', name='Choose download format').click()
                assert downloads.get_by_role('menuitem', name='Original PDF').is_visible()
                assert downloads.get_by_role('menuitem', name='Docling JSON (converted)').is_visible()
                page.keyboard.press('Escape')
                assert downloads.locator('.document-download-menu').is_hidden()
                downloads.get_by_role('button', name='Choose download format').press('ArrowDown')
                assert downloads.get_by_role('menuitem', name='Original PDF').evaluate('el => document.activeElement === el')
                page.keyboard.press('ArrowDown')
                assert downloads.get_by_role('menuitem', name='Docling JSON (converted)').evaluate('el => document.activeElement === el')
                page.keyboard.press('Escape')

                tag_input = panel.get_by_role('textbox', name='Add tag')
                tag_input.fill('Research')
                tag_input.press('Enter')
                panel.get_by_role('button', name='Remove tag Research').wait_for()
                assert page.evaluate("async (id) => (await fetch(`/api/documents/${id}/tags`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tag:'Research'})})).ok", other_id)
                panel.get_by_role('button', name='Remove tag Research').click()
                panel.get_by_role('button', name='Remove tag Research').wait_for(state='detached')
                tag_input = panel.get_by_role('textbox', name='Add tag')
                tag_input.fill('sea')
                assert panel.get_by_role('option', name='Research').is_visible()
                tag_input.press('ArrowDown')
                assert panel.get_by_role('option', name='Research').evaluate('el => document.activeElement === el')
                page.keyboard.press('Enter')
                panel.get_by_role('button', name='Remove tag Research').wait_for()
                tag_input = panel.get_by_role('textbox', name='Add tag')
                tag_input.fill('nomatch')
                assert panel.get_by_role('option', name='Research').count() == 0
                tag_input.press('Escape')
                assert panel.locator('.document-tag-suggestions').is_hidden()

                panel.get_by_role('button', name='Edit Title').click()
                title = panel.get_by_role('textbox', name='Title')
                title.fill('Unsaved title')
                page.locator('#readerScroll').evaluate('el => el.scrollTop = 500')
                reading_before = page.locator('#readerScroll').evaluate('el => el.scrollTop')
                panel.get_by_role('button', name='Minimize document info').click()
                assert panel.is_visible() and 'is-minimized' in panel.get_attribute('class')
                assert panel.locator('.reader-panel-details').is_hidden()
                assert panel.get_by_role('button', name='Add to bookshelf').is_visible()
                assert panel.get_by_role('button', name='Remove document').is_visible()
                check_trash_action(page, panel, '.reader-panel-rail')
                confirmation = []
                page.once('dialog', lambda dialog: (confirmation.append(dialog.message), dialog.dismiss()))
                panel.locator('.reader-panel-rail').get_by_role('button', name='Remove document').click()
                assert confirmation == ['Remove Panel PDF?']
                assert panel.is_visible()
                assert panel.get_by_role('button', name='Restore document info').is_visible()
                rail_box = panel.bounding_box()
                content_box = page.locator('#readerScroll').bounding_box()
                assert 60 <= rail_box['width'] <= 70 and content_box['x'] >= rail_box['x'] + rail_box['width']
                assert abs(rail_box['height'] - content_box['height']) < 2
                for control in panel.locator('.reader-panel-rail button').all():
                    assert control.bounding_box()['width'] >= 44 and control.bounding_box()['height'] >= 44
                panel.get_by_role('button', name='Restore document info').click()
                assert abs(page.locator('#readerScroll').evaluate('el => el.scrollTop') - reading_before) < 150
                assert panel.get_by_role('textbox', name='Title').evaluate('el => document.activeElement === el')
                panel.get_by_role('button', name='Minimize document info').click()
                page.locator('#readerClose').click()
                panel = open_document(page, document_id)
                assert 'is-minimized' in panel.get_attribute('class')
                panel.get_by_role('button', name='Restore document info').press('Enter')
                assert 'is-minimized' not in panel.get_attribute('class')
                assert panel.get_by_role('textbox', name='Title').input_value() == 'Unsaved title'
                title = panel.get_by_role('textbox', name='Title')
                title.press('Escape')
                assert panel.get_by_role('textbox', name='Title').count() == 0

                page.route(f'**/api/documents/{document_id}/metadata', lambda route: route.fulfill(status=503, content_type='application/json', body=json.dumps({'error': 'controlled rejection'})))
                panel.get_by_role('button', name='Edit Title').click()
                title = panel.get_by_role('textbox', name='Title')
                title.fill('Rejected title')
                title.press('Enter')
                panel.get_by_role('alert').get_by_text('controlled rejection', exact=False).wait_for()
                assert panel.get_by_role('textbox', name='Title').input_value() == 'Rejected title'
                page.unroute(f'**/api/documents/{document_id}/metadata')
                panel.get_by_role('button', name='Save Title').click()
                page.wait_for_function("document.querySelector('#readerTitle').textContent === 'Rejected title'")
                panel.get_by_role('button', name='Edit Author').click()
                panel.get_by_role('textbox', name='Author').fill('Changed author')
                panel.get_by_role('button', name='Save Author').click()
                panel.get_by_text('Changed author').wait_for()
                panel.get_by_role('button', name='Edit Title').click()
                panel.get_by_role('button', name='Edit Author').click()
                panel.get_by_role('textbox', name='Title').fill('Concurrent title')
                panel.get_by_role('textbox', name='Author').fill('Concurrent author')
                panel.evaluate("root => { root.querySelector('[aria-label=\"Save Title\"]').click(); root.querySelector('[aria-label=\"Save Author\"]').click(); }")
                page.wait_for_function('pendingCatalogMutation === 0 && !catalogLoading')
                saved = page.evaluate('async id => (await (await fetch(`/api/documents/${id}`)).json())', document_id)
                assert (saved['title'], saved['author']) == ('Concurrent title', 'Concurrent author'), saved
                assert page.locator('#readerTitle').inner_text() == 'Concurrent title'
                panel.get_by_role('button', name='Edit Stored filename').click()
                name = panel.get_by_role('textbox', name='Stored filename')
                name.fill('Renamed panel.pdf')
                name.press('Enter')
                panel.get_by_text('Renamed panel.pdf').wait_for()
                assert panel.get_by_text('Panel PDF.pdf').is_visible()
                panel.get_by_role('button', name='Edit Stored filename').click()
                panel.get_by_role('textbox', name='Stored filename').fill('Discarded.pdf')
                panel.get_by_role('button', name='Cancel Stored filename').click()
                assert panel.get_by_text('Renamed panel.pdf').is_visible()
                visibility = panel.get_by_label('Visibility')
                colors = []
                for theme in ('light', 'dark'):
                    page.evaluate('(theme) => document.documentElement.dataset.theme = theme', theme)
                    colors.append(visibility.evaluate('el => [getComputedStyle(el).color, getComputedStyle(el).backgroundColor, getComputedStyle(el.options[0]).backgroundColor]'))
                    assert colors[-1][1] == colors[-1][2] and colors[-1][0] != colors[-1][1]
                assert colors[0] != colors[1]
                page.locator('#readerClose').click()

                other_panel = open_document(page, other_id)
                assert 'is-minimized' not in other_panel.get_attribute('class')
                assert other_panel.locator('.document-download-split').count() == 1
                assert other_panel.get_by_role('button', name='Choose download format').count() == 0
                other_panel.get_by_role('button', name='Minimize document info').click()
                page.locator('#readerClose').click()
                panel = open_document(page, document_id)
                assert 'is-minimized' in panel.get_attribute('class')
                panel.get_by_role('button', name='Restore document info').click()
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
                mobile = open_document(phone, document_id)
                assert not mobile.get_by_label('Visibility').count()
                mobile.get_by_role('button', name='Minimize document info').tap()
                rail = mobile.bounding_box()
                reading = phone.locator('#readerScroll').bounding_box()
                assert 60 <= rail['width'] <= 70 and rail['x'] + rail['width'] <= reading['x']
                assert abs(rail['height'] - reading['height']) < 2 and reading['width'] >= 250
                assert mobile.get_by_role('button', name='Add to bookshelf').is_visible()
                assert mobile.get_by_role('button', name='Remove document').is_visible()
                phone.locator('#readerClose').tap()
                mobile = open_document(phone, document_id)
                assert 'is-minimized' in mobile.get_attribute('class')
                mobile.get_by_role('button', name='Restore document info').tap()
                assert 'is-minimized' not in mobile.get_attribute('class')
                phone.locator('#readerClose').tap()
                other_panel = open_document(page, other_id)
                confirmation = []
                page.once('dialog', lambda dialog: (confirmation.append(dialog.message), dialog.accept()))
                other_panel.get_by_role('button', name='Remove document').filter(visible=True).click()
                assert confirmation == ['Remove Other panel PDF?']
                page.locator(f'.document-card[data-document-id="{other_id}"]').wait_for(state='detached')
                browser.close()
            print('passed: reader document panel')
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == '__main__':
    main()
