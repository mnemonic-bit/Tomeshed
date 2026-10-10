"""Preserved-source preview boundaries and progress isolation."""

import io
import json
import sqlite3
import zipfile
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter

from test_documents import module, pdf_bytes, signed_in
from test_reader import add_document, docling_fixture, epub_fixture


def two_section_epub():
    data = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(epub_fixture())) as original, zipfile.ZipFile(data, 'w') as result:
        for name in original.namelist():
            if name == 'OPS/book.opf':
                text = original.read(name).decode().replace('</manifest>', '<item id="second" href="second.xhtml" media-type="application/xhtml+xml"/></manifest>')
                text = text.replace('</spine>', '<itemref idref="second"/></spine>')
                result.writestr(name, text)
            else:
                result.writestr(name, original.read(name))
        result.writestr('OPS/second.xhtml', '<html><body><p>Second chapter</p><p>' + 'word ' * 500 + '</p></body></html>')
    return data.getvalue()


def test_pdf_saved_position_cache_resolution_access_and_progress(module):
    client = signed_in(module)
    anonymous = module.app.test_client()
    document_id = add_document(module, pdf_bytes(4), 'pdf')
    base = f'/api/documents/{document_id}'
    assert anonymous.get(f'{base}/preview').status_code == 401
    assert anonymous.get(f'{base}/preview/page/1').status_code == 401
    assert anonymous.get(f'{base}/preview/location/0').status_code == 401
    assert client.get(f'{base}/preview').json['page'] == 1
    assert client.get(f'{base}/progress').json == {'position': None, 'completed': False}
    saved = {'locator': {'page': 3, 'offset': .2}, 'percent': 60}
    assert client.put(f'{base}/progress', json=saved).status_code == 200
    assert client.post(f'{base}/finish').status_code == 200
    initial = client.get(f'{base}/preview').json
    assert (initial['page'], initial['index'], initial['total']) == (3, 2, 4)
    assert client.get(f'{base}/preview/location/1').json['page'] == 2
    assert client.get(f'{base}/preview/location/4').status_code == 404
    module.app.config.update(PREVIEW_PDF_MAX_WIDTH=160, PREVIEW_CACHE_LOCATIONS=2)
    import preview_service
    original = preview_service.pdfium.PdfDocument
    rendered = []

    class CountedPage:
        def __init__(self, page, number):
            self.page, self.number = page, number

        def get_size(self):
            return self.page.get_size()

        def render(self, *args, **kwargs):
            rendered.append(self.number)
            return self.page.render(*args, **kwargs)

    class CountedPdf:
        def __init__(self, source):
            self.pdf = original(source)

        def __len__(self):
            return len(self.pdf)

        def __getitem__(self, index):
            return CountedPage(self.pdf[index], index + 1)

        def close(self):
            self.pdf.close()

    with patch.object(preview_service.pdfium, 'PdfDocument', side_effect=CountedPdf):
        first = client.get(f'{base}/preview/page/3')
        second = client.get(f'{base}/preview/page/3')
        assert rendered == [3]
        assert client.get(f'{base}/preview/page/1').status_code == 200
        assert client.get(f'{base}/preview/page/2').status_code == 200
        assert client.get(f'{base}/preview/page/3').status_code == 200
        assert rendered == [3, 1, 2, 3]
    assert first.status_code == second.status_code == 200
    image = Image.open(io.BytesIO(first.data))
    assert image.width <= 160
    assert client.get(f'{base}/progress').json == {'position': saved, 'completed': True}
    assert client.get('/static/preview-page-3.png').status_code != 200
    stored = module.document_library.root / 'sources' / f'{document_id}.source'
    stored.write_bytes(pdf_bytes(2))
    shortened = client.get(f'{base}/preview').json
    assert shortened['page'] == 2 and shortened['approximate'] is True
    stored.write_bytes(pdf_bytes(4))
    with module.db() as conn:
        conn.execute('UPDATE documents SET source_path=? WHERE id=?', ('../../etc/passwd', document_id))
    assert client.get(f'{base}/preview').status_code == 404
    assert client.get(f'{base}/preview/page/3').status_code == 404


def test_epub_one_section_per_location_limits_warning_and_approximate(module):
    client = signed_in(module)
    document_id = add_document(module, two_section_epub(), 'epub')
    base = f'/api/documents/{document_id}'
    with module.db() as conn:
        conn.execute('UPDATE documents SET state=? WHERE id=?', ('ready_with_warning', document_id))
    module.app.config.update(PREVIEW_TEXT_CHARS=120, PREVIEW_IMAGE_LIMIT=0, PREVIEW_CACHE_LOCATIONS=2)
    import preview_service
    original = preview_service.EpubSanitizer.feed
    fed = []

    def counted(self, data):
        fed.append(self.section)
        return original(self, data)

    with patch.object(preview_service.EpubSanitizer, 'feed', counted):
        initial = client.get(f'{base}/preview').json
        assert fed == ['OPS/chapter.xhtml']
        assert client.get(f'{base}/preview/location/0').status_code == 200
        assert fed == ['OPS/chapter.xhtml']
    assert initial['total'] > 2 and initial['index'] == 0 and initial['label'].startswith('Location')
    assert initial['characters'] <= 120 and initial['images'] == 0 and '<img' not in initial['html']
    saved = {'locator': {'section': 'OPS/second.xhtml', 'element': 2, 'offset': .3}, 'percent': 75}
    assert client.put(f'{base}/progress', json=saved).status_code == 200
    start = client.get(f'{base}/preview').json
    assert start['index'] > 1 and 'word' in start['html'] and 'Second chapter' not in start['html']
    assert client.get(f'{base}/progress').json['position'] == saved
    assert client.get(f'{base}/preview/location/2').json['index'] == 2
    assert client.get(f'{base}/preview/location/{initial["total"] - 1}').json['index'] == initial['total'] - 1
    assert client.get(f'{base}/preview/location/{initial["total"]}').status_code == 404
    with module.db() as conn:
        conn.execute('UPDATE reading_positions SET locator_json=? WHERE document_id=?',
                     (json.dumps({'section': 'removed.xhtml', 'element': 2, 'offset': .3}), document_id))
    assert client.get(f'{base}/preview').json['approximate'] is True


