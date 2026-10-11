"""Browser regression check for PDF preview frame stability during paging."""

import json
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check_reader import mixed_pdf_bytes, port_number, seed, start_server


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        process = start_server(folder, port)
        try:
            pdf_id, _ = seed(folder, mixed_pdf_bytes(), 'pdf', 'Mixed Preview PDF')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1280, 'height': 800})
                page.goto(f'http://127.0.0.1:{port}/login')
                page.locator('#password').fill('preview-password')
                page.locator('#password_confirmation').fill('preview-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_function('document.querySelectorAll(".document-card").length === 1')
                page.evaluate('''id => {
                  const card = document.querySelector(`[data-document-id="${id}"]`);
                  window.tomeshedPreview.open(id, card, card.querySelector('.document-preview'),
                    card.querySelector('.document-open'), true);
                }''', pdf_id)
                page.wait_for_function('''() => {
                  const image = document.querySelector('#previewContent img');
                  return image?.complete && image.naturalWidth > 0;
                }''')
                before = page.locator('#previewBubble').bounding_box()['height']
                first_image = page.locator('#previewContent img').evaluate('image => [image.naturalWidth, image.naturalHeight]')
                page.evaluate(f'''() => {{
                  const originalFetch = window.fetch;
                  const gate = new Promise(resolve => window.releaseNextPreviewLocation = resolve);
                  window.fetch = (input, options) =>
                    String(input).endsWith('/api/documents/{pdf_id}/preview/location/1')
                      ? gate.then(() => originalFetch(input, options)) : originalFetch(input, options);
                }}''')
                def delay_image(route):
                    time.sleep(.35)
                    route.continue_()

                page.route(f'**/api/documents/{pdf_id}/preview/page/2', delay_image)
                page.evaluate('''() => {
                  const bubble = document.querySelector('#previewBubble');
                  window.previewFrameHeights = [bubble.getBoundingClientRect().height];
                  window.previewFrameObserver = new ResizeObserver(() => {
                    window.previewFrameHeights.push(bubble.getBoundingClientRect().height);
                  });
                  window.previewFrameObserver.observe(bubble);
                }''')
                page.locator('#previewNext').click()
                pending = page.evaluate('''() => ({
                  height: document.querySelector('#previewBubble').getBoundingClientRect().height,
                  image: document.querySelector('#previewContent img')?.getAttribute('src'),
                  position: document.querySelector('#previewPosition').textContent,
                  nextDisabled: document.querySelector('#previewNext').disabled
                })''')
                assert pending['height'] == before, pending
                assert pending['image'].endswith('/preview/page/1'), pending
                assert pending['position'] == 'Page 1 of 2' and pending['nextDisabled'], pending
                page.evaluate('window.releaseNextPreviewLocation()')
                page.wait_for_function('''() => {
                  const image = document.querySelector('#previewContent img');
                  return document.querySelector('#previewPosition').textContent.includes('Page 2 of 2') &&
                    image?.complete && image.naturalWidth > 0;
                }''')
                page.wait_for_timeout(50)
                result = page.evaluate('''() => {
                  window.previewFrameObserver.disconnect();
                  const bubble = document.querySelector('#previewBubble');
                  const image = document.querySelector('#previewContent img');
                  return {heights: window.previewFrameHeights, after: bubble.getBoundingClientRect().height,
                    image: [image.naturalWidth, image.naturalHeight], visible: !bubble.hidden,
                    readerClosed: document.querySelector('#reader').hidden};
                }''')
                assert result['visible'] and result['readerClosed'], result
                assert first_image != result['image'], (first_image, result)
                assert min(result['heights']) >= min(before, result['after']) - 8, (before, result)
                browser.close()
                print(json.dumps({'pdf_preview_frame': 'passed', 'before': before, **result}))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
