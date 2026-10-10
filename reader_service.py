"""Authenticated reading content and user-owned reading positions."""

from __future__ import annotations

import html
import io
import json
import math
import posixpath
import re
import time
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree as ET

import pypdfium2 as pdfium
from docling_core.types.doc import DoclingDocument
from flask import abort, g, jsonify, request, send_file
from werkzeug.exceptions import HTTPException


class ReaderFailure(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def _inside_zip(base, target):
    target = unquote(target).replace('\\', '/')
    value = posixpath.normpath(posixpath.join(posixpath.dirname(base), target))
    if value.startswith('../') or value == '..' or value.startswith('/'):
        raise ReaderFailure('unsupported_content', 'The EPUB refers outside its archive')
    return value


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _epub_manifest(source):
    archive = None
    try:
        archive = zipfile.ZipFile(source)
        if archive.getinfo('META-INF/container.xml').file_size > 1_000_000:
            raise ReaderFailure('unsupported_content', 'The EPUB container is too large')
        container = ET.fromstring(archive.read('META-INF/container.xml'))
        rootfile = next((node.attrib['full-path'] for node in container.iter() if _local(node.tag) == 'rootfile'), None)
        if not rootfile:
            raise ReaderFailure('rendering_error', 'The EPUB has no package file')
        if archive.getinfo(rootfile).file_size > 1_000_000:
            raise ReaderFailure('unsupported_content', 'The EPUB package is too large')
        package = ET.fromstring(archive.read(rootfile))
        items = {}
        for node in package.iter():
            if _local(node.tag) == 'item':
                items[node.attrib['id']] = {'path': _inside_zip(rootfile, node.attrib['href']),
                                            'media_type': node.attrib.get('media-type', ''),
                                            'properties': node.attrib.get('properties', '')}
        sections = []
        for node in package.iter():
            if _local(node.tag) == 'itemref':
                item = items.get(node.attrib.get('idref'))
                if not item or item['media_type'] not in ('application/xhtml+xml', 'text/html'):
                    raise ReaderFailure('unsupported_content', 'The EPUB spine contains content this reader cannot display')
                sections.append(item['path'])
        if not sections:
            raise ReaderFailure('unsupported_content', 'The EPUB has no readable sections')
        return archive, items, sections
    except ReaderFailure:
        if archive:
            archive.close()
        raise
    except Exception as exc:
        if archive:
            archive.close()
        raise ReaderFailure('rendering_error', f'Could not read the EPUB: {exc}') from exc


_ALLOWED_TAGS = {'p', 'div', 'section', 'article', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                 'span', 'strong', 'em', 'b', 'i', 'u', 'blockquote', 'pre', 'code',
                 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'br',
                 'hr', 'img', 'a', 'sup', 'sub'}
_BLOCK_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'pre', 'table', 'img'}
_DROP_TAGS = {'script', 'style', 'iframe', 'object', 'embed', 'form', 'svg', 'math', 'video', 'audio'}
_IMAGE_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.gif': 'image/gif', '.webp': 'image/webp'}


class EpubSanitizer(HTMLParser):
    def __init__(self, document_id, section, section_index, archive_names):
        super().__init__(convert_charrefs=True)
        self.document_id = document_id
        self.section = section
        self.section_index = section_index
        self.archive_names = archive_names
        self.parts = []
        self.blocks = 0
        self.markers = {}
        self.anchors = {}
        self.suppressed = 0
        self.stack = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower().split(':')[-1]
        if tag in _DROP_TAGS:
            self.suppressed += 1
            return
        if self.suppressed:
            return
        if tag not in _ALLOWED_TAGS:
            self.stack.append(None)
            return
        attrs = dict(attrs)
        safe = []
        if attrs.get('id'):
            self.anchors[attrs['id']] = self.blocks + (1 if tag in _BLOCK_TAGS else 0)
        if tag in _BLOCK_TAGS:
            self.blocks += 1
            safe.append(f'data-locator="{html.escape(self.section, quote=True)}:{self.blocks}"')
            safe.append(f'id="loc-{self.section_index}-{self.blocks}"')
        if tag == 'img':
            src = attrs.get('src', '')
            parsed = urlsplit(src)
            if parsed.scheme or parsed.netloc or not parsed.path:
                self.stack.append(None)
                return
            try:
                target = _inside_zip(self.section, parsed.path)
            except ReaderFailure:
                self.stack.append(None)
                return
            if target not in self.archive_names or Path(target).suffix.lower() not in _IMAGE_TYPES:
                self.stack.append(None)
                return
            safe.append(f'src="/api/documents/{self.document_id}/reader/resource?path={quote(target, safe="")}"')
            safe.append(f'alt="{html.escape(attrs.get("alt", ""), quote=True)}"')
        if tag == 'a':
            href = attrs.get('href', '')
            parsed = urlsplit(href)
            if not parsed.scheme and not parsed.netloc:
                target = _inside_zip(self.section, parsed.path) if parsed.path else self.section
                if target in self.archive_names:
                    safe.append(f'href="#section-{html.escape(target, quote=True)}"')
        marker = attrs.get('epub:type', '') == 'pagebreak' or attrs.get('role', '') == 'doc-pagebreak'
        if marker:
            label = attrs.get('title') or attrs.get('aria-label') or attrs.get('id')
            if label:
                self.markers[self.blocks + 1] = str(label)[:60]
        self.parts.append(f'<{tag}{(" " + " ".join(safe)) if safe else ""}>')
        self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower().split(':')[-1]
        if tag in _DROP_TAGS:
            self.suppressed = max(0, self.suppressed - 1)
            return
        if self.suppressed or not self.stack:
            return
        opened = self.stack.pop()
        if opened:
            self.parts.append(f'</{opened}>')

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(html.escape(data))