def test_docling_slice_escaping_and_saved_reference(module):
    client = signed_in(module)
    document_id = add_document(module, docling_fixture(extra=6), 'docling')
    base = f'/api/documents/{document_id}'
    module.app.config['PREVIEW_TEXT_CHARS'] = 110
    first = client.get(f'{base}/preview').json
    assert first['total'] > 8 and first['characters'] <= 110
    assert '<script' not in first['html'] and '&lt;script&gt;' in first['html']
    position = {'locator': {'element': '#/texts/1', 'offset': .5}, 'percent': 70}
    assert client.put(f'{base}/progress', json=position).status_code == 200
    selected = client.get(f'{base}/preview').json
    assert selected['element'] == '#/texts/1' and selected['index'] > 0
    assert selected['characters'] <= 110 and selected['images'] == 0
    assert client.get(f'{base}/progress').json['position'] == position
    with module.db() as conn:
        conn.execute('UPDATE reading_positions SET locator_json=? WHERE document_id=?',
                     (json.dumps({'element': '#/removed/1', 'offset': .5}), document_id))
    assert client.get(f'{base}/preview').json['approximate'] is True


def test_docling_cache_bound_evicts_old_location(module):
    client = signed_in(module)
    document_id = add_document(module, docling_fixture(extra=6), 'docling')
    base = f'/api/documents/{document_id}/preview/location/'
    module.app.config['PREVIEW_CACHE_LOCATIONS'] = 2
    import preview_service
    original = preview_service.DoclingDocument.model_validate_json
    with patch.object(preview_service.DoclingDocument, 'model_validate_json', wraps=original) as parse:
        for index in (0, 0, 1, 2, 0):
            assert client.get(base + str(index)).status_code == 200
        assert parse.call_count == 5


def test_long_single_section_and_element_have_reachable_last_chunks(module):
    client = signed_in(module)
    module.app.config['PREVIEW_TEXT_CHARS'] = 100
    epub_id = add_document(module, epub_fixture(text='word ' * 500), 'epub')
    docling_id = add_document(module, docling_fixture(text=''.join(f'{number:04d} ' for number in range(500)), extra=0), 'docling')
    for document_id, kind in ((epub_id, 'epub'), (docling_id, 'docling')):
        base = f'/api/documents/{document_id}/preview'
        first = client.get(base).json
        assert first['format'] == kind and first['total'] > 2
        assert first['characters'] <= 100
        next_result = client.get(f'{base}/location/1').json
        last = client.get(f'{base}/location/{first["total"] - 1}').json
        assert next_result['index'] == 1 and last['index'] == first['total'] - 1
        assert next_result['html'] != first['html']
        assert client.get(f'{base}/location/{first["total"]}').status_code == 404


def test_epub_saved_mid_paragraph_and_publisher_page_marker(module):
    client = signed_in(module)
    source = epub_fixture(text=''.join(f'{number:04d} ' for number in range(600)))
    stream = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(stream, 'w') as changed:
        for name in original.namelist():
            if name == 'OPS/chapter.xhtml':
                markup = original.read(name).decode().replace('<p>', '<span role="doc-pagebreak" aria-label="12"></span><p>', 1)
                changed.writestr(name, markup)
            else:
                changed.writestr(name, original.read(name))
    document_id = add_document(module, stream.getvalue(), 'epub')
    base = f'/api/documents/{document_id}'
    module.app.config['PREVIEW_TEXT_CHARS'] = 100
    saved = {'locator': {'section': 'OPS/chapter.xhtml', 'element': 2, 'offset': .5}, 'percent': 50}
    assert client.put(f'{base}/progress', json=saved).status_code == 200
    initial = client.get(f'{base}/preview').json
    assert initial['index'] > 1 and initial['approximate'] is False
    assert initial['label'].startswith('Page 12 · Location ')
    assert '0000' not in initial['html']
    assert any(f'{number:04d}' in initial['html'] for number in range(295, 315))


def test_extremely_tall_pdf_is_rendered_within_both_dimension_limits(module):
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=20_000)
    output = io.BytesIO(); writer.write(output)
    client = signed_in(module)
    document_id = add_document(module, output.getvalue(), 'pdf')
    module.app.config.update(PREVIEW_PDF_MAX_WIDTH=160, PREVIEW_PDF_MAX_HEIGHT=360)
    response = client.get(f'/api/documents/{document_id}/preview/page/1')
    assert response.status_code == 200
    image = Image.open(io.BytesIO(response.data))
    assert 1 <= image.width <= 160 and 1 <= image.height <= 360
