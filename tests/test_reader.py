"""Reading content, saved positions, and authorization checks."""

import importlib
import io
import json
import time
import uuid
import zipfile
from html.parser import HTMLParser

from docling_core.types.doc import BoundingBox, DocItemLabel, DoclingDocument, ProvenanceItem, Size, TableCell, TableData
from PIL import Image

from test_documents import module, pdf_bytes, signed_in


def add_document(app_module, source, kind, title='Reader fixture'):
    document_id = uuid.uuid4().hex
    stored = f'sources/{document_id}.source'
    (app_module.document_library.root / stored).write_bytes(source)
    with app_module.db() as conn:
        conn.execute('''INSERT INTO documents(id,original_filename,source_path,source_type,title,author,byte_size,
            search_key,count_kind,state,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (document_id, f'fixture.{kind}', stored, kind, title, 'Test author', len(source), title.casefold(),
             'exact' if kind == 'pdf' else 'unknown', 'ready', time.time()))
    return document_id


def epub_fixture(chapter_name='chapter.xhtml', text='Paragraph one'):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('mimetype', 'application/epub+zip')
        archive.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
        archive.writestr('OPS/book.opf', f'''<package><manifest>
            <item id="chapter" href="{chapter_name.replace('"', '&quot;')}" media-type="application/xhtml+xml"/>
            <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
            <item id="image" href="image.png" media-type="image/png"/>
            </manifest><spine><itemref idref="chapter"/></spine></package>''')
        archive.writestr(f'OPS/{chapter_name}', f'''<html><body><h1 id="first">Chapter</h1>
            <p>{text}</p><img src="image.png" alt="Reading illustration"/>
            <script>window.epubAttack=1</script><a href="javascript:alert(1)" onclick="bad()">Unsafe link</a>
            </body></html>''')
        archive.writestr('OPS/nav.xhtml', '<html><body><nav><a href="chapter.xhtml#first">Chapter one</a></nav></body></html>')
        image = io.BytesIO()
        Image.new('RGB', (4, 4), '#286e48').save(image, format='PNG')
        archive.writestr('OPS/image.png', image.getvalue())
    return stream.getvalue()


def docling_fixture(text='<script>window.doclingAttack=1</script>', extra=25):
    doc = DoclingDocument(name='Structured fixture')
    doc.add_page(page_no=1, size=Size(width=300, height=400))
    doc.add_title(text, prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=0, t=0, r=200, b=100), charspan=(0, len(text))))
    doc.add_title('Second element')
    for index in range(extra):
        doc.add_text(DocItemLabel.TEXT, f'Paragraph {index + 1} ' + 'word ' * 45)
    return json.dumps(doc.export_to_dict()).encode()


class AttributeCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.attributes.append((tag, dict(attrs)))


def test_pdf_position_validation_restart_shorter_source_and_two_users(module):
    first = signed_in(module)
    second_user = first.post('/api/users', json={'username': 'reader2', 'password': 'reader-password', 'role': 'normal'}).json
    second = module.app.test_client()
    assert second.post('/login', data={'username': 'reader2', 'password': 'reader-password'}).status_code == 302
    anonymous = module.app.test_client()
    document_id = add_document(module, pdf_bytes(9), 'pdf')
    base = f'/api/documents/{document_id}'
    assert first.get(f'{base}/reader').json['page_count'] == 9
    assert first.get(f'{base}/reader/page/7').status_code == 200
    assert anonymous.get(f'{base}/reader').status_code == 401
    assert anonymous.get(f'{base}/reader/page/7').status_code == 401
    assert anonymous.get(f'{base}/source').status_code == 401
    assert anonymous.get(f'{base}/progress').status_code == 401
    assert anonymous.put(f'{base}/progress', json={'locator': {'page': 7, 'offset': .4}, 'percent': 70}).status_code == 401
    expected = {'locator': {'page': 7, 'offset': .4}, 'percent': 70}
    assert first.put(f'{base}/progress', json=expected).status_code == 200
    assert second.put(f'{base}/progress', json={'locator': {'page': 2, 'offset': .2}, 'percent': 15}).status_code == 200
    assert first.get(f'{base}/progress').json['position'] == expected
    assert second.get(f'{base}/progress').json['position']['locator']['page'] == 2
    for malformed in ({'locator': {'page': 10, 'offset': .4}, 'percent': 70},
                      {'locator': {'page': 7, 'offset': 1.1}, 'percent': 70},
                      {'locator': {'page': True, 'offset': .4}, 'percent': 70},
                      {'locator': {'page': 7, 'offset': .4}, 'percent': float('nan')},
                      {'locator': {'page': 7, 'offset': .4, 'extra': 1}, 'percent': 70}):
        assert first.put(f'{base}/progress', json=malformed).status_code == 400
        assert first.get(f'{base}/progress').json['position'] == expected
    assert first.post(f'{base}/finish').json['completed'] is True
    assert first.get(f'{base}/progress').json == {'position': expected, 'completed': True}
    assert second.get(f'{base}/progress').json['completed'] is False
    assert first.post(f'{base}/start-over').json == {'position': None, 'completed': False}
    assert first.get(f'{base}/progress').json['position'] is None
    assert second.get(f'{base}/progress').json['position']['locator']['page'] == 2
    assert first.put(f'{base}/progress', json=expected).status_code == 200
    reloaded = importlib.reload(module)
    resumed = reloaded.app.test_client()
    assert resumed.post('/login', data={'username': 'admin', 'password': 'secret-password'}).status_code == 302
    assert resumed.get(f'{base}/progress').json['position'] == expected
    path = reloaded.document_library.root / 'sources' / f'{document_id}.source'
    path.write_bytes(pdf_bytes(4))
    assert resumed.get(f'{base}/reader').json['page_count'] == 4
    assert resumed.get(f'{base}/progress').json['position'] == expected
    path.unlink()
    assert resumed.get(f'{base}/reader').json['state'] == 'source_missing'
    assert resumed.put(f'{base}/progress', json={'locator': {'page': 1, 'offset': 0}, 'percent': 0}).status_code == 404
    assert resumed.get(f'{base}/progress').json['position'] == expected
    assert second_user['id'] != 1


def test_epub_source_order_toc_resource_sanitization_and_invalid_locator(module):
    client = signed_in(module)
    source = epub_fixture()
    document_id = add_document(module, source, 'epub')
    base = f'/api/documents/{document_id}'
    response = client.get(f'{base}/reader')
    assert response.status_code == 200
    content = response.json
    assert content['sections'][0]['html'].index('Chapter') < content['sections'][0]['html'].index('Paragraph one') < content['sections'][0]['html'].index('Reading illustration')
    assert content['toc'][0]['label'] == 'Chapter one'
    assert content['sections'][0]['anchors']['first'] == 1
    markup = content['sections'][0]['html']
    collector = AttributeCollector(); collector.feed(markup)
    assert not any(name.startswith('on') or value.lower().startswith('javascript:') for _, attrs in collector.attributes for name, value in attrs.items())
    assert '<script' not in markup
    assert client.get(f'{base}/reader/resource?path=OPS/image.png').data.startswith(b'\x89PNG')
    assert client.get(f'{base}/reader/resource?path=../secret.png').status_code == 404
    position = {'locator': {'section': 'OPS/chapter.xhtml', 'element': 2, 'offset': .35}, 'percent': 45}
    assert client.put(f'{base}/progress', json=position).status_code == 200
    assert client.get(f'{base}/progress').json['position'] == position
    assert client.put(f'{base}/progress', json={'locator': {'section': 'OPS/chapter.xhtml', 'element': 99, 'offset': 0}, 'percent': 80}).status_code == 400
    assert client.get(f'{base}/progress').json['position'] == position
    (module.document_library.root / 'sources' / f'{document_id}.source').write_bytes(epub_fixture(text='Changed paragraph'))
    assert client.get(f'{base}/progress').json['position'] == position


def test_epub_member_name_cannot_add_html_attributes(module):
    client = signed_in(module)
    malicious = 'a" onload="window.attack=1.xhtml'
    document_id = add_document(module, epub_fixture(chapter_name=malicious), 'epub')
    response = client.get(f'/api/documents/{document_id}/reader')
    assert response.status_code == 200
    markup = response.json['sections'][0]['html']
    collector = AttributeCollector(); collector.feed(markup)
    assert not any(name.startswith('on') for _, attrs in collector.attributes for name in attrs)
    assert any(attrs.get('id') == 'loc-0-1' for _, attrs in collector.attributes)


def test_docling_html_escaping_stable_page_and_element_position(module):
    client = signed_in(module)
    document_id = add_document(module, docling_fixture(), 'docling')
    base = f'/api/documents/{document_id}'
    content = client.get(f'{base}/reader').json
    assert content['format'] == 'docling'
    assert content['elements'][0]['page'] == 1
    assert content['elements'][1]['page'] is None
    assert '&lt;script&gt;' in content['elements'][0]['html']
    assert '<script' not in content['elements'][0]['html']
    position = {'locator': {'element': '#/texts/1', 'offset': .5}, 'percent': 80}
    assert client.put(f'{base}/progress', json=position).status_code == 200
    assert client.get(f'{base}/progress').json['position'] == position
    assert client.put(f'{base}/progress', json={'locator': {'element': '#/texts/99', 'offset': .2}, 'percent': 80}).status_code == 400
    source = module.document_library.root / 'sources' / f'{document_id}.source'
    source.write_bytes(docling_fixture('Replacement heading'))
    assert client.get(f'{base}/progress').json['position'] == position
    source.write_bytes(b'{bad json')
    assert client.get(f'{base}/reader').json['state'] == 'rendering_error'
    assert client.get(f'{base}/progress').json['position'] == position


def test_docling_table_cell_is_escaped_and_malformed_epub_is_a_reader_state(module):
    client = signed_in(module)
    doc = DoclingDocument(name='Table fixture')
    doc.add_table(TableData(num_rows=1, num_cols=1, table_cells=[TableCell(
        start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=0, end_col_offset_idx=1,
        text='<img src=x onerror="window.attack=1">')]))
    table_id = add_document(module, json.dumps(doc.export_to_dict()).encode(), 'docling')
    response = client.get(f'/api/documents/{table_id}/reader')
    assert response.status_code == 200
    fragment = response.json['elements'][0]['html']
    assert '<table>' in fragment and '&lt;img' in fragment and '<img' not in fragment
    epub_id = add_document(module, epub_fixture(), 'epub')
    path = module.document_library.root / 'sources' / f'{epub_id}.source'
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as original, zipfile.ZipFile(buffer, 'w') as changed:
        for name in original.namelist():
            changed.writestr(name, '<package><manifest><item id="chapter"/></manifest><spine><itemref idref="chapter"/></spine></package>'
                             if name == 'OPS/book.opf' else original.read(name))
    path.write_bytes(buffer.getvalue())
    response = client.get(f'/api/documents/{epub_id}/reader')
    assert response.status_code == 422 and response.json['state'] == 'rendering_error'
