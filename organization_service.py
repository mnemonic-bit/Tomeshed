"""Catalog organization, discovery, and per-user reading state."""

from __future__ import annotations

import re
import sqlite3
import time
import unicodedata

from flask import abort, g, jsonify, request


def normalize_tag(value):
    if not isinstance(value, str):
        raise ValueError("Tag must be text")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("Tag must not contain control characters")
    display = re.sub(r"\s+", " ", value).strip()
    if not display or "," in display or len(display) > 64:
        raise ValueError("Tag must contain 1 to 64 characters and no commas")
    return display, display.casefold()


class OrganizationService:
    def __init__(self, library):
        self.library = library
        self.db = library.db
        self.app = library.app
        self._schema()
        self._routes()

    def _schema(self):
        with self.db() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
            for name, definition in (
                ("corrected_title", "TEXT"),
                ("corrected_author", "TEXT"),
                ("favorite", "INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0,1))"),
            ):
                if name not in columns:
                    conn.execute(f"ALTER TABLE documents ADD COLUMN {name} {definition}")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, normalized_name TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS document_tags (
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                    PRIMARY KEY(document_id, tag_id)
                );
                CREATE INDEX IF NOT EXISTS document_tags_tag ON document_tags(tag_id);
                CREATE TABLE IF NOT EXISTS reader_opens (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    opened_at REAL NOT NULL,
                    PRIMARY KEY(user_id, document_id)
                );
            """)

    def _document(self, conn, document_id):
        row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if row is None or not self.library.can_access_document(row, g.current_user["id"]):
            abort(404)
        return row

    @staticmethod
    def _tags(conn, document_id):
        return [row["name"] for row in conn.execute("""
            SELECT tags.name FROM tags JOIN document_tags ON document_tags.tag_id=tags.id
            WHERE document_tags.document_id=? ORDER BY tags.normalized_name
        """, (document_id,))]

    @staticmethod
    def _reading(conn, document_id, user_id):
        opened = conn.execute("SELECT opened_at FROM reader_opens WHERE user_id=? AND document_id=?", (user_id, document_id)).fetchone()
        completed = conn.execute("SELECT completed FROM reading_positions WHERE user_id=? AND document_id=?", (user_id, document_id)).fetchone()
        state = "finished" if completed and completed["completed"] else "in_progress" if opened else "unread"
        return state, opened["opened_at"] if opened else None

    def public_document(self, row, user_id, conn=None):
        if conn is None:
            with self.db() as own:
                return self.public_document(row, user_id, own)
        state, last_read = self._reading(conn, row["id"], user_id)
        from file_workflows import display_url, valid_docling_json
        try:
            source = self.library.safe_path(row["source_path"])
        except Exception:
            source = None
        try:
            artifact = self.library.safe_path(row["artifact_path"]) if row["artifact_path"] else None
        except Exception:
            artifact = None
        return {key: row[key] for key in (
            "id", "original_filename", "source_type", "byte_size", "page_count",
            "count_kind", "state", "error", "created_at"
        )} | {
            "title": row["corrected_title"] if row["corrected_title"] is not None else row["title"],
            "author": row["corrected_author"] if row["corrected_author"] is not None else row["author"],
            "favorite": bool(row["favorite"]),
            "tags": self._tags(conn, row["id"]),
            "reading_state": state,
            "last_read_at": last_read,
            "thumbnail_available": bool(row["thumbnail_path"]),
            "stored_filename": source.name if source and source.suffix != ".source" else row["original_filename"],
            "source_available": source is not None,
            "structured_available": valid_docling_json(source) if source and row["source_type"] == "docling" else valid_docling_json(artifact) if artifact else False,
            "source_url": display_url(row["source_url"]) if row["source_url"] else None,
            "owner_user_id": row["owner_user_id"],
            "visibility": row["visibility"],
            "can_manage_visibility": self.library.can_manage_document(row, user_id),
        }

    def suggestions(self, conn, user_id):
        visible = [row["id"] for row in conn.execute("SELECT * FROM documents") if self.library.can_access_document(row, user_id)]
        if not visible:
            return []
        placeholders = ",".join("?" for _ in visible)
        return [row["name"] for row in conn.execute(f"""
            SELECT DISTINCT tags.name, tags.normalized_name FROM tags
            JOIN document_tags ON document_tags.tag_id=tags.id
            WHERE document_tags.document_id IN ({placeholders}) ORDER BY tags.normalized_name
        """, visible)]

    @staticmethod
    def _filter_params():
        args = request.args
        source = args.get("type", "").strip().lower()
        author = args.get("author", "").strip().casefold()[:200]
        favorite = args.get("favorite", "")
        state = args.get("reading_state", "")
        mode = args.get("tag_mode", "ALL").upper()
        sort = args.get("sort", "date_added")
        direction = args.get("direction", "desc" if sort in ("date_added", "newest", "favorite") else "asc")
        if sort == "newest":
            sort = "date_added"
        tags = [normalize_tag(tag)[1] for tag in args.getlist("tag")]
        if source not in ("", "pdf", "epub", "docling") or favorite not in ("", "true", "false") or state not in ("", "unread", "in_progress", "finished") or mode not in ("ALL", "ANY") or sort not in ("date_added", "title", "author", "type", "favorite") or direction not in ("asc", "desc"):
            raise ValueError("Invalid catalog filter")
        if len(tags) > 30:
            raise ValueError("Too many selected tags")
        return source, author, favorite, state, mode, sort, direction, set(tags)

    def catalog(self):
        try:
            offset = int(request.args.get("offset", "0"))
            requested = int(request.args.get("limit", self.app.config["CATALOG_PAGE_SIZE"]))
            if offset < 0 or requested < 1:
                raise ValueError("Invalid catalog page")
            source, author, favorite, state, mode, sort, direction, tags = self._filter_params()
            scope = request.args.get("scope", "all")
            if scope not in ("all", "documents", "bookshelves"):
                raise ValueError("Invalid catalog scope")
        except (ValueError, TypeError) as exc:
            return jsonify(error=str(exc)), 400
        limit = min(requested, max(1, int(self.app.config["CATALOG_PAGE_SIZE"])))
        query = request.args.get("q", "").strip().casefold()[:200]
        user_id = g.current_user["id"]
        with self.db() as conn:
            all_rows = [row for row in conn.execute("SELECT * FROM documents") if self.library.can_access_document(row, user_id)]
            documents = []
            document_rows = all_rows if scope != "bookshelves" else ()
            for row in document_rows:
                public = self.public_document(row, user_id, conn)
                if query and not any(query in str(value).casefold() for value in (public["title"], public["author"], row["original_filename"], row["text_content"])):
                    continue
                if source and row["source_type"] != source:
                    continue
                if author and author not in public["author"].casefold():
                    continue
                if favorite and public["favorite"] != (favorite == "true"):
                    continue
                if state and public["reading_state"] != state:
                    continue
                names = {name.casefold() for name in public["tags"]}
                if tags and not (tags <= names if mode == "ALL" else bool(tags & names)):
                    continue
                documents.append(public | {"kind": "document"})
            shelves = []
            if scope != "documents" and not (source or author or favorite or state or tags):
                shelves = [item for item in self.library.bookshelves.catalog_items(conn, user_id)
                           if not query or query in item["name"].casefold()]
            results = documents + shelves
            results.sort(key=lambda item: item["id"])
            if sort == "date_added":
                results.sort(key=lambda item: (item["created_at"], (item["name"] if item["kind"] == "bookshelf" else item["title"]).casefold()), reverse=direction == "desc")
            elif sort == "favorite":
                results.sort(key=lambda item: item["created_at"], reverse=True)
                results.sort(key=lambda item: bool(item["favorite"]), reverse=direction == "desc")
            else:
                def sort_text(item):
                    if sort == "title":
                        return item["name"] if item["kind"] == "bookshelf" else item["title"]
                    if sort == "author":
                        return "" if item["kind"] == "bookshelf" else item["author"]
                    return "bookshelf" if item["kind"] == "bookshelf" else item["source_type"]

                results.sort(key=lambda item: (sort_text(item) or "").casefold(), reverse=direction == "desc")
                if sort == "author":
                    results.sort(key=lambda item: not bool((sort_text(item) or "").strip()))
            page = results[offset:offset + limit]
            return jsonify(items=page, documents=[item for item in page if item["kind"] == "document"],
                           total=len(results), library_total=len(all_rows), bookshelf_total=len(shelves),
                           offset=offset, limit=limit, available_tags=self.suggestions(conn, user_id))

    def _routes(self):
        app = self.app

        @app.get("/api/documents")
        def catalog():
            return self.catalog()

        @app.get("/api/tags")
        def tag_suggestions():
            with self.db() as conn:
                return jsonify(tags=self.suggestions(conn, g.current_user["id"]))

        @app.route("/api/documents/<document_id>/tags", methods=["POST", "DELETE"])
        def document_tags(document_id):
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify(error="A JSON object is required"), 400
            try:
                display, normalized = normalize_tag(data.get("tag"))
            except ValueError as exc:
                return jsonify(error=str(exc)), 400
            with self.db() as conn:
                conn.execute("BEGIN IMMEDIATE")
                self._document(conn, document_id)
                if request.method == "POST":
                    conn.execute("INSERT OR IGNORE INTO tags(name,normalized_name) VALUES (?,?)", (display, normalized))
                    conn.execute("INSERT OR IGNORE INTO document_tags(document_id,tag_id) SELECT ?,id FROM tags WHERE normalized_name=?", (document_id, normalized))
                else:
                    conn.execute("DELETE FROM document_tags WHERE document_id=? AND tag_id IN (SELECT id FROM tags WHERE normalized_name=?)", (document_id, normalized))
                    conn.execute("DELETE FROM tags WHERE NOT EXISTS (SELECT 1 FROM document_tags WHERE tag_id=tags.id)")
                result = self.public_document(self._document(conn, document_id), g.current_user["id"], conn)
                suggestions = self.suggestions(conn, g.current_user["id"])
            self.library.publish()
            return jsonify(document=result, available_tags=suggestions)

        @app.patch("/api/documents/<document_id>/favorite")
        def favorite(document_id):
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or type(data.get("favorite")) is not bool:
                return jsonify(error="Favorite must be true or false"), 400
            with self.db() as conn:
                conn.execute("BEGIN IMMEDIATE")
                self._document(conn, document_id)
                conn.execute("UPDATE documents SET favorite=? WHERE id=?", (int(data["favorite"]), document_id))
                result = self.public_document(self._document(conn, document_id), g.current_user["id"], conn)
            self.library.publish()
            return jsonify(document=result)

        @app.patch("/api/documents/<document_id>/metadata")
        def metadata(document_id):
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or set(data) != {"title", "author"}:
                return jsonify(error="Title and author are required"), 400
            title, author = data["title"], data["author"]
            if not isinstance(title, str) or not isinstance(author, str) or not title.strip() or len(title.strip()) > 300 or len(author.strip()) > 300 or any(unicodedata.category(c).startswith("C") for c in title + author):
                return jsonify(error="Enter a title and author of at most 300 characters without control characters"), 400
            with self.db() as conn:
                conn.execute("BEGIN IMMEDIATE")
                self._document(conn, document_id)
                conn.execute("UPDATE documents SET corrected_title=?,corrected_author=? WHERE id=?", (title.strip(), author.strip(), document_id))
                result = self.public_document(self._document(conn, document_id), g.current_user["id"], conn)
            self.library.publish()
            return jsonify(document=result)

        @app.post("/api/documents/<document_id>/reader-open")
        def reader_open(document_id):
            data = request.get_json(silent=True) or {}
            shelf_id = data.get('bookshelf_id')
            with self.db() as conn:
                conn.execute("BEGIN IMMEDIATE")
                source = self._document(conn, document_id)
                self.library.safe_path(source["source_path"])
                if shelf_id is not None:
                    self.library.bookshelves.bookmark_open(conn, shelf_id, document_id, g.current_user['id'])
                now = time.time()
                conn.execute("""INSERT INTO reader_opens(user_id,document_id,opened_at) VALUES (?,?,?)
                    ON CONFLICT(user_id,document_id) DO UPDATE SET opened_at=excluded.opened_at""",
                    (g.current_user["id"], document_id, now))
                result = self.public_document(self._document(conn, document_id), g.current_user["id"], conn)
            return jsonify(document=result)

        @app.patch('/api/documents/<document_id>/visibility')
        def visibility(document_id):
            data = request.get_json(silent=True) or {}
            if data.get('visibility') not in ('public', 'private'):
                return jsonify(error='Visibility must be public or private'), 400
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
                if row is None:
                    abort(404)
                if not self.library.can_manage_document(row, g.current_user['id']):
                    abort(403)
                conn.execute('UPDATE documents SET visibility=? WHERE id=?', (data['visibility'], document_id))
                result = self.public_document(conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone(), g.current_user['id'], conn)
            self.library.publish()
            return jsonify(document=result)
