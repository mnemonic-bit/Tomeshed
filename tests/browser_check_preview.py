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
                progress_writes = []
                page.on('request', lambda req: progress_writes.append(req.url) if req.method == 'PUT' and req.url.endswith('/progress') else None)
                position = {'locator': {'page': 3, 'offset': .2}, 'percent': 60}
                with sqlite3.connect(folder / 'library.db') as conn:
                    conn.execute('INSERT INTO reading_positions(user_id,document_id,locator_json,percent,completed,updated_at) VALUES (1,?,?,?,?,?)',
                                 (pdf_id, json.dumps(position['locator']), position['percent'], 1, time.time()))
                pdf = card(page, 'Preview PDF')
                pdf.locator('.document-preview').hover()
                page.locator('#previewBubble').wait_for(state='visible')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 3")')
                page.wait_for_function("document.querySelector('#previewContent img')?.complete")
                assert page.locator('#previewContent img').is_visible()
                page3_image = page.locator('#previewContent img').screenshot()
                page.evaluate("document.querySelector('#librarySearch').focus()")
                assert page.locator('#previewBubble').is_visible()
                # Cross the space between the cover and its bubble.
                from_box = pdf.locator('.document-preview').bounding_box()
                to_box = page.locator('#previewNext').bounding_box()
                page.mouse.move(from_box['x'] + from_box['width'] / 2, from_box['y'] + from_box['height'] / 2)
                page.mouse.move(to_box['x'] + to_box['width'] / 2, to_box['y'] + to_box['height'] / 2, steps=12)
                assert page.locator('#previewBubble').is_visible()
                page.locator('#previewNext').click()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 4")')
                page.wait_for_function("document.querySelector('#previewContent img')?.complete")
                page4_image = page.locator('#previewContent img').screenshot()
                assert page3_image != page4_image
                assert page.locator('#previewNext').is_disabled()
                page.locator('#previewPrevious').click()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 3")')
                page.wait_for_function("document.querySelector('#previewContent img')?.complete")
                assert page.locator('#previewContent img').screenshot() == page3_image
                assert check_geometry(page)
                page.screenshot(path=str(ARTIFACTS / 'pdf-saved-1280.png'))
                assert page.evaluate(f'''async () => await (await fetch('/api/documents/{pdf_id}/progress')).json()''') == {'position': position, 'completed': True}
                assert not progress_writes
                page.mouse.move(0, 0)
                page.locator('#previewBubble').wait_for(state='hidden')
                pdf.locator('.document-open').click()
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
                    page.locator('#previewClose').click()
                checks['warning_preserved_source'] = 'passed'

                epub = card(page, 'Preview EPUB')
                epub.get_by_role('button', name='Preview Preview EPUB').focus()
                page.keyboard.press('Enter')
                page.locator('#previewBubble').wait_for(state='visible')
                assert page.locator('#previewClose').evaluate('e => document.activeElement === e')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.startsWith("Location 1 of ")')
                assert page.locator('#previewPosition').inner_text().startswith('Location 1 of ')
                assert page.locator('#previewPrevious').is_disabled()
                page.keyboard.press('Tab'); assert page.locator('#previewNext').evaluate('e => document.activeElement === e')
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
                assert epub.locator('.document-preview-action').evaluate('e => document.activeElement === e')
                assert page.evaluate(f'''async () => await (await fetch('/api/documents/{epub_id}/progress')).json()''') == {'position': None, 'completed': False}
                assert not progress_writes
                epub_saved = {'locator': {'section': 'OPS/second.xhtml', 'element': 2, 'offset': .1}, 'percent': 80}
                assert page.evaluate(f'''async data => (await fetch('/api/documents/{epub_id}/progress', {{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}})).ok''', epub_saved)
                epub.locator('.document-preview').hover()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 2 of 3")')
                assert 'word' in page.locator('#previewContent').inner_text()
                page.locator('#previewClose').click()
                checks['epub_keyboard_unread'] = 'passed'

                docling = card(page, 'Preview Docling')
                docling.locator('.document-preview').hover()
                page.locator('#previewBubble').wait_for(state='visible')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 1")')
                assert '<script' not in page.locator('#previewContent').inner_html()
                page.locator('#previewNext').click()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 2")')
                checks['docling_slice'] = 'passed'
                # A point in the enclosing rectangle, outside both the card and bubble, must close.
                gap = page.evaluate('''() => {const b=document.querySelector('#previewBubble').getBoundingClientRect();
                  const a=document.querySelector('.document-card [aria-expanded="true"]').closest('.document-card').querySelector('.document-preview').getBoundingClientRect();
                  return {x:(a.right+b.left)/2,y:b.top+12};}''')
                page.mouse.move(gap['x'], gap['y'])
                page.locator('#previewBubble').wait_for(state='hidden')
                checks['pointer_leave'] = 'passed'
                docling_saved = {'locator': {'element': '#/texts/1', 'offset': .1}, 'percent': 30}
                assert page.evaluate(f'''async data => (await fetch('/api/documents/{docling_id}/progress', {{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}})).ok''', docling_saved)
                docling.locator('.document-preview').hover()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 2")')
                page.locator('#previewClose').click()
                checks['saved_epub_docling'] = 'passed'

                # An old image error must not replace content under another card.
                pdf.locator('.document-preview').hover()
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Page 3")')
                page.evaluate("window.oldPreviewImage = document.querySelector('#previewContent img')")
                page.evaluate(f'''() => {{const card=document.querySelector('.document-card[data-document-id="{docling_id}"]');
                  window.tomeshedPreview.open('{docling_id}',card,card.querySelector('.document-preview'),card.querySelector('.document-preview-action'),true);}}''')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 2")')
                page.evaluate("window.oldPreviewImage.dispatchEvent(new Event('error'))")
                assert 'Preview unavailable' not in page.locator('#previewContent').inner_text()
                checks['stale_image_error'] = 'passed'

                # The preview route fails while the preserved source remains readable.
                page.evaluate('window.tomeshedPreview.close()')
                page.route(f'**/api/documents/{pdf_id}/preview', lambda route: route.fulfill(status=503, body='unavailable'))
                pdf.locator('.document-preview').hover()
                page.wait_for_function('document.querySelector("#previewContent").textContent.includes("Preview unavailable")')
                pdf.locator('.document-open').click()
                page.locator('#reader').wait_for(state='visible')
                page.locator('#readerClose').click()
                page.unroute(f'**/api/documents/{pdf_id}/preview')
                checks['failure_reader_available'] = 'passed'

                # Switching cards ignores a late response from the first card.
                page.evaluate(f'''() => {{ const original=window.fetch; window.fetch=(input, options) => {{
                  if (String(input).endsWith('/api/documents/{pdf_id}/preview'))
                    return new Promise(resolve => setTimeout(() => resolve(original(input, options)), 450));
                  return original(input, options);
                }}; }}''')
                pdf.locator('.document-preview').hover()
                page.evaluate(f'''() => {{const card=document.querySelector('.document-card[data-document-id="{epub_id}"]');
                  window.tomeshedPreview.open('{epub_id}',card,card.querySelector('.document-preview'),card.querySelector('.document-preview-action'),true);}}''')
                page.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 2 of 3")')
                page.wait_for_timeout(600)
                assert page.locator('#previewPosition').inner_text().startswith('Location 2 of 3')
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
                        page.locator('#previewClose').click()
                checks['edge_placement'] = 'passed'
                page.set_viewport_size({'width': 390, 'height': 800})
                page.evaluate('window.scrollTo(0, 0)')
                page.mouse.move(0, 0)
                first_card = page.locator('.document-card').first
                first_card.locator('.document-preview').hover()
                page.locator('#previewBubble').wait_for(state='visible')
                page.mouse.wheel(0, 600)
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
                phone.get_by_role('button', name='Preview Preview EPUB').tap()
                phone.locator('#previewBubble').wait_for(state='visible')
                phone.locator('#previewNext').tap()
                phone.wait_for_function('document.querySelector("#previewPosition").textContent.includes("Location 3")')
                phone.locator('#previewClose').tap()
                assert not phone.locator('#previewBubble').is_visible()
                checks['touch'] = 'passed'
                touch.close(); browser.close()
        finally:
            process.terminate(); process.wait(timeout=10)
    (ARTIFACTS / 'report.json').write_text(json.dumps(checks, indent=2) + '\n')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
