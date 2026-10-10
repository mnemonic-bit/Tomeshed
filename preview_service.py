"""Bounded, authenticated excerpts from preserved document sources."""

from __future__ import annotations

import html
import io
import json
import threading
import zipfile
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

import pypdfium2 as pdfium
from docling_core.types.doc import DoclingDocument
from flask import abort, g, jsonify, request, send_file
from PIL import Image
from werkzeug.exceptions import HTTPException

from reader_service import EpubSanitizer, ReaderFailure, _epub_manifest, _IMAGE_TYPES


class VisibleCounter(HTMLParser):
    """Count EPUB text without converting sections into reader content."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.length = 0
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'iframe', 'object', 'embed', 'form', 'svg', 'math', 'video', 'audio'):
            self.suppressed += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'iframe', 'object', 'embed', 'form', 'svg', 'math', 'video', 'audio'):
            self.suppressed = max(0, self.suppressed - 1)

    def handle_data(self, data):
        if not self.suppressed:
            self.length += len(data)


class PreviewText(HTMLParser):
    """Collect source-ordered text and image events from one sanitized section."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.length = 0
        self.events = []
        self.blocks = {}
        self.page_markers = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'data-locator' in values:
            self.blocks[values['data-locator']] = self.length
            if self.length:
                self.events.append(('break', self.length))
        if tag == 'img' and values.get('src'):
            self.events.append(('image', self.length, values['src'], values.get('alt', '')))

    def handle_data(self, data):
        if data:
            self.events.append(('text', self.length, self.length + len(data), data))
            self.length += len(data)

    def excerpt(self, start, end, image_limit, document_id):
        parts = ['<div>']
        images = 0
        for event in self.events:
            if event[0] == 'text':
                left, right = max(start, event[1]), min(end, event[2])
                if left < right:
                    parts.append(html.escape(event[3][left - event[1]:right - event[1]]))
            elif event[0] == 'break' and start < event[1] < end:
                parts.append('<br>')
            elif event[0] == 'image' and start <= event[1] and (event[1] < end or event[1] == end == self.length) and images < image_limit:
                url = event[2].replace(f'/api/documents/{document_id}/reader/resource?',
                                       f'/api/documents/{document_id}/preview/resource?')
                if len(url) <= 500:
                    parts.append(f'<img src="{html.escape(url, quote=True)}" alt="{html.escape(event[3][:200], quote=True)}">')
                    images += 1
        parts.append('</div>')
        return ''.join(parts), images


