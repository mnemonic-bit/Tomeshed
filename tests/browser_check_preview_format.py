"""Browser checks for Bug 0025 preview sizing by displayed content."""

import io
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfWriter

from browser_check_reader import port_number, seed, start_server
from test_preview import two_section_epub
from test_reader import docling_fixture


def mixed_a4_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_blank_page(width=842, height=595)
    writer.add_blank_page(width=420, height=842)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def wait_for_layout(page, expected_ratio=None):
    page.wait_for_function("""expectedRatio => {
      const bubble = document.querySelector('#previewBubble');
      const content = document.querySelector('#previewContent');
      const child = content.firstElementChild;
      if (bubble.hidden || !child || document.querySelector('#previewPosition').textContent.includes('Loading')) return false;
      const images = [...content.querySelectorAll('img')];
      if (images.some(image => !image.complete || !image.naturalWidth)) return false;
      if (expectedRatio !== null &&
          (child.tagName !== 'IMG' || Math.abs(child.naturalWidth / child.naturalHeight - expectedRatio) >= .01)) return false;
      const header = document.querySelector('.app-header').getBoundingClientRect();
      const footer = document.querySelector('#versionFooter').getBoundingClientRect();
      const available = Math.min(innerHeight - 12, footer.top - 8) - Math.max(12, header.bottom + 8);
      const bubbleHeight = bubble.getBoundingClientRect().height;
      const childHeight = child.getBoundingClientRect().height;
      const target = childHeight + bubbleHeight - content.clientHeight;
      return target <= available + 2
        ? Math.abs(content.clientHeight - childHeight) <= 3
        : Math.abs(bubbleHeight - available) <= 3 && content.scrollHeight > content.clientHeight;
    }""", arg=expected_ratio)


def open_preview(page, document_id, expected_ratio=None):
    card = page.locator(f'.document-card[data-document-id="{document_id}"]')
    card.scroll_into_view_if_needed()
    page.evaluate("""id => {
      const card = document.querySelector(`.document-card[data-document-id="${id}"]`);
      window.tomeshedPreview.open(id, card, card.querySelector('.document-preview'),
                                  card.querySelector('.document-open'), true);
    }""", document_id)
    page.locator('#previewBubble').wait_for(state='visible')
    wait_for_layout(page, expected_ratio)


def geometry(page):
    return page.evaluate("""() => {
      const bubble = document.querySelector('#previewBubble');
      const content = document.querySelector('#previewContent');
      const child = content.firstElementChild;
      const rect = bubble.getBoundingClientRect();
      const header = document.querySelector('.app-header').getBoundingClientRect();
      const footer = document.querySelector('#versionFooter').getBoundingClientRect();
      const topBound = Math.max(12, header.bottom + 8);
      const bottomBound = Math.min(innerHeight - 12, footer.top - 8);
      return {height: rect.height, width: rect.width, top: rect.top, bottom: rect.bottom,
        left: rect.left, right: rect.right, viewportWidth: innerWidth,
        available: bottomBound - topBound, topBound, bottomBound,
        contentHeight: content.clientHeight, contentScrollHeight: content.scrollHeight,
        childHeight: child.getBoundingClientRect().height,
        childWidth: child.getBoundingClientRect().width,
        naturalWidth: child.naturalWidth || null, naturalHeight: child.naturalHeight || null,
        controlsBottom: document.querySelector('.preview-controls').getBoundingClientRect().bottom};
    }""")


def assert_sized_to_content(values):
    chrome = values['height'] - values['contentHeight']
    target = values['childHeight'] + chrome
    if values['naturalWidth']:
        assert abs(values['childWidth'] / values['childHeight'] - values['naturalWidth'] / values['naturalHeight']) < .02, values
    assert values['top'] >= values['topBound'] - 1 and values['bottom'] <= values['bottomBound'] + 1, values
    assert values['left'] >= -1 and values['right'] <= values['viewportWidth'] + 1, values
    assert values['controlsBottom'] <= values['bottom'] - 1, values
    if target <= values['available'] + 2:
        assert abs(values['contentHeight'] - values['childHeight']) <= 3, values
    else:
        assert abs(values['height'] - values['available']) <= 3, values
        assert values['contentScrollHeight'] > values['contentHeight'], values


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        process = start_server(folder, port)
        try:
            pdf_id, _ = seed(folder, mixed_a4_pdf(), 'pdf', 'Format PDF')
            epub_id, _ = seed(folder, two_section_epub(), 'epub', 'Format EPUB')
            docling_id, _ = seed(folder, docling_fixture(extra=5), 'docling', 'Format Docling')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1280, 'height': 1200})
                page.goto(f'http://127.0.0.1:{port}/login')
                page.locator('#password').fill('preview-format-password')
                page.locator('#password_confirmation').fill('preview-format-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 3")

                open_preview(page, pdf_id, 595 / 842)
                portrait = geometry(page)
                assert abs(portrait['naturalWidth'] / portrait['naturalHeight'] - 595 / 842) < .01, portrait
                assert_sized_to_content(portrait)
                page.locator('#previewNext').click()
                page.wait_for_function("document.querySelector('#previewPosition').textContent.includes('Page 2')")
                wait_for_layout(page, 842 / 595)
                landscape = geometry(page)
                assert abs(landscape['naturalWidth'] / landscape['naturalHeight'] - 842 / 595) < .01, landscape
                assert_sized_to_content(landscape)
                assert portrait['height'] > landscape['height'] + 100, (portrait, landscape)
                page.locator('#previewNext').click()
                page.wait_for_function("document.querySelector('#previewPosition').textContent.includes('Page 3')")
                wait_for_layout(page, 420 / 842)
                assert_sized_to_content(geometry(page))

                for document_id in (epub_id, docling_id):
                    page.evaluate('window.tomeshedPreview.close()')
                    open_preview(page, document_id)
                    assert page.locator('#previewContent .preview-excerpt').count() == 1
                    assert_sized_to_content(geometry(page))

                page.evaluate('window.tomeshedPreview.close()')
                page.set_viewport_size({'width': 390, 'height': 400})
                open_preview(page, pdf_id, 595 / 842)
                compact = geometry(page)
                assert_sized_to_content(compact)
                assert compact['contentScrollHeight'] > compact['contentHeight'], compact
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
    print('Bug 0025 browser preview format checks passed')
