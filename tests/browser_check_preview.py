"""Feature 0004 Chromium acceptance checks with preserved-source fixtures."""

import json
import sqlite3
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
import io

from browser_check_reader import ROOT, port_number, seed, start_server
from test_documents import pdf_bytes
from test_preview import two_section_epub
from test_reader import docling_fixture

ARTIFACTS = Path('/tmp/tomeshed-feature-0004-browser')
ARTIFACTS.mkdir(exist_ok=True)


def numbered_pdf_bytes(pages=4):
    writer = PdfWriter()
    for number in range(1, pages + 1):
        page = writer.add_blank_page(width=300, height=400)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
            NameObject('/F1'): DictionaryObject({
                NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
                NameObject('/BaseFont'): NameObject('/Helvetica')})})})
        shade = number / (pages + 1)
        commands = f'{shade:.3f} 0.35 0.75 rg 20 20 260 360 re f\n0 0 0 rg BT /F1 36 Tf 65 190 Td (PAGE {number}) Tj ET'
        stream = DecodedStreamObject(); stream.set_data(commands.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    output = io.BytesIO(); writer.write(output)
    return output.getvalue()


def card(page, title):
    return page.locator('.document-card').filter(has_text=title)


def bubble_geometry(page):
    return page.locator('#previewBubble').evaluate('''element => {
      const r=element.getBoundingClientRect(), h=document.querySelector('.app-header').getBoundingClientRect(),
        f=document.querySelector('#versionFooter').getBoundingClientRect(), a=document.querySelector('.document-card [aria-expanded="true"]').closest('.document-card').querySelector('.document-preview').getBoundingClientRect();
      return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,header:h.bottom,footer:f.top,
        side:element.dataset.side,pointer:parseFloat(getComputedStyle(element).getPropertyValue('--preview-pointer-y'))+r.top,
        anchorY:a.top+a.height/2};}''')


def check_geometry(page):
    result = bubble_geometry(page)
    assert result['left'] >= 0 and result['right'] <= result['width'], result
    assert result['top'] >= result['header'] and result['bottom'] <= result['footer'], result
    assert abs(result['pointer'] - result['anchorY']) <= 18 or result['anchorY'] < result['top'] or result['anchorY'] > result['bottom'], result
    return result


def check_hover_dwell(page, pdf, pdf_id):
    bubble = page.locator('#previewBubble')
    thumbnail = pdf.locator('.document-preview')
    requests = []
    endpoint = f'/api/documents/{pdf_id}/preview'
    page.on('request', lambda request: requests.append(request.url) if request.url.endswith(endpoint) else None)

    page.mouse.move(0, 0)
    thumbnail.hover()
    page.wait_for_timeout(250)
    assert not bubble.is_visible() and not requests, 'Preview opened before 800 ms'
    page.mouse.move(0, 0)
    page.wait_for_timeout(850)
    assert not bubble.is_visible() and not requests, 'Preview opened after pointer exit'

    thumbnail.hover()
    page.wait_for_timeout(250)
    pdf.evaluate('(card) => card.hidden = true')
    page.wait_for_timeout(850)
    assert not bubble.is_visible() and not requests, 'Hidden card opened preview'
    pdf.evaluate('(card) => card.hidden = false')
    page.mouse.move(0, 0)

    thumbnail.hover()
    page.wait_for_timeout(250)
    page.mouse.down()
    page.wait_for_timeout(850)
    assert not bubble.is_visible() and not requests, 'Drag opened preview'
    page.mouse.move(0, 0)
    page.mouse.up()

    thumbnail.hover()
    page.wait_for_timeout(250)
    pdf.locator('.document-open').dblclick(delay=100)
    page.locator('#reader').wait_for(state='visible')
    page.wait_for_timeout(850)
    assert not bubble.is_visible() and not requests, 'Reader open left preview pending'
    page.locator('#readerClose').click()
    page.locator('#reader').wait_for(state='hidden')
    page.locator('#librarySearch').focus()
    page.mouse.move(0, 0)

    thumbnail.evaluate('''(element, endpoint) => {
      window.previewHoverStart = null;
      window.previewFetchDelay = null;
      element.addEventListener('pointermove', () => { window.previewHoverStart = performance.now(); }, {once: true, capture: true});
      window.previewOriginalFetch = window.fetch;
      window.fetch = (...args) => {
        if (String(args[0]).endsWith(endpoint)) window.previewFetchDelay = performance.now() - window.previewHoverStart;
        return window.previewOriginalFetch(...args);
      };
    }''', endpoint)
    thumbnail.hover()
    page.wait_for_timeout(500)
    box = thumbnail.bounding_box()
    page.mouse.move(box['x'] + box['width'] * .6, box['y'] + box['height'] * .6)
    page.wait_for_timeout(200)
    assert not bubble.is_visible() and not requests, 'Movement shortened dwell'
    bubble.wait_for(state='visible', timeout=350)
    assert len(requests) == 1, f'Expected one initial preview request, got {len(requests)}'
    assert page.evaluate('window.previewFetchDelay >= 800'), 'Preview request started before 800 ms'
    page.evaluate('window.fetch = window.previewOriginalFetch')
    page.mouse.move(0, 0)
    bubble.wait_for(state='hidden')


def main():
    checks = {}
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number(); base = f'http://127.0.0.1:{port}'
        process = start_server(folder, port)
        try:
            pdf_id, _ = seed(folder, numbered_pdf_bytes(4), 'pdf', 'Preview PDF')
            epub_id, _ = seed(folder, two_section_epub(), 'epub', 'Preview EPUB')
            docling_id, _ = seed(folder, docling_fixture(extra=5), 'docling', 'Preview Docling')
            warning_pdf_id, _ = seed(folder, pdf_bytes(2), 'pdf', 'Warning PDF', 'ready_with_warning')
            warning_epub_id, _ = seed(folder, two_section_epub(), 'epub', 'Warning EPUB', 'ready_with_warning')
            for number in range(3):
                seed(folder, pdf_bytes(1), 'pdf', f'Edge {number} PDF')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(viewport={'width': 1280, 'height': 800}, has_touch=True)
                page = context.new_page()
                page.goto(base + '/login')
                page.locator('#password').fill('preview-password')
                page.locator('#password_confirmation').fill('preview-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_url(base + '/')
                page.wait_for_function('document.querySelectorAll(".document-card").length >= 8')
                assert page.locator('.document-preview-action').count() == 0, 'Cards still show Preview buttons'
                progress_writes = []
                page.on('request', lambda req: progress_writes.append(req.url) if req.method == 'PUT' and req.url.endswith('/progress') else None)
                position = {'locator': {'page': 3, 'offset': .2}, 'percent': 60}
                with sqlite3.connect(folder / 'library.db') as conn:
                    conn.execute('INSERT INTO reading_positions(user_id,document_id,locator_json,percent,completed,updated_at) VALUES (1,?,?,?,?,?)',
                                 (pdf_id, json.dumps(position['locator']), position['percent'], 1, time.time()))
                pdf = card(page, 'Preview PDF')
                check_hover_dwell(page, pdf, pdf_id)
                checks['hover_dwell'] = 'passed'
                pdf.locator('.document-preview').hover()
                page.locator('#previewBubble').wait_for(state='visible')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 1")')
                page.wait_for_function("document.querySelector('#previewContent img')?.complete")
                assert page.locator('#previewContent img').is_visible()
                page1_image = page.locator('#previewContent img').screenshot()
                page.evaluate("document.querySelector('#librarySearch').focus()")
                assert page.locator('#previewBubble').is_visible()
                # Cross the space between the cover and its bubble.
                from_box = pdf.locator('.document-preview').bounding_box()
                to_box = page.locator('#previewNext').bounding_box()
                page.mouse.move(from_box['x'] + from_box['width'] / 2, from_box['y'] + from_box['height'] / 2)
                page.mouse.move(to_box['x'] + to_box['width'] / 2, to_box['y'] + to_box['height'] / 2, steps=12)
                assert page.locator('#previewBubble').is_visible()
                page.locator('#previewNext').click()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 2")')
                page.locator('#previewNext').click()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 3")')
                page.locator('#previewNext').click()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 4")')
                page.wait_for_function("document.querySelector('#previewContent img')?.complete")
                page4_image = page.locator('#previewContent img').screenshot()
                assert page1_image != page4_image
                assert page.locator('#previewNext').is_disabled()
                page.locator('#previewPrevious').click()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 3")')
                page.locator('#previewPrevious').click()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 2")')
                page.wait_for_function("document.querySelector('#previewContent img')?.complete")
                assert check_geometry(page)
                page.screenshot(path=str(ARTIFACTS / 'pdf-saved-1280.png'))
                assert page.evaluate(f'''async () => await (await fetch('/api/documents/{pdf_id}/progress')).json()''') == {'position': position, 'completed': True}
                assert not progress_writes
                page.mouse.move(0, 0)
                page.locator('#previewBubble').wait_for(state='hidden')
                card(page, 'Warning PDF').locator('.document-preview').hover()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 1")')
                page.evaluate('window.tomeshedPreview.close()')
                pdf.locator('.document-preview').hover()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 2")')
                page.mouse.move(0, 0)
                page.locator('#previewBubble').wait_for(state='hidden')
                pdf.locator('.document-open').dblclick()
                page.locator('#reader').wait_for(state='visible')
                page.wait_for_function('document.querySelector("#readerPosition").textContent.includes("Page 3")')
                assert not page.locator('#previewBubble').is_visible()
                page.locator('#readerClose').click()
                checks['pdf_saved_navigation_reader_isolation'] = 'passed'
                checks['hover_with_background_focus'] = 'passed'

                for title in ('Warning PDF', 'Warning EPUB'):
                    item = card(page, title)
                    item.locator('.document-preview').hover()
                    page.locator('#previewBubble').wait_for(state='visible')
                    page.wait_for_function('document.querySelector("#previewPosition").textContent.includes(" of ")')
                    assert 'Preview unavailable' not in page.locator('#previewContent').inner_text()
                    page.evaluate('window.tomeshedPreview.close()')
                checks['warning_preserved_source'] = 'passed'

                epub = card(page, 'Preview EPUB')
                page.keyboard.press('Tab')
                epub.locator('.document-open').focus()
                assert epub.locator('.document-open').evaluate("e => e.matches(':focus-visible')")
                page.wait_for_timeout(250)
                assert not page.locator('#previewBubble').is_visible(), 'Keyboard focus opened preview before 800 ms'
                page.locator('#previewBubble').wait_for(state='visible')
                assert page.locator('#previewNext').evaluate('e => document.activeElement === e')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.startsWith("Location 1 of ")')
                assert page.locator('#previewPosition').inner_text().startswith('Location 1 of ')
                assert page.locator('#previewPrevious').is_disabled()
                assert page.locator('#previewNext').evaluate("e => getComputedStyle(e).outlineStyle !== 'none'")
                page.keyboard.press('Enter')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 2")')
                assert 'Second chapter' in page.locator('#previewContent').inner_text()
                assert not page.locator('#previewNext').is_disabled()
                page.locator('#previewNext').click()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 3")')
                assert page.locator('#previewNext').is_disabled()
                page.keyboard.press('Escape')
                assert not page.locator('#previewBubble').is_visible()
                assert epub.locator('.document-open').evaluate('e => document.activeElement === e')
                page.wait_for_timeout(850)
                assert not page.locator('#previewBubble').is_visible(), 'Restored focus reopened preview'
                assert page.evaluate(f'''async () => await (await fetch('/api/documents/{epub_id}/progress')).json()''') == {'position': None, 'completed': False}
                assert not progress_writes
                epub_saved = {'locator': {'section': 'OPS/second.xhtml', 'element': 2, 'offset': .1}, 'percent': 80}
                assert page.evaluate(f'''async data => (await fetch('/api/documents/{epub_id}/progress', {{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}})).ok''', epub_saved)
                epub.locator('.document-preview').hover()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 3 of 3")')
                assert 'word' in page.locator('#previewContent').inner_text()
                page.evaluate('window.tomeshedPreview.close()')
                checks['epub_keyboard_unread'] = 'passed'

                docling = card(page, 'Preview Docling')
                docling.locator('.document-preview').hover()
                page.locator('#previewBubble').wait_for(state='visible')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 1")')
                assert '<script' not in page.locator('#previewContent').inner_html()
                page.locator('#previewNext').click()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 2")')
                checks['docling_slice'] = 'passed'
                # Moving beyond the card and bubble without preview focus must close it.
                page.locator('#librarySearch').focus()
                page.mouse.move(0, 0)
                page.locator('#previewBubble').wait_for(state='hidden')
                checks['pointer_leave'] = 'passed'
                docling_saved = {'locator': {'element': '#/texts/1', 'offset': .1}, 'percent': 30}
                assert page.evaluate(f'''async data => (await fetch('/api/documents/{docling_id}/progress', {{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}})).ok''', docling_saved)
                docling.locator('.document-preview').hover()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 2")')
                page.evaluate('window.tomeshedPreview.close()')
                checks['saved_epub_docling'] = 'passed'

                # An old image error must not replace content under another card.
                pdf.locator('.document-preview').hover()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 2")')
                page.evaluate("window.oldPreviewImage = document.querySelector('#previewContent img')")
                page.evaluate(f'''() => {{const card=document.querySelector('.document-card[data-document-id="{docling_id}"]');
                  window.tomeshedPreview.open('{docling_id}',card,card.querySelector('.document-preview'),card.querySelector('.document-open'),true);}}''')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 2")')
                page.evaluate("window.oldPreviewImage.dispatchEvent(new Event('error'))")
                assert 'Preview unavailable' not in page.locator('#previewContent').inner_text()
                checks['stale_image_error'] = 'passed'

                # The preview route fails while the preserved source remains readable.
                page.evaluate('window.tomeshedPreview.close()')
                page.route(f'**/api/documents/{pdf_id}/preview?index=1', lambda route: route.fulfill(status=503, body='unavailable'))
                pdf.locator('.document-preview').hover()
                page.wait_for_function('document.querySelector("#previewContent").textContent.includes("Preview unavailable")')
                pdf.locator('.document-open').dblclick()
                page.locator('#reader').wait_for(state='visible')
                page.locator('#readerClose').click()
                page.unroute(f'**/api/documents/{pdf_id}/preview?index=1')
                checks['failure_reader_available'] = 'passed'

                # Switching cards ignores a late response from the first card.
                page.evaluate(f'''() => {{ const original=window.fetch; window.fetch=(input, options) => {{
                  if (String(input).endsWith('/api/documents/{pdf_id}/preview?index=1'))
                    return new Promise(resolve => setTimeout(() => resolve(original(input, options)), 450));
                  return original(input, options);
                }}; }}''')
                pdf.locator('.document-preview').hover()
                page.evaluate(f'''() => {{const card=document.querySelector('.document-card[data-document-id="{epub_id}"]');
                  window.tomeshedPreview.open('{epub_id}',card,card.querySelector('.document-preview'),card.querySelector('.document-open'),true);}}''')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 3 of 3")')
                page.wait_for_timeout(600)
                assert page.locator('#previewPosition').inner_text().startswith('Location 3 of 3')
                checks['stale_response'] = 'passed'
                page.locator('#librarySearch').fill('No such book')
                page.wait_for_function('document.querySelectorAll(".document-card").length === 0')
                assert not page.locator('#previewBubble').is_visible()
                checks['filter_close'] = 'passed'
                page.locator('#librarySearch').fill('')
                page.wait_for_function('document.querySelectorAll(".document-card").length >= 8')

                for width in (390, 1280):
                    page.set_viewport_size({'width': width, 'height': 800})
                    cards = page.locator('.document-card')
                    for index in (0, min(cards.count() - 1, 4 if width == 1280 else 1)):
                        item = cards.nth(index)
                        page.evaluate('window.tomeshedPreview.close()')
                        page.mouse.move(0, 0)
                        item.locator('.document-preview').hover()
                        page.locator('#previewBubble').wait_for(state='visible')
                        page.wait_for_function('!document.querySelector("#previewPosition").textContent.includes("Loading")')
                        check_geometry(page)
                        page.screenshot(path=str(ARTIFACTS / f'edge-{width}-{index}.png'))
                        page.evaluate('window.tomeshedPreview.close()')
                checks['edge_placement'] = 'passed'
                page.set_viewport_size({'width': 390, 'height': 800})
                page.evaluate('window.scrollTo(0, 0)')
                page.mouse.move(0, 0)
                first_card = page.locator('.document-card').first
                first_card.locator('.document-preview').hover()
                page.locator('#previewBubble').wait_for(state='visible')
                page.evaluate('''() => {
                  const anchor = document.querySelector('.document-card .document-preview').getBoundingClientRect();
                  const header = document.querySelector('.app-header').getBoundingClientRect().bottom;
                  window.scrollBy(0, Math.ceil(anchor.bottom - header + 20));
                }''')
                page.wait_for_function('''() => {
                  const a=document.querySelector('.document-card .document-preview').getBoundingClientRect();
                  const header=document.querySelector('.app-header').getBoundingClientRect().bottom;
                  return a.bottom <= header;
                }''')
                page.locator('#previewBubble').wait_for(state='hidden')
                checks['scroll_origin_offscreen'] = 'passed'
                touch = browser.new_context(viewport={'width': 390, 'height': 800}, has_touch=True, is_mobile=True)
                touch.add_cookies(context.cookies())
                phone = touch.new_page(); phone.goto(base + '/')
                phone.wait_for_function('document.querySelectorAll(".document-card").length >= 8')
                phone_cover = card(phone, 'Preview EPUB').locator('.document-open')
                assert phone_cover.get_attribute('aria-controls') == 'previewBubble'
                assert phone_cover.get_attribute('aria-expanded') == 'false'
                phone_cover.scroll_into_view_if_needed()
                box = phone_cover.bounding_box()
                assert box['y'] >= 0 and box['y'] + box['height'] <= 800, box
                x = box['x'] + box['width'] / 2; y = box['y'] + box['height'] / 2
                cdp = touch.new_cdp_session(phone)
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
                phone.wait_for_timeout(250)
                assert not phone.locator('#previewBubble').is_visible(), 'Touch opened preview before 800 ms'
                phone.locator('#previewBubble').wait_for(state='visible')
                assert phone_cover.get_attribute('aria-expanded') == 'true'
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                assert not phone.locator('#reader').is_visible(), 'Touch hold opened the reader'
                assert phone.locator('.document-selection-badge').count() == 0, 'Touch hold selected a document'
                phone.locator('#previewNext').tap()
                phone.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 2")')
                phone.locator('#versionFooter').tap()
                assert not phone.locator('#previewBubble').is_visible()
                assert phone_cover.get_attribute('aria-expanded') == 'false'
                assert phone_cover.evaluate('e => document.activeElement === e'), 'Touch close did not restore thumbnail focus'
                assert phone.evaluate(f'''async () => await (await fetch('/api/documents/{epub_id}/progress')).json()''')['position'] == epub_saved
                phone_cover.tap()
                assert not phone.locator('#reader').is_visible(), 'Short tap opened the reader'
                phone.locator('#openSelected').tap()
                phone.locator('#reader').wait_for(state='visible')
                assert not phone.locator('#previewBubble').is_visible(), 'Short tap left the preview open'
                phone.locator('#readerClose').tap()
                checks['touch'] = 'passed'
                touch.close(); browser.close()
        finally:
            process.terminate(); process.wait(timeout=10)
    (ARTIFACTS / 'report.json').write_text(json.dumps(checks, indent=2) + '\n')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
