"""Check document selection and reader opening in Chromium."""

import tempfile
import json
import sqlite3
import zipfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from browser_check_reader import port_number, seed, start_server
from test_documents import pdf_bytes


def card(page, title):
    return page.locator('.document-card').filter(has_text=title)


def click_selection(page, document_card):
    document_card.locator('.document-open').click()
    page.wait_for_timeout(550)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        server = start_server(folder, port)
        try:
            seed(folder, pdf_bytes(2), 'pdf', 'First PDF')
            seed(folder, pdf_bytes(2), 'pdf', 'Second PDF')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 900, 'height': 750})
                page.goto(f'http://127.0.0.1:{port}/login')
                page.locator('#password').fill('selection-password')
                page.locator('#password_confirmation').fill('selection-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 2")

                first = card(page, 'First PDF')
                second = card(page, 'Second PDF')
                first_star = first.locator('.document-star')
                assert first_star.get_attribute('aria-label') == 'Add to favorites'
                assert first_star.get_attribute('aria-pressed') == 'false'
                assert first_star.locator('svg path').count() == 1
                assert first_star.inner_text() == ''
                rest = first_star.evaluate("""button => {
                    const style = getComputedStyle(button);
                    const icon = getComputedStyle(button.querySelector('svg'));
                    return {background: style.backgroundColor, border: style.borderTopWidth,
                            shadow: style.boxShadow, color: style.color, fill: icon.fill,
                            width: button.getBoundingClientRect().width,
                            height: button.getBoundingClientRect().height};
                }""")
                assert rest['background'] == 'rgba(0, 0, 0, 0)' and rest['border'] == '0px'
                assert rest['shadow'] == 'none' and rest['fill'] == 'none'
                assert rest['width'] >= 40 and rest['height'] >= 40
                first_star.hover()
                hover = first_star.evaluate("""button => {
                    const style = getComputedStyle(button);
                    return {background: style.backgroundColor, color: style.color};
                }""")
                assert hover['background'] != rest['background'] and hover['color'] != rest['color']
                page.mouse.move(0, 0)
                page.evaluate("document.documentElement.dataset.theme = 'dark'")
                dark_rest = first_star.evaluate("button => ({background: getComputedStyle(button).backgroundColor, color: getComputedStyle(button).color})")
                assert dark_rest['background'] == rest['background']
                first_star.hover()
                dark_hover = first_star.evaluate("button => ({background: getComputedStyle(button).backgroundColor, color: getComputedStyle(button).color})")
                assert dark_hover['background'] != dark_rest['background'] and dark_hover['color'] != dark_rest['color']
                page.mouse.move(0, 0)
                page.evaluate("document.documentElement.dataset.theme = 'light'")
                page.keyboard.press('Tab')
                first_star.focus()
                assert first_star.evaluate("button => getComputedStyle(button).outlineStyle") != 'none'
                assert first.locator('.document-new-badge').is_visible()
                click_selection(page, first)
                assert page.locator('#reader').is_hidden(), 'Single click opened the reader'
                assert first.locator('.document-selection-badge').is_visible()
                assert first.locator('.document-new-badge').count() == 0
                assert first.locator('.document-open').get_attribute('aria-pressed') == 'true'
                first.locator('.document-open').focus()
                page.keyboard.press('Space')
                assert first.locator('.document-open').get_attribute('aria-pressed') == 'false'
                page.keyboard.press('Space')
                assert first.locator('.document-open').get_attribute('aria-pressed') == 'true'
                click_selection(page, second)
                assert second.locator('.document-selection-badge').is_visible()
                assert first.locator('.document-selection-badge').is_visible()
                assert page.locator('.document-selection-badge').count() == 2
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                click_selection(page, second)
                assert page.locator('.document-selection-badge').count() == 1
                assert second.locator('.document-new-badge').is_visible()
                click_selection(page, second)
                assert page.locator('.document-selection-badge').count() == 2
                first.locator('.document-preview').hover()
                page.locator('#previewBubble').wait_for(state='visible')
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                page.mouse.move(0, 0)
                page.locator('#previewBubble').wait_for(state='hidden')

                second.locator('.document-star').click()
                pressed_star = second.locator('.document-star')
                expect(pressed_star).to_have_attribute('aria-pressed', 'true')
                assert pressed_star.get_attribute('aria-label') == 'Remove from favorites'
                assert pressed_star.locator('svg path').get_attribute('d') == first_star.locator('svg path').get_attribute('d')
                assert pressed_star.locator('svg').evaluate("icon => getComputedStyle(icon).fill") != 'none'
                page.mouse.move(0, 0)
                assert pressed_star.evaluate("button => getComputedStyle(button).backgroundColor") == rest['background']
                assert second.locator('.document-selection-badge').is_visible()
                assert page.locator('#reader').is_hidden()
                second.locator('.document-open').dblclick()
                page.locator('#reader').wait_for(state='visible')
                assert page.locator('.document-selection-badge').count() == 2
                page.locator('#readerClose').click()

                click_selection(page, first)
                assert page.locator('#selectionCount').inner_text() == '1 selected'
                page.locator('#librarySearch').fill('Second')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 1")
                assert page.locator('.document-selection-badge').count() == 1
                page.locator('#librarySearch').fill('')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 2")
                assert card(page, 'First PDF').locator('.document-new-badge').is_visible()
                first.locator('.document-open').focus()
                page.keyboard.press('Enter')
                page.locator('#reader').wait_for(state='visible')
                assert page.locator('#selectionCount').inner_text() == '1 selected'
                page.locator('#readerClose').click()

                touch = browser.new_context(viewport={'width': 390, 'height': 750}, has_touch=True, is_mobile=True)
                touch.add_cookies(page.context.cookies())
                phone = touch.new_page()
                phone.goto(f'http://127.0.0.1:{port}/')
                phone.wait_for_function("document.querySelectorAll('.document-card').length === 2")
                phone_first = card(phone, 'First PDF')
                phone_star = phone_first.locator('.document-star')
                assert phone_star.is_visible()
                phone_star.tap()
                expect(phone_star).to_have_attribute('aria-pressed', 'true')
                assert phone_star.get_attribute('aria-label') == 'Remove from favorites'
                phone_first.locator('.document-open').tap()
                assert phone.locator('#reader').is_hidden()
                assert phone_first.locator('.document-selection-badge').is_visible()
                phone_second = card(phone, 'Second PDF')
                phone_second.locator('.document-open').tap()
                assert phone_first.locator('.document-selection-badge').is_visible()
                assert phone.locator('#selectionCount').inner_text() == '2 selected'
                assert phone.locator('.document-selected-open, .document-open-action').count() == 0
                assert phone.locator('#openSelected').is_disabled()
                phone.locator('#openSelectedDocument').select_option(phone_first.get_attribute('data-document-id'))
                phone.locator('#openSelected').tap()
                phone.locator('#reader').wait_for(state='visible')
                assert phone.locator('#selectionCount').inner_text() == '2 selected'
                phone.locator('#readerClose').tap()
                touch.close()

                for index in range(9):
                    seed(folder, pdf_bytes(1), 'pdf', f'Extra PDF {index}')
                page.reload()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 10")
                click_selection(page, page.locator('.document-card').first)
                assert page.locator('.document-selection-badge').count() == 1
                first_page_id = page.evaluate('[...selectedDocumentIds][0]')
                first_page_title = page.evaluate('(id) => selectedDocumentLabels.get(id)', first_page_id)
                page.locator('#pagerNext').click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.includes('Page 2 of 2')")
                assert page.locator('.document-selection-badge').count() == 0
                assert page.locator('#selectionCount').inner_text() == '1 selected'
                click_selection(page, page.locator('.document-card').first)
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                assert page.locator('#openSelected').is_disabled()
                page.locator('#openSelectedDocument').select_option(first_page_id)
                page.locator('#openSelected').click()
                page.locator('#reader').wait_for(state='visible')
                assert page.locator('#readerTitle').inner_text() == first_page_title
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                page.locator('#readerClose').click()
                page.locator('#pagerPrev').click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.includes('Page 1 of 2')")
                assert page.locator('.document-selection-badge').count() == 1
                page.locator('#librarySearch').fill('no matching document title')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 0")
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                page.locator('#librarySearch').fill('')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 10")
                page.locator('#sortToggle').click()
                page.locator('#sortField').select_option('title')
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.includes('Page 1 of 2')")
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                page.locator('#sortToggle').click()
                page.locator('#filtersToggle').click()
                page.locator('#filterType').select_option('epub')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 0")
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                page.locator('#filterType').select_option('')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 10")
                page.locator('#filtersToggle').click()
                page.evaluate('() => loadCatalog(false, true)')
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                page.locator('#accountMenuButton').click()
                page.locator('#settingsMenuItem').click()
                page.locator('#prefPageSize').select_option('endless')
                page.get_by_text('Items per page saved.').wait_for()
                page.locator('#settingsBack').click()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 11")
                assert page.locator('.document-selection-badge').count() == 2

                with page.expect_download() as download_event:
                    page.locator('#downloadSelected').click()
                archive_path = folder / 'selected.zip'
                download_event.value.save_as(str(archive_path))
                with zipfile.ZipFile(archive_path) as archive:
                    manifest = json.loads(archive.read('manifest.json'))
                    assert len(manifest['included']) == 2 and manifest['failures'] == []
                    assert len({item['filename'] for item in manifest['included']}) == 2
                page.locator('#clearSelection').click()
                assert page.locator('#selectionCount').inner_text() == '0 selected'
                assert page.locator('.document-selection-badge').count() == 0

                click_selection(page, page.locator('.document-card').first)
                click_selection(page, page.locator('.document-card').nth(1))
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                selected_ids = page.evaluate('[...selectedDocumentIds]')
                dialogs = []
                page.on('dialog', lambda dialog: (dialogs.append(dialog.message), dialog.accept()))
                page.route('**/api/documents/bulk/delete', lambda route: route.fulfill(
                    status=207, content_type='application/json', body=json.dumps({
                        'removed': selected_ids[:1],
                        'failures': [{'id': selected_ids[1], 'reason': 'cleanup_failed'}],
                        'remaining_document_ids': selected_ids[1:]})))
                page.locator('#deleteSelected').click()
                page.get_by_text('1 deleted; 1 failed.', exact=False).wait_for()
                assert page.locator('#selectionCount').inner_text() == '1 selected'
                assert page.evaluate('[...selectedDocumentIds]') == selected_ids[1:]
                page.unroute('**/api/documents/bulk/delete')
                page.locator('#clearSelection').click()
                click_selection(page, page.locator('.document-card').first)
                click_selection(page, page.locator('.document-card').nth(1))
                page.locator('#deleteSelected').click()
                page.wait_for_function("document.querySelector('#selectionCount').textContent === '0 selected'")
                assert dialogs == ['Delete 2 selected documents?', 'Delete 2 selected documents?']
                page.get_by_text('2 selected documents deleted.').wait_for()
                assert page.locator('#libraryNotice').inner_text() == '2 selected documents deleted.'
                assert page.locator('#libraryError').is_hidden()
                missing_ids = [f'missing_{index:03d}' for index in range(200)]
                page.evaluate("ids => { for (const id of ids) { selectedDocumentIds.add(id); selectedDocumentLabels.set(id, id); } updateSelectionActions(); }", missing_ids)
                with page.expect_download() as missing_download:
                    page.locator('#downloadSelected').click()
                missing_path = folder / 'missing-selected.zip'
                missing_download.value.save_as(str(missing_path))
                with zipfile.ZipFile(missing_path) as archive:
                    missing_manifest = json.loads(archive.read('manifest.json'))
                    assert len(missing_manifest['failures']) == 200
                page.wait_for_function("document.querySelector('#selectionCount').textContent === '0 selected'")
                assert missing_ids[0] in page.locator('#libraryError').inner_text()
                assert missing_ids[-1] in page.locator('#libraryError').inner_text()
                remaining = page.locator('.document-card').first
                remaining_id = remaining.get_attribute('data-document-id')
                remaining_title = remaining.locator('.document-copy h3').inner_text()
                click_selection(page, remaining)
                assert page.locator('#selectionCount').inner_text() == '1 selected'
                assert page.evaluate("""async ({id, title}) => (await fetch(`/api/documents/${id}`, {
                    method: 'DELETE', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({confirm: title})})).ok""", {'id': remaining_id, 'title': remaining_title})
                page.evaluate('() => loadCatalog()')
                assert page.locator('#selectionCount').inner_text() == '0 selected'

                assert page.evaluate("""async () => (await fetch('/api/users', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: 'reader', name: 'Reader', password: 'reader-password', role: 'normal'})
                })).ok""")
                reader_context = browser.new_context(viewport={'width': 900, 'height': 750})
                reader_page = reader_context.new_page()
                reader_page.goto(f'http://127.0.0.1:{port}/login')
                reader_page.locator('#username').fill('reader')
                reader_page.locator('#password').fill('reader-password')
                reader_page.get_by_role('button', name='Sign in').click()
                reader_page.wait_for_function("document.querySelectorAll('.document-card').length > 0")
                reader_card = reader_page.locator('.document-card').first
                revoked_id = reader_card.get_attribute('data-document-id')
                click_selection(reader_page, reader_card)
                assert reader_page.locator('#selectionCount').inner_text() == '1 selected'
                reader_page.on('dialog', lambda dialog: dialog.accept())
                reader_page.locator('#deleteSelected').click()
                reader_page.get_by_text('0 deleted; 1 failed.', exact=False).wait_for()
                assert reader_page.locator('#selectionCount').inner_text() == '1 selected'
                assert reader_card.locator('.document-selection-badge').is_visible()
                with sqlite3.connect(folder / 'library.db') as conn:
                    conn.execute("UPDATE documents SET visibility='private' WHERE id=?", (revoked_id,))
                reader_page.evaluate('() => loadCatalog()')
                assert reader_page.locator('#selectionCount').inner_text() == '0 selected'
                reader_context.close()
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == '__main__':
    main()
    print('selection: passed')