def _epub_content(source, document_id):
    archive, items, sections = _epub_manifest(source)
    try:
        names = set(archive.namelist())
        output = []
        for index, section in enumerate(sections):
            if archive.getinfo(section).file_size > 10_000_000:
                raise ReaderFailure('unsupported_content', 'An EPUB section is too large to display')
            raw = archive.read(section)
            parser = EpubSanitizer(document_id, section, index, names)
            parser.feed(raw.decode('utf-8-sig'))
            output.append({'path': section, 'index': index, 'html': ''.join(parser.parts),
                           'blocks': parser.blocks, 'markers': parser.markers, 'anchors': parser.anchors})
        toc = []
        for item in items.values():
            if 'nav' not in item['properties'].split() and item['media_type'] != 'application/x-dtbncx+xml':
                continue
            try:
                if archive.getinfo(item['path']).file_size > 1_000_000:
                    continue
                tree = ET.fromstring(archive.read(item['path']))
            except (KeyError, ET.ParseError):
                continue
            for node in tree.iter():
                if _local(node.tag) not in ('a', 'content'):
                    continue
                href = node.attrib.get('href') or node.attrib.get('src') or ''
                parsed = urlsplit(href)
                if parsed.scheme or parsed.netloc:
                    continue
                target = _inside_zip(item['path'], parsed.path) if parsed.path else item['path']
                if target in sections:
                    label = ''.join(node.itertext()).strip() or parsed.fragment or f'Section {sections.index(target) + 1}'
                    toc.append({'label': label[:120], 'section': target, 'fragment': parsed.fragment})
        total_blocks = sum(s['blocks'] for s in output)
        if total_blocks == 0:
            raise ReaderFailure('unsupported_content', 'The EPUB has no displayable content')
        return {'format': 'epub', 'sections': output, 'toc': toc, 'total_blocks': total_blocks}
    except (UnicodeDecodeError, KeyError, ET.ParseError) as exc:
        raise ReaderFailure('rendering_error', f'Could not render the EPUB: {exc}') from exc
    finally:
        archive.close()


def _docling_content(source):
    try:
        doc = DoclingDocument.model_validate_json(source.read_text(encoding='utf-8'))
        output = []
        for item, _level in doc.iterate_items():
            ref = item.self_ref
            label = str(getattr(item, 'label', '')).lower()
            value = str(getattr(item, 'text', '') or '').strip()
            table = getattr(item, 'data', None)
            if table is not None and hasattr(table, 'table_cells'):
                rows = []
                for row_index in range(min(table.num_rows, 1000)):
                    cells = sorted((cell for cell in table.table_cells if cell.start_row_offset_idx == row_index),
                                   key=lambda cell: cell.start_col_offset_idx)
                    rows.append('<tr>' + ''.join(f'<{"th" if cell.column_header or cell.row_header else "td"}>'
                                                f'{html.escape(cell.text)}</{"th" if cell.column_header or cell.row_header else "td"}>'
                                                for cell in cells) + '</tr>')
                fragment = '<table>' + ''.join(rows) + '</table>'
            elif value:
                tag = 'h1' if 'title' in label else 'h2' if 'heading' in label else 'p'
                fragment = f'<{tag}>{html.escape(value)}</{tag}>'
            else:
                continue
            provenance = getattr(item, 'prov', None) or []
            page = getattr(provenance[0], 'page_no', None) if provenance else None
            if page is not None and (not isinstance(page, int) or page < 1 or page not in doc.pages):
                page = None
            output.append({'ref': ref, 'html': f'<div data-locator="{html.escape(ref, quote=True)}">{fragment}</div>',
                           'page': page})
        if not output:
            raise ReaderFailure('unsupported_content', 'This Docling document has no displayable text')
        return {'format': 'docling', 'elements': output}
    except ReaderFailure:
        raise
    except Exception as exc:
        raise ReaderFailure('rendering_error', f'Could not render Docling content: {exc}') from exc


