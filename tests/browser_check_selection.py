"""Check document selection and reader opening in Chromium."""

import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check_reader import port_number, seed, start_server
from test_documents import pdf_bytes


def card(page, title):
    return page.locator('.document-card').filter(has_text=title)


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
                assert first.locator('.document-new-badge').is_visible()
                first.locator('.document-open').click()
                assert page.locator('#reader').is_hidden(), 'Single click opened the reader'
                assert first.locator('.document-selection-badge').is_visible()
                assert first.locator('.document-new-badge').count() == 0
                assert first.locator('.document-open').get_attribute('aria-pressed') == 'true'
                second.locator('.document-open').click()
                assert second.locator('.document-selection-badge').is_visible()
                assert first.locator('.document-new-badge').is_visible()
                assert page.locator('.document-selection-badge').count() == 1
                second.locator('.document-open').click()
                assert page.locator('.document-selection-badge').count() == 0
                assert second.locator('.document-new-badge').is_visible()
                second.locator('.document-open').click()

                second.locator('.document-star').click()
                assert second.locator('.document-selection-badge').is_visible()
                assert page.locator('#reader').is_hidden()
                second.locator('.document-open').dblclick()
                page.locator('#reader').wait_for(state='visible')
                assert page.locator('.document-selection-badge').count() == 0
                page.locator('#readerClose').click()

                first.locator('.document-open').click()
                page.locator('#librarySearch').fill('Second')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 1")
                assert page.locator('.document-selection-badge').count() == 0
                page.locator('#librarySearch').fill('')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 2")
                assert card(page, 'First PDF').locator('.document-new-badge').is_visible()
                first.locator('.document-open').focus()
                page.keyboard.press('Enter')
                page.locator('#reader').wait_for(state='visible')
                page.locator('#readerClose').click()

                touch = browser.new_context(viewport={'width': 390, 'height': 750}, has_touch=True, is_mobile=True)
                touch.add_cookies(page.context.cookies())
                phone = touch.new_page()
                phone.goto(f'http://127.0.0.1:{port}/')
                phone.wait_for_function("document.querySelectorAll('.document-card').length === 2")
                phone_first = card(phone, 'First PDF')
                phone_first.locator('.document-open').tap()
                assert phone.locator('#reader').is_hidden()
                assert phone_first.locator('.document-selection-badge').is_visible()
                phone_first.locator('.document-selected-open').tap()
                phone.locator('#reader').wait_for(state='visible')
                phone.locator('#readerClose').tap()
                touch.close()

                for index in range(9):
                    seed(folder, pdf_bytes(1), 'pdf', f'Extra PDF {index}')
                page.reload()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 10")
                page.locator('.document-card').first.locator('.document-open').click()
                assert page.locator('.document-selection-badge').count() == 1
                page.locator('#pagerLast').click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.includes('Page 2 of 2')")
                assert page.locator('.document-selection-badge').count() == 0
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == '__main__':
    main()
    print('selection: passed')
