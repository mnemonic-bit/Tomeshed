"""Browser regression checks for Bug 0045 pointer-exit dismissal."""

import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from browser_check_preview import numbered_pdf_bytes
from browser_check_reader import port_number, seed, start_server


def check_selection_dismissal(page, card, selected, outside=(0, 0)):
    cover = card.locator('.document-open')
    card.locator('.document-preview').hover()
    bubble = page.locator('#previewBubble')
    bubble.wait_for(state='visible')
    page.wait_for_function("document.querySelector('#previewContent img')?.complete")
    cover.click()
    expect(cover).to_have_attribute('aria-pressed', str(selected).lower())
    assert bubble.is_visible(), 'Selection closed preview while pointer remained on cover'
    page.mouse.move(*outside)
    expect(bubble).to_be_hidden(timeout=1500)
    expect(cover).to_have_attribute('aria-expanded', 'false')


def check_navigation_dismissal(page, card, endpoints=False):
    card.locator('.document-preview').hover()
    bubble = page.locator('#previewBubble')
    bubble.wait_for(state='visible')
    position = page.locator('#previewPosition')
    page.wait_for_function("document.querySelector('#previewContent img')?.complete")
    while page.locator('#previewPrevious').is_enabled():
        page.locator('#previewPrevious').click()
        page.wait_for_function("!document.querySelector('#previewNext').disabled")
    steps = [
        ('#previewNext', 'Page 2 of 4'),
        ('#previewNext', 'Page 3 of 4'),
        ('#previewPrevious', 'Page 2 of 4'),
        ('#previewNext', 'Page 3 of 4'),
    ]
    if endpoints:
        steps += [
            ('#previewNext', 'Page 4 of 4'),
            ('#previewPrevious', 'Page 3 of 4'),
            ('#previewPrevious', 'Page 2 of 4'),
            ('#previewPrevious', 'Page 1 of 4'),
        ]
    for control, label in steps:
        page.locator(control).click()
        expect(position).to_have_text(label)
    page.mouse.move(0, 0)
    expect(bubble).to_be_hidden(timeout=1500)


def check_keyboard_retention(page, card):
    page.mouse.move(0, 0)
    page.keyboard.press('Tab')
    cover = card.locator('.document-open')
    cover.focus()
    bubble = page.locator('#previewBubble')
    bubble.wait_for(state='visible')
    expect(page.locator('#previewNext')).to_be_focused()
    box = bubble.bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + 20)
    page.mouse.move(0, 0)
    assert bubble.is_visible(), 'Pointer exit closed a keyboard-focused preview'
    page.keyboard.press('Escape')
    expect(bubble).to_be_hidden()
    expect(cover).to_be_focused()
    page.wait_for_timeout(850)
    expect(bubble).to_be_hidden()


def check_keyboard_after_hover(page, card):
    page.locator('#librarySearch').focus()
    card.locator('.document-preview').hover()
    bubble = page.locator('#previewBubble')
    bubble.wait_for(state='visible')
    page.wait_for_function("document.querySelector('#previewContent img')?.complete")
    for _ in range(40):
        page.keyboard.press('Tab')
        if page.locator('#previewNext').evaluate('element => document.activeElement === element'):
            break
    expect(page.locator('#previewNext')).to_be_focused()
    page.mouse.move(0, 0)
    assert bubble.is_visible(), 'Pointer exit closed a preview after keyboard navigation'
    for _ in range(40):
        page.keyboard.press('Tab')
        if not bubble.is_visible():
            break
    expect(bubble).to_be_hidden()


def main():
    failures = []
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        process = start_server(folder, port)
        try:
            document_id, _ = seed(folder, numbered_pdf_bytes(4), 'pdf', 'Dismissal PDF')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1280, 'height': 800})
                page.goto(f'http://127.0.0.1:{port}/login')
                page.locator('#password').fill('preview-dismissal-password')
                page.locator('#password_confirmation').fill('preview-dismissal-password')
                page.get_by_role('button', name='Set password and open library').click()
                card = page.locator(f'.document-card[data-document-id="{document_id}"]')
                card.wait_for(state='visible')
                for name, check in (
                    ('select', lambda: check_selection_dismissal(page, card, True)),
                    ('deselect', lambda: check_selection_dismissal(page, card, False)),
                    ('select_viewport_exit', lambda: check_selection_dismissal(page, card, True, (-10, -10))),
                    ('deselect_viewport_exit', lambda: check_selection_dismissal(page, card, False, (-10, -10))),
                    ('page_navigation', lambda: check_navigation_dismissal(page, card)),
                    ('page_navigation_endpoints', lambda: check_navigation_dismissal(page, card, endpoints=True)),
                    ('keyboard_retention', lambda: check_keyboard_retention(page, card)),
                    ('keyboard_after_hover', lambda: check_keyboard_after_hover(page, card)),
                ):
                    try:
                        check()
                        print(f'{name}: passed', flush=True)
                    except AssertionError as error:
                        failures.append(f'{name}: failed: {error}')
                        print(f'{name}: failed', flush=True)
                    finally:
                        page.evaluate('window.tomeshedPreview.close()')
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)
    assert not failures, '\n\n'.join(failures)


if __name__ == '__main__':
    main()
    print('Bug 0045 browser preview dismissal checks passed')