def _pdf_count(source):
    try:
        pdf = pdfium.PdfDocument(str(source))
        try:
            count = len(pdf)
            pages = [list(pdf[index].get_size()) for index in range(count)]
        finally:
            pdf.close()
        if count < 1:
            raise ReaderFailure('unsupported_content', 'The PDF has no pages')
        return pages
    except ReaderFailure:
        raise
    except Exception as exc:
        raise ReaderFailure('rendering_error', f'Could not render the PDF: {exc}') from exc


def _position_payload(fmt, value, content):
    if not isinstance(value, dict) or set(value) != {'locator', 'percent'}:
        raise ValueError('Position must contain locator and percent')
    locator, percent = value['locator'], value['percent']
    if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not math.isfinite(percent) or not 0 <= percent <= 100:
        raise ValueError('Percent must be between 0 and 100')
    if not isinstance(locator, dict):
        raise ValueError('Locator must be an object')
    if fmt == 'pdf':
        if set(locator) != {'page', 'offset'} or isinstance(locator['page'], bool) or not isinstance(locator['page'], int) or not 1 <= locator['page'] <= content['page_count']:
            raise ValueError('PDF page is outside the document')
        offset = locator['offset']
        if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(offset) or not 0 <= offset <= 1:
            raise ValueError('PDF offset must be between 0 and 1')
    elif fmt == 'epub':
        if set(locator) != {'section', 'element', 'offset'} or not isinstance(locator['section'], str) or isinstance(locator['element'], bool) or not isinstance(locator['element'], int):
            raise ValueError('EPUB locator is malformed')
        section = next((s for s in content['sections'] if s['path'] == locator['section']), None)
        if section is None or not 1 <= locator['element'] <= section['blocks']:
            raise ValueError('EPUB locator is outside the document')
        offset = locator['offset']
        if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(offset) or not 0 <= offset <= 1:
            raise ValueError('EPUB offset must be between 0 and 1')
    else:
        if set(locator) != {'element', 'offset'} or not isinstance(locator['element'], str) or not re.fullmatch(r'#/[-\w/]+', locator['element']):
            raise ValueError('Docling locator is malformed')
        if locator['element'] not in {item['ref'] for item in content['elements']}:
            raise ValueError('Docling locator is outside the document')
        offset = locator['offset']
        if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(offset) or not 0 <= offset <= 1:
            raise ValueError('Docling offset must be between 0 and 1')
    return {'locator': locator, 'percent': float(percent)}