def install_preview(library):
    app, db = library.app, library.db
    cache = OrderedDict()
    index_cache = OrderedDict()
    lock = threading.Lock()

    def config(name, minimum, maximum):
        return max(minimum, min(maximum, int(app.config[name])))

    def lookup(document_id):
        with db() as conn:
            row = conn.execute('SELECT * FROM documents WHERE id=? AND state IN ("ready","ready_with_warning")',
                               (document_id,)).fetchone()
        if row is None or not library.can_access_document(row, g.current_user['id']):
            abort(404)
        source = library.safe_path(row['source_path'])
        return row, source

    def cached(key, create):
        with lock:
            if key in cache:
                cache.move_to_end(key)
                return cache[key]
        result = create()
        with lock:
            cache[key] = result
            cache.move_to_end(key)
            while len(cache) > config('PREVIEW_CACHE_LOCATIONS', 1, 128):
                cache.popitem(last=False)
        return result

    def source_key(row, source, index, extra=None):
        stat = source.stat()
        return row['id'], stat.st_mtime_ns, stat.st_size, index, extra

    def location_key(row, source, index, initial_start=None):
        if row['source_type'] == 'pdf':
            return source_key(row, source, index)
        return source_key(row, source, index,
                          (initial_start, text_limit(), config('PREVIEW_IMAGE_LIMIT', 0, 8)))

    def failure(exc):
        status = {'source_missing': 404, 'rendering_error': 422, 'unsupported_content': 415}[exc.kind]
        return jsonify(error=str(exc), state=exc.kind), status

    def text_limit():
        return config('PREVIEW_TEXT_CHARS', 1, 10000)

    def chunks(length):
        return max(1, (length + text_limit() - 1) // text_limit())

    def docling_value(item):
        value = str(getattr(item, 'text', '') or '').strip()
        table = getattr(item, 'data', None)
        if not value and table is not None and hasattr(table, 'table_cells'):
            cells = sorted(table.table_cells,
                           key=lambda cell: (cell.start_row_offset_idx, cell.start_col_offset_idx))
            value = ' '.join(str(cell.text) for cell in cells)
        return value

    def content_index(row, source):
        key = source_key(row, source, 'index', text_limit())
        with lock:
            if key in index_cache:
                index_cache.move_to_end(key)
                return index_cache[key]
        fmt = row['source_type']
        entries = []
        if fmt == 'pdf':
            total = pdf_metadata(source)
        elif fmt == 'epub':
            archive, _items, sections = _epub_manifest(source)
            try:
                cursor = 0
                for section in sections:
                    info = archive.getinfo(section)
                    if info.file_size > 10_000_000:
                        raise ReaderFailure('unsupported_content', 'An EPUB section is too large to preview')
                    counter = VisibleCounter()
                    counter.feed(archive.read(info).decode('utf-8-sig'))
                    count = chunks(counter.length)
                    entries.append({'path': section, 'length': counter.length, 'start': cursor, 'chunks': count})
                    cursor += count
                total = cursor
            finally:
                archive.close()
        elif fmt == 'docling':
            try:
                doc = DoclingDocument.model_validate_json(source.read_text(encoding='utf-8'))
                cursor = 0
                for item, _ in doc.iterate_items():
                    value = docling_value(item)
                    if value:
                        count = chunks(len(value))
                        entries.append({'ref': item.self_ref, 'length': len(value), 'start': cursor, 'chunks': count})
                        cursor += count
                total = cursor
                if not total:
                    raise ReaderFailure('unsupported_content', 'No displayable text')
            except ReaderFailure:
                raise
            except Exception as exc:
                raise ReaderFailure('rendering_error', f'Could not preview Docling content: {exc}') from exc
        else:
            raise ReaderFailure('unsupported_content', 'Unknown source format')
        result = {'format': fmt, 'total': total, 'entries': entries}
        with lock:
            index_cache[key] = result
            index_cache.move_to_end(key)
            while len(index_cache) > 4:
                index_cache.popitem(last=False)
        return result

    def segment(info, index):
        if index < 0 or index >= info['total']:
            abort(404)
        return next((entry for entry in info['entries']
                     if entry['start'] <= index < entry['start'] + entry['chunks']), None)

    def epub_text(source, document_id, section):
        archive, _items, sections = _epub_manifest(source)
        try:
            if section not in sections:
                abort(404)
            info = archive.getinfo(section)
            if info.file_size > 10_000_000:
                raise ReaderFailure('unsupported_content', 'An EPUB section is too large to preview')
            parser = EpubSanitizer(document_id, section, sections.index(section), set(archive.namelist()))
            parser.feed(archive.read(info).decode('utf-8-sig'))
            content = PreviewText()
            content.feed(''.join(parser.parts))
            content.page_markers = sorted((content.blocks[f'{section}:{block}'], label)
                                          for block, label in parser.markers.items()
                                          if f'{section}:{block}' in content.blocks)
            return content
        except (KeyError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
            raise ReaderFailure('rendering_error', f'Could not preview EPUB content: {exc}') from exc
        finally:
            archive.close()

    def docling_text(source, ref):
        try:
            doc = DoclingDocument.model_validate_json(source.read_text(encoding='utf-8'))
            for item, _level in doc.iterate_items():
                if item.self_ref == ref:
                    return docling_value(item)
            abort(404)
        except ReaderFailure:
            raise
        except HTTPException:
            raise
        except Exception as exc:
            raise ReaderFailure('rendering_error', f'Could not preview Docling content: {exc}') from exc

    def pdf_metadata(source):
        try:
            pdf = pdfium.PdfDocument(str(source))
            count = len(pdf)
            pdf.close()
            if count < 1:
                raise ReaderFailure('unsupported_content', 'The PDF has no pages')
            return count
        except ReaderFailure:
            raise
        except Exception as exc:
            raise ReaderFailure('rendering_error', f'Could not preview PDF: {exc}') from exc

    def location(row, source, index, initial_start=None):
        info = content_index(row, source)
        fmt, total = info['format'], info['total']
        if fmt == 'pdf':
            if index < 0 or index >= total:
                abort(404)
            return {'format': fmt, 'index': index, 'total': total, 'label': f'Page {index + 1} of {total}',
                    'image': f'/api/documents/{quote(row["id"])}/preview/page/{index + 1}',
                    'page': index + 1}
        if fmt == 'epub':
            entry = segment(info, index)
            content = epub_text(source, row['id'], entry['path'])
            start = entry['length'] and (index - entry['start']) * text_limit() or 0
            if initial_start is not None:
                start = max(start, min(initial_start, entry['length']))
            end = min(entry['length'], (index - entry['start'] + 1) * text_limit())
            excerpt, images = content.excerpt(start, end if end > start else start + 1,
                                             config('PREVIEW_IMAGE_LIMIT', 0, 8), row['id'])
            markers = [label for offset, label in content.page_markers if offset <= start]
            label = f'Location {index + 1} of {total}'
            if markers:
                label = f'Page {markers[-1]} · {label}'
            return {'format': fmt, 'index': index, 'total': total, 'label': label,
                    'html': excerpt, 'section': entry['path'], 'characters': max(0, end - start), 'images': images}
        if fmt == 'docling':
            entry = segment(info, index)
            value = docling_text(source, entry['ref'])
            start = (index - entry['start']) * text_limit()
            if initial_start is not None:
                start = max(start, min(initial_start, len(value)))
            end = min(len(value), (index - entry['start'] + 1) * text_limit())
            return {'format': fmt, 'index': index, 'total': total, 'label': f'Location {index + 1} of {total}',
                    'html': '<p>' + html.escape(value[start:end]) + '</p>', 'element': entry['ref'],
                    'characters': max(0, end - start), 'images': 0}
        raise ReaderFailure('unsupported_content', 'Unknown source format')

    @app.get('/api/documents/<document_id>/preview')
    def preview_start(document_id):
        try:
            row, source = lookup(document_id)
            info = content_index(row, source)
            fmt, total, entries = info['format'], info['total'], info['entries']
            with db() as conn:
                saved = conn.execute('SELECT locator_json,percent FROM reading_positions WHERE user_id=? AND document_id=?',
                                     (g.current_user['id'], document_id)).fetchone()
            locator = json.loads(saved['locator_json']) if saved and saved['locator_json'] else None
            approximate = False
            index, initial_start = 0, None
            if locator:
                if fmt == 'pdf':
                    page = locator.get('page')
                    if isinstance(page, int) and not isinstance(page, bool) and 1 <= page <= total:
                        index = page - 1
                    elif isinstance(page, int) and not isinstance(page, bool):
                        index = max(0, min(total - 1, page - 1))
                        approximate = True
                    else:
                        index = max(0, min(total - 1, int(float(saved['percent']) / 100 * total)))
                        approximate = True
                elif fmt == 'epub':
                    entry = next((item for item in entries if item['path'] == locator.get('section')), None)
                    if entry:
                        content = epub_text(source, document_id, entry['path'])
                        block = f'{entry["path"]}:{locator.get("element")}'
                        if block in content.blocks:
                            block_start = content.blocks[block]
                            later = [value for value in content.blocks.values() if value > block_start]
                            block_end = min(later) if later else content.length
                            fraction = max(0, min(1, float(locator.get('offset') or 0)))
                            initial_start = min(max(0, content.length - 1),
                                                block_start + int((block_end - block_start) * fraction))
                            index = entry['start'] + min(entry['chunks'] - 1, initial_start // text_limit())
                        else:
                            index = max(0, min(total - 1, int(float(saved['percent']) / 100 * total)))
                            approximate = True
                    else:
                        index = max(0, min(total - 1, int(float(saved['percent']) / 100 * total)))
                        approximate = True
                else:
                    entry = next((item for item in entries if item['ref'] == locator.get('element')), None)
                    if entry:
                        fraction = max(0, min(1, float(locator.get('offset') or 0)))
                        initial_start = min(entry['length'] - 1, int(fraction * entry['length']))
                        index = entry['start'] + min(entry['chunks'] - 1, initial_start // text_limit())
                    else:
                        index = max(0, min(total - 1, int(float(saved['percent']) / 100 * total)))
                        approximate = True
            result = cached(location_key(row, source, index, initial_start),
                            lambda: location(row, source, index, initial_start))
            return jsonify(**result, approximate=approximate)
        except ReaderFailure as exc:
            return failure(exc)
        except HTTPException:
            raise
        except Exception as exc:
            return failure(ReaderFailure('rendering_error', f'Preview unavailable: {exc}'))

    @app.get('/api/documents/<document_id>/preview/location/<int:index>')
    def preview_location(document_id, index):
        try:
            row, source = lookup(document_id)
            return jsonify(cached(location_key(row, source, index), lambda: location(row, source, index)))
        except ReaderFailure as exc:
            return failure(exc)
        except HTTPException:
            raise
        except Exception as exc:
            return failure(ReaderFailure('rendering_error', f'Preview unavailable: {exc}'))

    @app.get('/api/documents/<document_id>/preview/page/<int:page>')
    def preview_page(document_id, page):
        try:
            row, source = lookup(document_id)
            if row['source_type'] != 'pdf':
                abort(404)
            width_limit = config('PREVIEW_PDF_MAX_WIDTH', 32, 1200)
            height_limit = config('PREVIEW_PDF_MAX_HEIGHT', 32, 1600)
            key = source_key(row, source, ('page', page), (width_limit, height_limit))
            def create():
                pdf = pdfium.PdfDocument(str(source))
                try:
                    if page < 1 or page > len(pdf):
                        abort(404)
                    pdf_page = pdf[page - 1]
                    width, height = pdf_page.get_size()
                    scale = min(1.0, width_limit / max(1, width), height_limit / max(1, height))
                    image = pdf_page.render(scale=scale).to_pil()
                    output = io.BytesIO(); image.save(output, 'PNG')
                    return output.getvalue()
                finally:
                    pdf.close()
            data = cached(key, create)
            return send_file(io.BytesIO(data), mimetype='image/png')
        except ReaderFailure as exc:
            return failure(exc)
        except HTTPException:
            raise
        except Exception as exc:
            return failure(ReaderFailure('rendering_error', f'Could not render preview page: {exc}'))

    @app.get('/api/documents/<document_id>/preview/resource')
    def preview_resource(document_id):
        try:
            row, source = lookup(document_id)
            if row['source_type'] != 'epub':
                abort(404)
            path = request.args.get('path', '')
            if path.startswith('/') or '..' in path.split('/') or Path(path).suffix.lower() not in _IMAGE_TYPES:
                abort(404)
            with zipfile.ZipFile(source) as archive:
                info = archive.getinfo(path)
                if info.file_size > 2_000_000:
                    abort(413)
                image = Image.open(io.BytesIO(archive.read(info)))
                if image.width * image.height > 50_000_000:
                    abort(413)
                image.thumbnail((config('PREVIEW_PDF_MAX_WIDTH', 100, 1200),) * 2)
                output = io.BytesIO(); image.convert('RGB').save(output, 'PNG')
            return send_file(io.BytesIO(output.getvalue()), mimetype='image/png')
        except (KeyError, zipfile.BadZipFile):
            abort(404)
        except HTTPException:
            raise
        except Exception as exc:
            return failure(ReaderFailure('rendering_error', f'Could not render preview image: {exc}'))
