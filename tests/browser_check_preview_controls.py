"""Browser checks for Bug 0038 preview controls and spacing."""

import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check_preview import numbered_pdf_bytes
from browser_check_reader import port_number, seed, start_server
from test_preview import two_section_epub


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        process = start_server(folder, port)
        try:
            pdf_id, _ = seed(folder, numbered_pdf_bytes(3), 'pdf', 'Control PDF')
            epub_id, _ = seed(folder, two_section_epub(), 'epub', 'Control EPUB')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1280, 'height': 800})
                page.goto(f'http://127.0.0.1:{port}/login')
                page.locator('#password').fill('preview-controls-password')
                page.locator('#password_confirmation').fill('preview-controls-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 2")
                card = page.locator(f'.document-card[data-document-id="{pdf_id}"]')
                card.locator('.document-preview').hover()
                page.wait_for_function("document.querySelector('#previewPosition').textContent.includes('Page 1')")
                page.wait_for_function("document.querySelector('#previewContent img')?.complete")
                assert page.locator('#previewClose, #previewBubble .preview-toolbar').count() == 0
                assert page.locator('#previewBubble .preview-position-row').count() == 1
                assert page.locator('#previewPrevious').is_disabled()
                assert page.locator('#previewPrevious').get_attribute('aria-label') == 'Previous preview location'
                assert page.locator('#previewNext').get_attribute('aria-label') == 'Next preview location'
                layout = page.locator('#previewBubble').evaluate("""bubble => {
                  const box = selector => bubble.querySelector(selector).getBoundingClientRect().toJSON();
                  return {bubble:bubble.getBoundingClientRect().toJSON(), page:box('#previewContent img'),
                    position:box('.preview-position-row'), previousHit:box('.preview-nav-previous'),
                    previousButton:box('#previewPrevious'), nextHit:box('.preview-nav-next'),
                    nextButton:box('#previewNext')};
                }""")
                assert abs((layout['page']['top'] - layout['bubble']['top']) -
                           (layout['page']['left'] - layout['bubble']['left'])) <= 2, layout
                assert layout['page']['bottom'] <= layout['position']['top'], layout
                for side in ('previous', 'next'):
                    hit = layout[side + 'Hit']; button = layout[side + 'Button']
                    assert abs(hit['width'] - 2 * button['width']) <= 1, layout
                    assert abs(hit['height'] - 2 * button['height']) <= 1, layout
                    assert abs((hit['x'] + hit['width'] / 2) -
                               (button['x'] + button['width'] / 2)) <= 1, layout
                    assert abs((hit['y'] + hit['height'] / 2) -
                               (button['y'] + button['height'] / 2)) <= 1, layout
                stage = page.locator('.preview-stage').bounding_box()
                page.mouse.move(stage['x'] + stage['width'] / 2, stage['y'] + 20)
                assert page.locator('#previewNext').evaluate('button => getComputedStyle(button).opacity === "0"')
                hit = layout['nextHit']
                page.mouse.move(hit['x'] + 2, hit['y'] + hit['height'] / 2)
                assert page.locator('#previewNext').evaluate('button => getComputedStyle(button).opacity === "1"')
                button = layout['nextButton']
                page.mouse.move(button['x'] + button['width'] / 2, button['y'] + button['height'] / 2)
                assert page.locator('#previewNext').evaluate('button => getComputedStyle(button).opacity === "1"')
                page.mouse.click(button['x'] + button['width'] / 2, button['y'] + button['height'] / 2)
                page.wait_for_function("document.querySelector('#previewPosition').textContent.includes('Page 2')")
                assert not page.locator('#previewPrevious').is_disabled()
                page.locator('#previewNext').click()
                page.wait_for_function("document.querySelector('#previewPosition').textContent.includes('Page 3')")
                assert page.locator('#previewNext').is_disabled()
                page.locator('#previewPrevious').click()
                page.wait_for_function("document.querySelector('#previewPosition').textContent.includes('Page 2')")
                page.locator('#librarySearch').focus()
                page.mouse.move(0, 0)
                page.locator('#previewBubble').wait_for(state='hidden')

                page.set_viewport_size({'width': 390, 'height': 800})
                epub = page.locator(f'.document-card[data-document-id="{epub_id}"]')
                epub.locator('.document-preview').hover()
                page.wait_for_function("document.querySelector('#previewPosition').textContent.startsWith('Location 1 of ')")
                bounds = page.locator('#previewBubble').bounding_box()
                assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= 390, bounds
                assert page.locator('#previewNext').is_enabled()
                assert page.locator('.preview-position-row').is_visible()
                excerpt_layout = page.locator('.preview-stage').evaluate("""stage => {
                  const outer = stage.getBoundingClientRect();
                  const hit = stage.querySelector('.preview-nav-next').getBoundingClientRect();
                  return {stageTop:outer.top, stageBottom:outer.bottom, hitTop:hit.top, hitBottom:hit.bottom};
                }""")
                assert excerpt_layout['hitTop'] >= excerpt_layout['stageTop'] - 1, excerpt_layout
                assert excerpt_layout['hitBottom'] <= excerpt_layout['stageBottom'] + 1, excerpt_layout

                hybrid = browser.new_context(viewport={'width': 1280, 'height': 800}, has_touch=True)
                hybrid.add_cookies(page.context.cookies())
                hybrid_page = hybrid.new_page()
                hybrid_page.goto(f'http://127.0.0.1:{port}/')
                hybrid_card = hybrid_page.locator(f'.document-card[data-document-id="{pdf_id}"]')
                hybrid_card.locator('.document-preview').hover()
                hybrid_page.wait_for_function("document.querySelector('#previewPosition').textContent.includes('Page 1')")
                hybrid_stage = hybrid_page.locator('.preview-stage').bounding_box()
                hx = hybrid_stage['x'] + hybrid_stage['width'] / 2
                hy = hybrid_stage['y'] + 20
                hybrid_page.mouse.move(hx, hy)
                assert hybrid_page.locator('#previewNext').evaluate('button => getComputedStyle(button).opacity === "0"')
                hybrid_page.evaluate("""point => document.elementFromPoint(point.x, point.y).dispatchEvent(
                  new PointerEvent('pointermove', {bubbles:true, pointerType:'pen', clientX:point.x, clientY:point.y}))""",
                                     {'x': hx, 'y': hy})
                assert hybrid_page.locator('#previewBubble').get_attribute('data-pointer-type') == 'pen'
                assert hybrid_page.locator('#previewNext').evaluate('button => getComputedStyle(button).opacity === "0"')
                cdp = hybrid.new_cdp_session(hybrid_page)
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': hx, 'y': hy}]})
                assert hybrid_page.locator('#previewNext').evaluate('button => getComputedStyle(button).opacity === "1"')
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                hybrid_page.mouse.move(hx + 3, hy)
                assert hybrid_page.locator('#previewNext').evaluate('button => getComputedStyle(button).opacity === "0"')
                hybrid_page.evaluate('window.tomeshedPreview.close()')
                cover = hybrid_card.locator('.document-open').bounding_box()
                cx = cover['x'] + cover['width'] / 2
                cy = cover['y'] + cover['height'] / 2
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': cx, 'y': cy}]})
                hybrid_page.locator('#previewBubble').wait_for(state='visible', timeout=2500)
                assert hybrid_page.locator('#previewNext').evaluate('button => getComputedStyle(button).opacity === "1"')
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                hybrid_stage = hybrid_page.locator('.preview-stage').bounding_box()
                hybrid_page.mouse.move(hybrid_stage['x'] + hybrid_stage['width'] / 2, hybrid_stage['y'] + 20)
                assert hybrid_page.locator('#previewNext').evaluate('button => getComputedStyle(button).opacity === "0"')
                hybrid.close()
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
    print('Bug 0038 browser preview controls checks passed')
