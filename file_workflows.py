"""Managed document transfer, URL fetch, watched inbox, and cleanup workflows."""

from __future__ import annotations

import http.client
import ipaddress
import json
import logging
import math
import os
import re
import shutil
import socket
import ssl
import stat
import threading
import time
import uuid
import zipfile
from pathlib import Path
from tempfile import SpooledTemporaryFile
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode, unquote

from flask import abort, g, jsonify, request, send_file
from document_processing import detect_source
from werkzeug.exceptions import HTTPException

LOG = logging.getLogger(__name__)
TEMP_SUFFIXES = ('.part', '.partial', '.tmp', '.crdownload', '.download')


def config_seconds(name, default, minimum=0):
    raw = os.environ.get(name, str(default))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise RuntimeError(f'{name} must be a finite number') from None
    if not math.isfinite(value) or (value < minimum if minimum else value <= 0):
        raise RuntimeError(f'{name} must be a finite number of at least {minimum}' if minimum else f'{name} must be a positive finite number')
    return value


def validate_url(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Enter an HTTP or HTTPS PDF or EPUB URL')
    value = value.strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError('Malformed URL') from None
    if parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError('URL must use HTTP or HTTPS without credentials')
    if any(char.isspace() or ord(char) < 32 for char in value) or len(value) > 4096 or not parsed.hostname.strip('. '):
        raise ValueError('Malformed URL')
    try:
        hostname = parsed.hostname.encode('idna').decode('ascii')
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            if len(hostname) > 253 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in hostname.rstrip('.').split('.')):
                raise ValueError()
    except (UnicodeError, ValueError):
        raise ValueError('Malformed URL hostname') from None
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('Malformed URL port')
    return value


def display_url(value):
    parsed = urlsplit(value)
    query = urlencode([(key, 'REDACTED') for key, _ in parse_qsl(parsed.query, keep_blank_values=True)])
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ''))


def signature(meta):
    return (meta.st_dev, meta.st_ino, meta.st_size, meta.st_mtime_ns)


def valid_docling_json(path):
    try:
        from docling_core.types.doc import DoclingDocument
        data = json.loads(path.read_text(encoding='utf-8'))
        document = DoclingDocument.model_validate(data)
        return bool(document.name and (document.texts or document.tables or document.pictures or document.pages))
    except Exception:
        return False