def install_reader(library):
    app, db = library.app, library.db
    with db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS reading_positions (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                locator_json TEXT, percent REAL NOT NULL DEFAULT 0,
                completed INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL,
                PRIMARY KEY(user_id, document_id)
            );
        ''')

    def document_row(document_id):
        with db() as conn:
            row = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
        if row is None or not library.can_access_document(row, g.current_user['id']):
            abort(404)
        return row

    def source_path(row):
        try:
            return library.safe_path(row['source_path'])
        except Exception as exc:
            raise ReaderFailure('source_missing', 'The source file is missing') from exc

    def content_for(row, source):
        fmt = row['source_type']
        if fmt == 'pdf':
            pages = _pdf_count(source)
            return {'format': 'pdf', 'page_count': len(pages), 'pages': pages}
        if fmt == 'epub':
            return _epub_content(source, row['id'])
        if fmt == 'docling':
            return _docling_content(source)
        raise ReaderFailure('unsupported_content', 'This document format is not supported')

    def failure_response(exc):
        status = {'source_missing': 404, 'rendering_error': 422, 'unsupported_content': 415}[exc.kind]
        return jsonify(error=str(exc), state=exc.kind), status

    @app.get('/api/documents/<document_id>/reader')
    def reader_content(document_id):
        row = document_row(document_id)
        try:
            return jsonify(content_for(row, source_path(row)))
        except ReaderFailure as exc:
            return failure_response(exc)
        except Exception as exc:
            return failure_response(ReaderFailure('rendering_error', f'Could not open the source: {exc}'))

    @app.get('/api/documents/<document_id>/reader/page/<int:page>')
    def reader_pdf_page(document_id, page):
        row = document_row(document_id)
        if row['source_type'] != 'pdf':
            abort(404)
        try:
            source = source_path(row)
            pdf = pdfium.PdfDocument(str(source))
            try:
                if page < 1 or page > len(pdf):
                    abort(404)
                image = pdf[page - 1].render(scale=1.5).to_pil()
                data = io.BytesIO()
                image.save(data, format='PNG')
                data.seek(0)
                return send_file(data, mimetype='image/png', conditional=True)
            finally:
                pdf.close()
        except ReaderFailure as exc:
            return failure_response(exc)
        except HTTPException:
            raise
        except Exception as exc:
            return failure_response(ReaderFailure('rendering_error', f'Could not render PDF page: {exc}'))

    @app.get('/api/documents/<document_id>/reader/resource')
    def reader_epub_resource(document_id):
        row = document_row(document_id)
        if row['source_type'] != 'epub':
            abort(404)
        try:
            path = request.args.get('path', '')
            if path.startswith('/') or '..' in path.split('/') or Path(path).suffix.lower() not in _IMAGE_TYPES:
                abort(404)
            with zipfile.ZipFile(source_path(row)) as archive:
                info = archive.getinfo(path)
                if info.file_size > 10_000_000:
                    abort(413)
                data = archive.read(info)
            return send_file(io.BytesIO(data), mimetype=_IMAGE_TYPES[Path(path).suffix.lower()])
        except (KeyError, zipfile.BadZipFile):
            abort(404)
        except ReaderFailure as exc:
            return failure_response(exc)

    @app.get('/api/documents/<document_id>/progress')
    def reading_progress(document_id):
        document_row(document_id)
        with db() as conn:
            row = conn.execute('SELECT * FROM reading_positions WHERE user_id=? AND document_id=?',
                               (g.current_user['id'], document_id)).fetchone()
        return jsonify(position={'locator': json.loads(row['locator_json']), 'percent': row['percent']} if row and row['locator_json'] else None,
                       completed=bool(row['completed']) if row else False)

    @app.put('/api/documents/<document_id>/progress')
    def save_reading_progress(document_id):
        row = document_row(document_id)
        try:
            content = content_for(row, source_path(row))
            value = _position_payload(row['source_type'], request.get_json(silent=True), content)
        except ReaderFailure as exc:
            return failure_response(exc)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        with db() as conn:
            conn.execute('''INSERT INTO reading_positions(user_id,document_id,locator_json,percent,updated_at)
                VALUES (?,?,?,?,?) ON CONFLICT(user_id,document_id) DO UPDATE SET
                locator_json=excluded.locator_json,percent=excluded.percent,updated_at=excluded.updated_at''',
                (g.current_user['id'], document_id, json.dumps(value['locator']), value['percent'], time.time()))
        return jsonify(position=value)

    @app.post('/api/documents/<document_id>/finish')
    def finish_document(document_id):
        document_row(document_id)
        with db() as conn:
            conn.execute('''INSERT INTO reading_positions(user_id,document_id,completed,updated_at)
                VALUES (?,?,1,?) ON CONFLICT(user_id,document_id) DO UPDATE SET completed=1,updated_at=excluded.updated_at''',
                (g.current_user['id'], document_id, time.time()))
        return jsonify(completed=True)

    @app.post('/api/documents/<document_id>/start-over')
    def start_over(document_id):
        document_row(document_id)
        with db() as conn:
            conn.execute('''INSERT INTO reading_positions(user_id,document_id,locator_json,percent,completed,updated_at)
                VALUES (?,?,NULL,0,0,?) ON CONFLICT(user_id,document_id) DO UPDATE SET
                locator_json=NULL,percent=0,completed=0,updated_at=excluded.updated_at''',
                (g.current_user['id'], document_id, time.time()))
        return jsonify(position=None, completed=False)
