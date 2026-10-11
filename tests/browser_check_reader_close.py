"""Browser regression for the reader close control, position, and focus."""

import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check_reader import open_card, port_number, seed, start_server
from test_documents import pdf_bytes


def check_close_control(page):
    button = page.get_by_role('button', name='Close reader')
    assert button.locator('svg[aria-hidden="true"]').count() == 1
    assert button.inner_text() == ''
    for theme in ('light', 'dark'):
        page.evaluate('(theme) => document.documentElement.dataset.theme = theme', theme)
        for width in (1000, 390, 320):
            page.set_viewport_size({'width': width, 'height': 750})
            page.mouse.move(width - 1, 749)
            button.evaluate('el => el.blur()')
            resting = button.evaluate('''el => {
              const button = el.getBoundingClientRect();
              const title = document.querySelector('#readerTitle').getBoundingClientRect();
              const style = getComputedStyle(el);
              return {width: button.width, height: button.height, right: button.right,
                centerY: (button.top + button.bottom) / 2,
                titleLeft: title.left, titleCenterY: (title.top + title.bottom) / 2,
                background: style.backgroundColor, border: style.borderTopColor,
                radius: style.borderRadius};
            }''')
            assert resting['width'] >= 44 and resting['height'] >= 44, (theme, width, resting)
            assert resting['background'] == 'rgba(0, 0, 0, 0)', (theme, width, resting)
            assert resting['border'] == 'rgba(0, 0, 0, 0)', (theme, width, resting)
            assert resting['radius'] == '50%', (theme, width, resting)
            assert 0 <= resting['titleLeft'] - resting['right'] <= 16, (theme, width, resting)
            assert abs(resting['titleCenterY'] - resting['centerY']) <= 5, (theme, width, resting)
            button.hover()
            hovered = button.evaluate('el => getComputedStyle(el).backgroundColor')
            assert hovered != resting['background'], (theme, width, hovered)
            page.mouse.move(width - 1, 749)
            button.focus()
            page.keyboard.press('Tab')
            page.keyboard.press('Shift+Tab')
            focused = button.evaluate('''el => ({visible: el.matches(':focus-visible'),
              outline: getComputedStyle(el).outlineStyle,
              background: getComputedStyle(el).backgroundColor})''')
            assert focused['visible'] and focused['outline'] != 'none', (theme, width, focused)
            assert focused['background'] == hovered, (theme, width, focused)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        base = f'http://127.0.0.1:{port}'
        process = start_server(folder, port)
        try:
            warning_id = None
            for title in ('Reader PDF', 'Mixed PDF', 'Warning PDF', 'Missing PDF'):
                document_id, _ = seed(folder, pdf_bytes(3 if title == 'Warning PDF' else 1), 'pdf', title)
                if title == 'Warning PDF':
                    warning_id = document_id
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 390, 'height': 300})
                page.goto(base + '/login')
                page.locator('#password').fill('reader-password')
                page.locator('#password_confirmation').fill('reader-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_url(base + '/')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 4")
                page.locator('#librarySearch').fill('PDF')
                card = page.locator('.document-card').filter(has_text='Warning PDF')
                button = card.locator('.document-open')
                for method in ('Close', 'Escape'):
                    button.scroll_into_view_if_needed()
                    page.evaluate('window.scrollTo(0, window.scrollY - 26)')
                    before = page.evaluate('window.scrollY')
                    assert before > 0, before
                    # Click the exposed part of the card without Playwright moving the page first.
                    bounds = button.bounding_box()
                    header_bottom = page.evaluate("document.querySelector('.app-header').getBoundingClientRect().bottom")
                    x = bounds['x'] + bounds['width'] / 2
                    y = max(bounds['y'] + 2, header_bottom + 2)
                    assert y < bounds['y'] + bounds['height'] - 2, bounds
                    page.mouse.click(x, y, click_count=1)
                    page.mouse.down(click_count=2)
                    page.mouse.up(click_count=2)
                    page.locator('#reader').wait_for(state='visible')
                    page.wait_for_function("document.querySelector('#readerPosition').textContent !== 'Opening…'")
                    assert page.evaluate('window.scrollY') == before
                    if method == 'Close':
                        check_close_control(page)
                        page.set_viewport_size({'width': 390, 'height': 300})
                        page.evaluate('(y) => window.scrollTo(0, y)', before)
                    page.evaluate('window.scrollTo(0, 0)')
                    assert page.evaluate('window.scrollY') == 0
                    if method == 'Close':
                        page.locator('#readerClose').click()
                    else:
                        page.keyboard.press('Escape')
                    page.wait_for_function("document.querySelector('#reader').hidden")
                    after = page.evaluate('window.scrollY')
                    assert page.locator('#librarySearch').input_value() == 'PDF'
                    assert page.evaluate("document.activeElement.closest('.document-card')?.dataset.documentId") == warning_id
                    assert abs(after - before) <= 2, f'{method}: before={before}, after={after}'
                page.set_viewport_size({'width': 390, 'height': 300})
                open_card(page, 'Warning PDF')
                page.locator('#readerNext').click()
                page.wait_for_function("document.querySelector('#readerPosition').textContent === 'Page 2 of 3'")
                page.locator('#readerClose').click()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    progress = page.request.get(base + f'/api/documents/{warning_id}/progress').json()['position']
                    if progress and progress['locator']['page'] == 2:
                        break
                    time.sleep(.05)
                else:
                    raise AssertionError('Closing the reader did not save page 2')
                open_card(page, 'Warning PDF')
                assert page.locator('#readerPosition').inner_text() == 'Page 2 of 3'
                page.keyboard.press('Escape')
                page.wait_for_function("document.querySelector('#reader').hidden")
                assert page.evaluate("document.activeElement.closest('.document-card')?.dataset.documentId") == warning_id
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