class SourceChanged(Exception):
    pass


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, port, timeout):
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class FileWorkflows:
    def __init__(self, library):
        self.library = library
        self.app = library.app
        self.db = library.db
        self.root = library.root
        self.scan_seconds = config_seconds('TOMESHED_INGEST_SCAN_SECONDS', 10, 1)
        self.settle_seconds = config_seconds('TOMESHED_INGEST_SETTLE_SECONDS', 60, 1)
        self.connect_timeout = config_seconds('TOMESHED_URL_CONNECT_TIMEOUT_SECONDS', 10)
        self.total_timeout = config_seconds('TOMESHED_URL_TOTAL_TIMEOUT_SECONDS', 300)
        raw_cidrs = os.environ.get('TOMESHED_URL_ALLOWED_CIDRS', '')
        try:
            self.allowed_cidrs = [ipaddress.ip_network(part.strip(), strict=False) for part in raw_cidrs.split(',') if part.strip()]
        except ValueError as exc:
            raise RuntimeError(f'TOMESHED_URL_ALLOWED_CIDRS is invalid: {exc}') from exc
        self.inbox = None
        raw_inbox = os.environ.get('TOMESHED_INGEST_DIR', '').strip()
        if raw_inbox:
            inbox = Path(raw_inbox).resolve()
            if not inbox.is_dir() or not os.access(inbox, os.R_OK | os.X_OK):
                raise RuntimeError(f'TOMESHED_INGEST_DIR must name an existing readable directory: {raw_inbox}')
            if inbox == self.root or inbox.is_relative_to(self.root) or self.root.is_relative_to(inbox):
                raise RuntimeError('TOMESHED_INGEST_DIR must be distinct from managed storage')
            self.inbox = inbox
        self.candidates = {}
        self.handoffs = {}
        self.inflight = set()
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        self._schema()
        self._routes()

    def _schema(self):
        with self.db() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS ingest_receipts (
                    source_path TEXT PRIMARY KEY, signature TEXT NOT NULL,
                    document_id TEXT NOT NULL, created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cleanup_failures (
                    document_id TEXT PRIMARY KEY, artifacts TEXT NOT NULL,
                    error TEXT NOT NULL, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_ingest (
                    job_id TEXT PRIMARY KEY, source_path TEXT NOT NULL,
                    signature TEXT NOT NULL
                );
            ''')

    def owned_path(self, stored):
        relative = Path(stored)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
            raise ValueError('Stored path is outside managed storage')
        current = self.root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError('Stored path crosses a symlink')
        if not current.resolve().is_relative_to(self.root):
            raise ValueError('Stored path is outside managed storage')
        return current

    def remove_owned_source(self, row):
        target = self.owned_path(row['source_path'])
        target.unlink(missing_ok=True)
        if target.parent.name == row['document_id'] and target.parent != self.root:
            try:
                target.parent.rmdir()
            except OSError:
                pass

    def register(self, filename, origin='browser', source_url=None, expected_bytes=None,
                 watch_path=None, watch_signature=None, owner_user_id=None):
        name = Path(str(filename).replace('\\', '/')).name[:255]
        if not name or name in ('.', '..') or any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise ValueError('Filename is required')
        if expected_bytes is not None and (not isinstance(expected_bytes, int) or expected_bytes < 0 or expected_bytes > self.app.config['MAX_UPLOAD_BYTES']):
            raise ValueError(f'Upload exceeds the {self.app.config["MAX_UPLOAD_BYTES"]} byte size limit')
        job_id, document_id = uuid.uuid4().hex, uuid.uuid4().hex
        path = f'sources/{document_id}/{name}'
        (self.root / 'sources' / document_id).mkdir()
        now = time.time()
        with self.db() as conn:
            conn.execute('''INSERT INTO import_jobs(id,document_id,original_filename,source_path,state,origin,source_url,expected_bytes,created_at,updated_at,owner_user_id)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                         (job_id, document_id, name, path, 'pending', origin, source_url, expected_bytes, now, now, owner_user_id))
            if origin == 'watch':
                conn.execute('INSERT INTO pending_ingest(job_id,source_path,signature) VALUES (?,?,?)',
                             (job_id,watch_path,json.dumps(watch_signature)))
        self.library.publish()
        return job_id, document_id, path

    def fail(self, job_id, reason, remove_source=True):
        with self.db() as conn:
            row = conn.execute('SELECT source_path,state,document_id FROM import_jobs WHERE id=?', (job_id,)).fetchone()
            if not row or row['state'] in ('ready', 'ready_with_warning'):
                return
            conn.execute("UPDATE import_jobs SET state='failed',error=?,updated_at=? WHERE id=?", (str(reason)[:1000], time.time(), job_id))
        if remove_source:
            try:
                self.remove_owned_source(row)
            except (OSError, ValueError) as exc:
                LOG.error('Import source cleanup failed for %s: %s', job_id, exc)
        with self.db() as conn:
            conn.execute('DELETE FROM pending_ingest WHERE job_id=?', (job_id,))
        self.library.publish()

    def cancelled(self, job_id):
        with self.db() as conn:
            row = conn.execute('SELECT cancel_requested FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        return bool(row and row['cancel_requested'])

    def _routes(self):
        app = self.app
        library = self.library

        @app.post('/api/imports/register')
        def register_browser_import():
            data = request.get_json(silent=True) or {}
            if isinstance(data.get('size'), bool) or not isinstance(data.get('size'), int):
                return jsonify(error='File size is required before transfer'), 400
            try:
                job_id, document_id, _ = self.register(data.get('filename', ''), expected_bytes=data.get('size'), owner_user_id=g.current_user['id'])
            except ValueError as exc:
                return jsonify(error=str(exc)), 400
            return jsonify(id=job_id, document_id=document_id, state='pending'), 202

        @app.put('/api/imports/<job_id>/file')
        def transfer_browser_import(job_id):
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute('SELECT * FROM import_jobs WHERE id=?', (job_id,)).fetchone()
                if not row or not library.can_access_job(row, g.current_user['id']):
                    abort(404)
                if row['origin'] != 'browser' or row['state'] != 'pending' or row['cancel_requested']:
                    return jsonify(error='Import is not awaiting a file'), 409
                if row['bytes_received'] or self.owned_path(row['source_path']).exists():
                    return jsonify(error='Transfer already started'), 409
            size = 0
            target = self.owned_path(row['source_path'])
            try:
                with target.open('xb') as output:
                    while chunk := request.stream.read(1024 * 1024):
                        if self.cancelled(job_id):
                            raise ValueError('Cancelled by user')
                        size += len(chunk)
                        if size > self.app.config['MAX_UPLOAD_BYTES'] or (row['expected_bytes'] is not None and size > row['expected_bytes']):
                            raise ValueError(f'Upload exceeds the {self.app.config["MAX_UPLOAD_BYTES"]} byte size limit')
                        output.write(chunk)
                        with self.db() as conn:
                            conn.execute('UPDATE import_jobs SET bytes_received=?,updated_at=? WHERE id=?', (size, time.time(), job_id))
                        library.publish()
                if not size or (row['expected_bytes'] is not None and size != row['expected_bytes']):
                    raise ValueError('Upload ended before all bytes arrived')
                if self.cancelled(job_id):
                    raise ValueError('Cancelled by user')
            except Exception as exc:
                self.fail(job_id, str(exc))
                return jsonify(error=str(exc)), 409 if str(exc) == 'Cancelled by user' else 413 if 'size limit' in str(exc) else 400
            with self.db() as conn:
                changed = conn.execute('''UPDATE import_jobs SET transfer_complete=1,bytes_received=?,updated_at=?
                    WHERE id=? AND state='pending' AND cancel_requested=0''',(size,time.time(),job_id)).rowcount
            if not changed:
                self.fail(job_id,'Cancelled by user')
                return jsonify(error='Cancelled by user'),409
            library.pool.submit(library._process_job, job_id)
            return jsonify(id=job_id, state='pending', bytes_received=size), 202

        @app.post('/api/imports/<job_id>/cancel')
        def cancel_import(job_id):
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute('SELECT * FROM import_jobs WHERE id=?', (job_id,)).fetchone()
                if not row or not library.can_access_job(row, g.current_user['id']):
                    abort(404)
                if row['origin'] != 'browser':
                    return jsonify(error='Only browser imports can be cancelled'), 409
                if row['state'] in ('ready', 'ready_with_warning'):
                    return jsonify(error='Document is already available'), 409
                if row['state'] == 'failed':
                    return jsonify(error='Import has already ended'), 409
                conn.execute("UPDATE import_jobs SET cancel_requested=1,state='failed',error='Cancelled by user',updated_at=? WHERE id=?", (time.time(), job_id))
            try:
                self.remove_owned_source(row)
            except (OSError, ValueError) as exc:
                LOG.error('Cancelled import cleanup failed for %s: %s', job_id, exc)
            library.publish()
            return jsonify(id=job_id, state='failed', error='Cancelled by user')

        @app.post('/api/imports/<job_id>/retry')
        def retry_import(job_id):
            with self.db() as conn:
                row = conn.execute('SELECT * FROM import_jobs WHERE id=?', (job_id,)).fetchone()
            if not row or not library.can_access_job(row, g.current_user['id']):
                abort(404)
            if row['state'] != 'failed' or row['retry']:
                return jsonify(error='Only a failed import can be retried'), 409
            if row['origin'] == 'url':
                new_id, document_id, _ = self.register(row['original_filename'], 'url', row['source_url'], owner_user_id=g.current_user['id'])
                self.library.pool.submit(self.fetch_url, new_id)
                return jsonify(id=new_id, document_id=document_id, state='pending'), 202
            if row['origin'] == 'browser':
                return jsonify(reselect=True, filename=row['original_filename'])
            return jsonify(error='Watched files retry after their signature changes'), 409

        @app.post('/api/imports/url')
        def register_url_import():
            data = request.get_json(silent=True) or {}
            try:
                url = validate_url(data.get('url'))
            except ValueError as exc:
                return jsonify(error=str(exc)), 400
            filename = unquote(Path(urlsplit(url).path).name) or 'download'
            if not filename.lower().endswith(('.pdf', '.epub')):
                filename = Path(filename).stem + '.pdf'
            job_id, document_id, _ = self.register(filename, 'url', url, owner_user_id=g.current_user['id'])
            self.library.pool.submit(self.fetch_url, job_id)
            return jsonify(id=job_id, document_id=document_id, state='pending'), 202

        @app.get('/api/documents/<document_id>/export/original')
        def export_original(document_id):
            row = self.document(document_id)
            source = library.safe_path(row['source_path'])
            return send_file(source, as_attachment=True, download_name=source.name,
                             mimetype={'pdf':'application/pdf','epub':'application/epub+zip','docling':'application/json'}[row['source_type']])

        @app.post('/api/documents/bulk/status')
        def selected_document_status():
            try:
                ids = self.selected_ids()
            except ValueError as exc:
                return jsonify(error=str(exc)), 400
            accessible = []
            for document_id in ids:
                with self.db() as conn:
                    row = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
                if row and library.can_access_document(row, g.current_user['id']):
                    accessible.append(document_id)
            return jsonify(accessible_ids=accessible,
                           unavailable_ids=[document_id for document_id in ids if document_id not in accessible])

        @app.post('/api/documents/bulk/export/original')
        def export_selected_originals():
            try:
                ids = self.selected_ids()
            except ValueError as exc:
                return jsonify(error=str(exc)), 400
            included, failures = [], []
            archive_file = SpooledTemporaryFile(max_size=8 * 1024 * 1024)
            with zipfile.ZipFile(archive_file, 'w', compression=zipfile.ZIP_STORED) as archive:
                for document_id in ids:
                    with self.db() as conn:
                        row = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
                    if not row or not library.can_access_document(row, g.current_user['id']):
                        failures.append({'id': document_id, 'reason': 'unavailable'})
                        continue
                    try:
                        source = library.safe_path(row['source_path'])
                        filename = row['original_filename'] if source.suffix == '.source' else source.name
                        basename = re.sub(r'[\\/\x00-\x1f\x7f]', '_', filename)
                        entry_name = f'{Path(basename).stem} ({document_id}){Path(basename).suffix}'
                        archive.write(source, entry_name)
                    except (HTTPException, OSError, ValueError):
                        failures.append({'id': document_id, 'reason': 'source_unavailable'})
                        continue
                    included.append({'id': document_id, 'filename': entry_name})
                archive.writestr('manifest.json', json.dumps({
                    'requested_ids': ids, 'included': included, 'failures': failures}, indent=2))
            archive_file.seek(0)
            response = send_file(archive_file, as_attachment=True, download_name='tomeshed-originals.zip',
                                 mimetype='application/zip')
            response.headers['X-Tomeshed-Bulk-Included'] = str(len(included))
            response.headers['X-Tomeshed-Bulk-Failure-Count'] = str(len(failures))
            return response

        @app.post('/api/documents/bulk/delete')
        def delete_selected_documents():
            try:
                ids = self.selected_ids()
            except ValueError as exc:
                return jsonify(error=str(exc)), 400
            data = request.get_json(silent=True) or {}
            if type(data.get('confirm_count')) is not int or data['confirm_count'] != len(ids):
                return jsonify(error='Confirm deletion with the selected document count'), 400
            removed, failures = [], []
            for document_id in ids:
                with self.lock:
                    with self.db() as conn:
                        row = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
                        active = conn.execute("SELECT 1 FROM import_jobs WHERE document_id=? AND state IN ('pending','processing')", (document_id,)).fetchone()
                    if not row or not library.can_access_document(row, g.current_user['id']):
                        failures.append({'id': document_id, 'reason': 'unavailable'})
                    elif not library.can_manage_document(row, g.current_user['id']):
                        failures.append({'id': document_id, 'reason': 'not_manageable'})
                    elif active:
                        failures.append({'id': document_id, 'reason': 'active_import'})
                    else:
                        result, _ = self.remove_many([document_id])
                        if document_id in result['removed']:
                            removed.append(document_id)
                        else:
                            failures.append({'id': document_id, 'reason': 'cleanup_failed'})
            remaining = []
            for document_id in ids:
                if document_id in removed:
                    continue
                with self.db() as conn:
                    row = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
                if row and library.can_access_document(row, g.current_user['id']):
                    remaining.append(document_id)
            return jsonify(removed=removed, failures=failures,
                           remaining_document_ids=remaining), 207 if failures else 200

        @app.get('/api/documents/<document_id>/export/docling')
        def export_docling(document_id):
            row = self.document(document_id)
            if row['source_type'] == 'docling':
                target = library.safe_path(row['source_path'])
            elif row['artifact_path']:
                target = library.safe_path(row['artifact_path'])
            else:
                abort(404)
            if not valid_docling_json(target):
                abort(404)
            return send_file(target, as_attachment=True, download_name=Path(row['original_filename']).stem + '-docling.json', mimetype='application/json')

        @app.post('/api/documents/<document_id>/rename-file')
        def rename_file(document_id):
            row = self.document(document_id)
            data = request.get_json(silent=True) or {}
            name = data.get('filename')
            if not isinstance(name, str) or not name.strip() or name in ('.','..') or any(char in name for char in ('/', '\\')) or any(ord(char) < 32 or ord(char) == 127 for char in name):
                return jsonify(error='Enter a basename without separators or control characters'), 400
            source = library.safe_path(row['source_path'])
            extension = {'pdf':'.pdf','epub':'.epub','docling':'.json'}[row['source_type']]
            requested = name.strip()
            stem = Path(requested).stem.strip()
            if not stem or stem in ('.','..') or stem.startswith('.'):
                return jsonify(error='Filename is empty'), 400
            target = source.with_name(stem + extension)
            if target == source:
                return jsonify(document=library.public_document(row))
            with self.lock:
                if target.exists() or target.is_symlink():
                    return jsonify(error='A file with that name already exists'), 409
                try:
                    os.link(source, target, follow_symlinks=False)
                    with self.db() as conn:
                        conn.execute('UPDATE documents SET source_path=? WHERE id=?', (str(target.relative_to(self.root)), document_id))
                    try:
                        source.unlink()
                    except OSError:
                        with self.db() as conn:
                            conn.execute('UPDATE documents SET source_path=? WHERE id=?', (row['source_path'], document_id))
                        raise
                except Exception as exc:
                    target.unlink(missing_ok=True)
                    return jsonify(error=f'Rename failed: {exc}'), 500
            with self.db() as conn:
                updated = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
            library.publish()
            return jsonify(document=library.public_document(updated))

        @app.delete('/api/documents/<document_id>')
        def remove_document(document_id):
            row = self.document(document_id)
            data = request.get_json(silent=True) or {}
            title = row['corrected_title'] if row['corrected_title'] is not None else row['title']
            if data.get('confirm') != title:
                return jsonify(error='Confirm removal with the document title'), 400
            result, status = self.remove_many([document_id])
            return jsonify(result), status

        @app.get('/api/library/clear/preview')
        def clear_preview():
            if g.current_user['role'] != 'admin':
                abort(403)
            return jsonify(self.bulk_preview())

        @app.post('/api/library/clear')
        def clear_library():
            if g.current_user['role'] != 'admin':
                abort(403)
            data = request.get_json(silent=True) or {}
            preview = self.bulk_preview()
            if data.get('token') != preview['token']:
                return jsonify(error='Library changed; request a new preview'), 409
            result, status = self.remove_many(preview['document_ids'])
            return jsonify(result), status

        @app.post('/api/library/cleanup/retry')
        def retry_cleanup():
            if g.current_user['role'] != 'admin':
                abort(403)
            with self.db() as conn:
                ids = [row['document_id'] for row in conn.execute('SELECT document_id FROM cleanup_failures')]
            result, status = self.remove_many(ids)
            return jsonify(result), status

    def document(self, document_id):
        with self.db() as conn:
            row = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
        if row is None or not self.library.can_access_document(row, g.current_user['id']):
            abort(404)
        return row

    def selected_ids(self):
        data = request.get_json(silent=True)
        ids = data.get('ids') if isinstance(data, dict) else None
        if (not isinstance(ids, list) or not 0 < len(ids) <= 1000 or
                any(not isinstance(document_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', document_id) for document_id in ids) or
                len(set(ids)) != len(ids)):
            raise ValueError('Provide 1 to 1000 distinct document IDs')
        return ids

    def bulk_preview(self):
        with self.db() as conn:
            rows = conn.execute('''SELECT * FROM documents d WHERE NOT EXISTS
                 (SELECT 1 FROM import_jobs j WHERE j.document_id=d.id AND j.state IN ('pending','processing')) ORDER BY d.id''').fetchall()
        ids = [row['id'] for row in rows]
        paths = [self.root / row[key] for row in rows for key in ('source_path','artifact_path','thumbnail_path') if row[key]]
        existing = sorted(str(path) for path in paths if path.exists())
        import hashlib
        token = hashlib.sha256(json.dumps([ids, existing]).encode()).hexdigest()
        return {'document_count':len(ids), 'file_count':len(existing), 'document_ids':ids, 'token':token}

    def remove_many(self, ids):
        remaining, artifacts, removed = [], [], []
        with self.lock:
            for document_id in ids:
                with self.db() as conn:
                    row = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
                    active = conn.execute("SELECT 1 FROM import_jobs WHERE document_id=? AND state IN ('pending','processing')", (document_id,)).fetchone()
                if not row:
                    continue
                if active:
                    remaining.append(document_id)
                    continue
                paths = [row[key] for key in ('source_path','artifact_path','thumbnail_path') if row[key]]
                failed_paths = []
                for stored in paths:
                    try:
                        self.owned_path(stored).unlink(missing_ok=True)
                    except Exception as exc:
                        failed_paths.append(stored)
                        LOG.error('Cleanup failed for %s: %s', stored, exc)
                try:
                    source_dir = self.owned_path(row['source_path']).parent
                except ValueError:
                    source_dir = None
                if source_dir and source_dir.name == document_id and source_dir.is_dir():
                    try:
                        source_dir.rmdir()
                    except OSError:
                        pass
                if failed_paths:
                    remaining.append(document_id)
                    artifacts.extend(failed_paths)
                    with self.db() as conn:
                        conn.execute('REPLACE INTO cleanup_failures(document_id,artifacts,error,updated_at) VALUES (?,?,?,?)', (document_id, json.dumps(failed_paths), 'Managed artifact removal failed', time.time()))
                    continue
                with self.db() as conn:
                    self.library.bookshelves.compact_removed_document(conn, document_id)
                    conn.execute('DELETE FROM documents WHERE id=?', (document_id,))
                    conn.execute('DELETE FROM import_jobs WHERE document_id=?', (document_id,))
                    conn.execute('DELETE FROM cleanup_failures WHERE document_id=?', (document_id,))
                removed.append(document_id)
        self.library.publish()
        return {'removed':removed, 'remaining_document_ids':remaining, 'remaining_artifacts':artifacts}, 500 if remaining else 200

    def checked_addresses(self, hostname, port):
        try:
            candidates = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError(f'DNS lookup failed: {exc}') from exc
        addresses = []
        for candidate in candidates:
            address = candidate[4][0]
            parsed = ipaddress.ip_address(address)
            if not parsed.is_global and not any(parsed in network for network in self.allowed_cidrs):
                raise ValueError('URL destination is not public or allowed')
            addresses.append(address)
        if not addresses:
            raise ValueError('URL has no resolved address')
        return addresses[0]

    def fetch_url(self, job_id):
        with self.db() as conn:
            row = conn.execute('SELECT * FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            return
        target = self.root / row['source_path']
        started = time.monotonic()
        url = row['source_url']
        connection = None
        try:
            for redirects in range(6):
                validate_url(url)
                parsed = urlsplit(url)
                port = parsed.port or (443 if parsed.scheme == 'https' else 80)
                address = self.checked_addresses(parsed.hostname, port)
                timeout = min(self.connect_timeout, max(.01, self.total_timeout - (time.monotonic()-started)))
                connection = PinnedHTTPSConnection(parsed.hostname, address, port, timeout) if parsed.scheme == 'https' else http.client.HTTPConnection(address, port, timeout=timeout)
                host = parsed.hostname if parsed.port is None else f'{parsed.hostname}:{parsed.port}'
                connection.request('GET', urlunsplit(('', '', parsed.path or '/', parsed.query, '')), headers={'Host':host,'Accept':'application/pdf, application/epub+zip','User-Agent':'Tomeshed/0.1'})
                response = connection.getresponse()
                if 300 <= response.status < 400 and response.getheader('Location'):
                    if redirects >= 5:
                        raise ValueError('URL exceeded five redirects')
                    url = urljoin(url, response.getheader('Location'))
                    connection.close()
                    continue
                if response.status != 200:
                    raise ValueError(f'URL returned HTTP {response.status}')
                if response.getheader('Content-Length') and int(response.getheader('Content-Length')) > self.app.config['MAX_UPLOAD_BYTES']:
                    raise ValueError('URL exceeds upload size limit')
                count = 0
                with target.open('xb') as output:
                    while True:
                        remaining = self.total_timeout - (time.monotonic()-started)
                        if remaining <= 0:
                            raise ValueError('URL total timeout exceeded')
                        response_socket = connection.sock or getattr(getattr(response.fp, 'raw', None), '_sock', None)
                        if response_socket is not None:
                            response_socket.settimeout(min(self.connect_timeout, remaining))
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > self.app.config['MAX_UPLOAD_BYTES']:
                            raise ValueError('URL exceeds upload size limit')
                        output.write(chunk)
                        with self.db() as conn:
                            conn.execute('UPDATE import_jobs SET bytes_received=?,updated_at=? WHERE id=?', (count,time.time(),job_id))
                        self.library.publish()
                if count == 0:
                    raise ValueError('URL returned an empty file')
                kind, *_ = detect_source(target)
                if kind not in ('pdf','epub'):
                    raise ValueError('URL did not contain a PDF or EPUB')
                with self.db() as conn:
                    if not row['original_filename'].lower().endswith('.' + kind):
                        name = Path(row['original_filename']).stem + '.' + kind
                        renamed = target.with_name(name)
                        os.replace(target, renamed)
                        target = renamed
                        conn.execute('UPDATE import_jobs SET original_filename=?,source_path=? WHERE id=?',
                                     (name,str(renamed.relative_to(self.root)),job_id))
                    conn.execute('UPDATE import_jobs SET transfer_complete=1,bytes_received=?,updated_at=? WHERE id=?',
                                 (count,time.time(),job_id))
                self.library.pool.submit(self.library._process_job, job_id)
                return
            raise ValueError('URL exceeded five redirects')
        except Exception as exc:
            self.fail(job_id, str(exc))
        finally:
            if connection:
                connection.close()

    def start_watcher(self):
        for path in (self.root / 'staging').glob('.watch-*.part'):
            if path.is_file() and not path.is_symlink():
                path.unlink(missing_ok=True)
        if not self.inbox:
            return
        with self.db() as conn:
            rows = conn.execute('''SELECT p.job_id,p.source_path,p.signature,j.state,j.document_id
                FROM pending_ingest p LEFT JOIN import_jobs j ON j.id=p.job_id''').fetchall()
            for row in rows:
                if row['state'] in ('ready','ready_with_warning'):
                    self.record_receipt(row['job_id'],row['document_id'],conn)
                elif row['state'] not in ('pending','processing'):
                    conn.execute('DELETE FROM pending_ingest WHERE job_id=?',(row['job_id'],))
        self.watcher_thread = threading.Thread(target=self.watch_loop, daemon=True, name='tomeshed-ingest')
        self.watcher_thread.start()

    def watch_loop(self):
        while not self.stop_event.is_set():
            try:
                self.scan_once()
            except Exception as exc:
                LOG.error('Watched inbox scan failed for %s: %s', self.inbox, exc)
            self.stop_event.wait(self.scan_seconds)

    def scan_once(self, now=None):
        if not self.inbox:
            return
        now = time.monotonic() if now is None else now
        visible = set()
        try:
            entries = list(os.scandir(self.inbox))
        except OSError as exc:
            LOG.error('Watched inbox scan failed for %s: %s', self.inbox, exc)
            return
        for entry in entries:
            if entry.name.lower().endswith(TEMP_SUFFIXES):
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISREG(metadata.st_mode):
                    self.handoffs[signature(metadata)] = (entry.path, now)
        self.handoffs = {sig:item for sig,item in self.handoffs.items()
                         if now - item[1] <= max(self.settle_seconds,self.scan_seconds) * 3}
        with self.db() as conn:
            receipts = {row['source_path']:row['signature'] for row in conn.execute('SELECT source_path,signature FROM ingest_receipts')}
            pending = {(row['source_path'], row['signature']) for row in conn.execute('SELECT source_path,signature FROM pending_ingest')}
        for entry in entries:
            name = entry.name
            if name.startswith('.') or name.lower().endswith(TEMP_SUFFIXES):
                continue
            try:
                meta = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if not stat.S_ISREG(meta.st_mode):
                continue
            path = str(self.inbox / name)
            sig = signature(meta)
            encoded = json.dumps(sig)
            visible.add(path)
            if (path, encoded) in pending:
                continue
            if receipts.get(path) == encoded:
                self.candidates.pop(path, None)
                continue
            candidate = self.candidates.get(path)
            if not candidate or candidate['signature'] != sig:
                handoff = sig in self.handoffs and not Path(self.handoffs[sig][0]).exists()
                self.candidates[path] = {'signature':sig,'since':now-self.settle_seconds if handoff else now,
                                         'observations':3 if handoff else 1,'failed':False}
                if not handoff:
                    continue
                candidate = self.candidates[path]
                self.handoffs.pop(sig,None)
            candidate['observations'] += 1
            if candidate['failed'] or candidate['observations'] < 3 or now - candidate['since'] < self.settle_seconds or (path, sig) in self.inflight:
                continue
            self.inflight.add((path,sig))
            try:
                self.ingest(path, sig)
                self.candidates.pop(path,None)
            except SourceChanged:
                self.candidates.pop(path,None)
            except Exception as exc:
                candidate['failed'] = True
                LOG.error('Watched inbox import failed for %s: %s', path, exc)
            finally:
                self.inflight.discard((path,sig))
        for path in set(self.candidates)-visible:
            self.candidates.pop(path,None)
        with self.db() as conn:
            for path in set(receipts)-visible:
                conn.execute('DELETE FROM ingest_receipts WHERE source_path=?',(path,))

    def path_signature(self,path):
        meta = os.stat(path,follow_symlinks=False)
        if not stat.S_ISREG(meta.st_mode):
            raise SourceChanged()
        return signature(meta)

    def ingest(self,path,sig):
        if self.path_signature(path) != sig:
            raise SourceChanged()
        name = Path(path).name
        flags = os.O_RDONLY | getattr(os,'O_NOFOLLOW',0)
        fd = os.open(path,flags)
        job_id = None
        temporary = self.root / 'staging' / f'.watch-{uuid.uuid4().hex}.part'
        try:
            with os.fdopen(fd,'rb') as source:
                if signature(os.fstat(source.fileno())) != sig:
                    raise SourceChanged()
                with temporary.open('xb') as output:
                    shutil.copyfileobj(source,output,1024*1024)
                if signature(os.fstat(source.fileno())) != sig or self.path_signature(path) != sig:
                    raise SourceChanged()
            if temporary.stat().st_size > self.app.config['MAX_UPLOAD_BYTES']:
                raise ValueError('Watched source exceeds upload size limit')
            detect_source(temporary)
            if self.path_signature(path) != sig:
                raise SourceChanged()
            job_id, document_id, stored = self.register(name,'watch',watch_path=path,watch_signature=sig)
            os.replace(temporary,self.root/stored)
            with self.db() as conn:
                conn.execute('UPDATE import_jobs SET transfer_complete=1,bytes_received=?,updated_at=? WHERE id=?',
                             (sig[2],time.time(),job_id))
            self.library.pool.submit(self.library._process_job,job_id)
        except Exception:
            temporary.unlink(missing_ok=True)
            if job_id:
                self.fail(job_id,'Watched import failed')
            raise

    def record_receipt(self,job_id,document_id,conn):
        row = conn.execute('SELECT * FROM pending_ingest WHERE job_id=?',(job_id,)).fetchone()
        if row:
            conn.execute('''INSERT OR REPLACE INTO ingest_receipts(source_path,signature,document_id,created_at)
                            VALUES (?,?,?,?)''',(row['source_path'],row['signature'],document_id,time.time()))
            conn.execute('DELETE FROM pending_ingest WHERE job_id=?',(job_id,))

    def watched_failed(self, job_id, reason):
        with self.db() as conn:
            row = conn.execute('SELECT * FROM pending_ingest WHERE job_id=?',(job_id,)).fetchone()
            if row:
                conn.execute('DELETE FROM pending_ingest WHERE job_id=?',(job_id,))
        if row:
            try:
                sig = tuple(json.loads(row['signature']))
                self.candidates[row['source_path']] = {'signature':sig,'since':time.monotonic(),
                                                        'observations':3,'failed':True}
            except (TypeError, ValueError):
                pass
            LOG.error('Watched inbox import failed for %s: %s', row['source_path'], reason)
