"""Personal bookshelf membership, sharing, and per-user resume bookmarks."""

from __future__ import annotations

import time
import unicodedata
import uuid

from flask import abort, g, jsonify, request


def valid_name(value):
    if not isinstance(value, str) or any(unicodedata.category(char).startswith('C') for char in value):
        raise ValueError('Bookshelf name must contain 1 to 120 visible characters')
    name = value.strip()
    if not 1 <= len(name) <= 120:
        raise ValueError('Bookshelf name must contain 1 to 120 visible characters')
    return name


def revision(value, allow_zero=False):
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise ValueError('Expected revision is required')
    return value


class BookshelfService:
    def __init__(self, library):
        self.library = library
        self.db = library.db
        self.app = library.app
        self._schema()
        self._routes()

    def _schema(self):
        with self.db() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS bookshelf_orders (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    revision INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS bookshelves (
                    id TEXT PRIMARY KEY, owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL, position INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS bookshelves_owner_order ON bookshelves(owner_user_id,position);
                CREATE TABLE IF NOT EXISTS bookshelf_members (
                    id TEXT PRIMARY KEY, bookshelf_id TEXT NOT NULL REFERENCES bookshelves(id) ON DELETE CASCADE,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL, UNIQUE(bookshelf_id,document_id)
                );
                CREATE INDEX IF NOT EXISTS bookshelf_members_order ON bookshelf_members(bookshelf_id,position);
                CREATE TABLE IF NOT EXISTS bookshelf_shares (
                    bookshelf_id TEXT NOT NULL REFERENCES bookshelves(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    PRIMARY KEY(bookshelf_id,user_id)
                );
                CREATE TABLE IF NOT EXISTS bookshelf_bookmarks (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    bookshelf_id TEXT NOT NULL REFERENCES bookshelves(id) ON DELETE CASCADE,
                    document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(user_id,bookshelf_id)
                );
            ''')

    def _row(self, conn, shelf_id, user_id, mutate=False):
        row = conn.execute('SELECT * FROM bookshelves WHERE id=?', (shelf_id,)).fetchone()
        if row is None:
            abort(404)
        if row['owner_user_id'] == user_id:
            return row
        share = conn.execute('SELECT 1 FROM bookshelf_shares WHERE bookshelf_id=? AND user_id=?', (shelf_id,user_id)).fetchone()
        if not share:
            abort(404)
        if mutate:
            abort(403)
        return row

    def _owned(self, conn, shelf_id, user_id):
        return self._row(conn, shelf_id, user_id, True)

    def _order_revision(self, conn, user_id):
        row = conn.execute('SELECT revision FROM bookshelf_orders WHERE user_id=?', (user_id,)).fetchone()
        return row['revision'] if row else 0

    def _bump_order(self, conn, user_id):
        conn.execute('INSERT INTO bookshelf_orders(user_id,revision) VALUES (?,1) ON CONFLICT(user_id) DO UPDATE SET revision=revision+1', (user_id,))

    def _members(self, conn, shelf_id):
        return conn.execute('''SELECT m.id AS member_id,m.document_id,m.position,d.* FROM bookshelf_members m
            LEFT JOIN documents d ON d.id=m.document_id WHERE m.bookshelf_id=? ORDER BY m.position,m.id''', (shelf_id,)).fetchall()

    def _present(self, row):
        try:
            self.library.safe_path(row['source_path'])
            return True
        except Exception:
            return False

    def _detail(self, conn, shelf, user_id):
        owned = shelf['owner_user_id'] == user_id
        visible = []
        editor = []
        for member in self._members(conn, shelf['id']):
            accessible = member['id'] is not None and self.library.can_access_document(member, user_id)
            if accessible:
                item = self.library.organization.public_document(member, user_id, conn)
                item['position'] = len(visible)
                item['member_id'] = member['member_id']
                visible.append(item)
                editor.append({'member_id':member['member_id'],'document':item,'unavailable':False})
            elif owned:
                editor.append({'member_id':member['member_id'],'document':None,'unavailable':True})
        bookmark = conn.execute('SELECT document_id FROM bookshelf_bookmarks WHERE user_id=? AND bookshelf_id=?', (user_id,shelf['id'])).fetchone()
        usable = [item for item in visible if item['source_available']]
        selected = next((item for item in usable if bookmark and item['id']==bookmark['document_id']), None)
        if selected is None:
            selected = usable[0] if usable else None
        result = {'id':shelf['id'],'name':shelf['name'],'owner_user_id':shelf['owner_user_id'],
                  'owned':owned,'position':shelf['position'],'revision':shelf['revision'],
                  'count':len(visible),'covers':[item['id'] for item in visible if item['thumbnail_available']][:4],
                  'members':visible,'continue_document_id':selected['id'] if selected else None,
                  'bookmark_document_id':bookmark['document_id'] if bookmark and any(item['id']==bookmark['document_id'] for item in usable) else None}
        if owned:
            result['editor_members']=editor
            result['shares']=[dict(row) for row in conn.execute('''SELECT u.id,u.username FROM users u JOIN bookshelf_shares s ON s.user_id=u.id
                WHERE s.bookshelf_id=? ORDER BY u.username''',(shelf['id'],))]
        return result

    def _valid_members(self, conn, shelf_id, values, user_id):
        if not isinstance(values, list):
            raise ValueError('Members must be a list')
        existing = {row['member_id']:row for row in self._members(conn,shelf_id)} if shelf_id else {}
        selected=[]; seen=set()
        for value in values:
            if isinstance(value,dict) and isinstance(value.get('member_id'),str):
                member=existing.get(value['member_id'])
                if not member or member['id'] is not None and self.library.can_access_document(member,user_id):
                    raise ValueError('Unavailable member is invalid')
                doc_id=member['document_id']; member_id=member['member_id']
            elif isinstance(value,str):
                row=conn.execute('SELECT * FROM documents WHERE id=?',(value,)).fetchone()
                if row is None or not self.library.can_access_document(row,user_id):
                    abort(404)
                if row['state'] not in ('ready','ready_with_warning'):
                    raise ValueError('Every member must be an accessible ready document')
                doc_id=value
                found=next((row for row in existing.values() if row['document_id']==value),None)
                member_id=found['member_id'] if found else uuid.uuid4().hex
            else:
                raise ValueError('Member must be a document ID or unavailable member token')
            if doc_id in seen:
                raise ValueError('A document may occur only once in a bookshelf')
            seen.add(doc_id); selected.append((member_id,doc_id))
        return selected

    def _replace_members(self, conn, shelf_id, members):
        conn.execute('DELETE FROM bookshelf_members WHERE bookshelf_id=?',(shelf_id,))
        for position,(member_id,doc_id) in enumerate(members):
            conn.execute('INSERT INTO bookshelf_members(id,bookshelf_id,document_id,position) VALUES (?,?,?,?)',
                         (member_id,shelf_id,doc_id,position))

    def bookmark_open(self, conn, shelf_id, document_id, user_id):
        self._row(conn,shelf_id,user_id)
        member=conn.execute('SELECT 1 FROM bookshelf_members WHERE bookshelf_id=? AND document_id=?',(shelf_id,document_id)).fetchone()
        if member is None:
            abort(404)
        row=conn.execute('SELECT * FROM documents WHERE id=?',(document_id,)).fetchone()
        if row is None or not self.library.can_access_document(row,user_id):
            abort(404)
        self.library.safe_path(row['source_path'])
        conn.execute('''INSERT INTO bookshelf_bookmarks(user_id,bookshelf_id,document_id,updated_at) VALUES (?,?,?,?)
            ON CONFLICT(user_id,bookshelf_id) DO UPDATE SET document_id=excluded.document_id,updated_at=excluded.updated_at''',
            (user_id,shelf_id,document_id,time.time()))

    def compact_removed_document(self, conn, document_id):
        shelves=[row['bookshelf_id'] for row in conn.execute('SELECT DISTINCT bookshelf_id FROM bookshelf_members WHERE document_id=?',(document_id,))]
        conn.execute('DELETE FROM bookshelf_bookmarks WHERE document_id=?',(document_id,))
        conn.execute('DELETE FROM bookshelf_members WHERE document_id=?',(document_id,))
        for shelf_id in shelves:
            for position,row in enumerate(conn.execute('SELECT id FROM bookshelf_members WHERE bookshelf_id=? ORDER BY position,id',(shelf_id,))):
                conn.execute('UPDATE bookshelf_members SET position=? WHERE id=?',(position,row['id']))
            conn.execute('UPDATE bookshelves SET revision=revision+1 WHERE id=?',(shelf_id,))

    def _routes(self):
        app=self.app
        library=self.library

        @app.get('/api/bookshelves')
        def list_bookshelves():
            user_id=g.current_user['id']
            with self.db() as conn:
                owned=conn.execute('SELECT * FROM bookshelves WHERE owner_user_id=? ORDER BY position,id',(user_id,)).fetchall()
                shared=conn.execute('''SELECT b.* FROM bookshelves b JOIN bookshelf_shares s ON s.bookshelf_id=b.id
                    WHERE s.user_id=? ORDER BY b.name,b.id''',(user_id,)).fetchall()
                return jsonify(owned=[self._detail(conn,row,user_id) for row in owned],
                    shared=[self._detail(conn,row,user_id) for row in shared],
                    order_revision=self._order_revision(conn,user_id))

        @app.post('/api/bookshelves')
        def create_bookshelf():
            data=request.get_json(silent=True) or {}
            try:
                name=valid_name(data.get('name'))
                values=data.get('members',[])
                if not isinstance(values,list): raise ValueError('Members must be a list')
            except ValueError as exc:
                return jsonify(error=str(exc)),400
            user_id=g.current_user['id']; shelf_id=uuid.uuid4().hex
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                try:
                    members=self._valid_members(conn,None,values,user_id)
                except ValueError as exc:
                    return jsonify(error=str(exc)),400
                position=conn.execute('SELECT COUNT(*) FROM bookshelves WHERE owner_user_id=?',(user_id,)).fetchone()[0]
                conn.execute('INSERT INTO bookshelves(id,owner_user_id,name,position,created_at) VALUES (?,?,?,?,?)',(shelf_id,user_id,name,position,time.time()))
                self._replace_members(conn,shelf_id,members)
                self._bump_order(conn,user_id)
                result=self._detail(conn,conn.execute('SELECT * FROM bookshelves WHERE id=?',(shelf_id,)).fetchone(),user_id)
            library.publish()
            return jsonify(result),201

        @app.put('/api/bookshelves/order')
        def order_bookshelves():
            data=request.get_json(silent=True) or {}
            try:
                expected=revision(data.get('expected_revision'),True)
                ids=data.get('ids')
                if not isinstance(ids,list) or not all(isinstance(item,str) for item in ids) or len(ids)!=len(set(ids)):
                    raise ValueError('Bookshelf IDs must be unique')
            except ValueError as exc:
                return jsonify(error=str(exc)),400
            user_id=g.current_user['id']
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                for shelf_id in ids:
                    shelf=conn.execute('SELECT owner_user_id FROM bookshelves WHERE id=?',(shelf_id,)).fetchone()
                    if shelf is None:
                        abort(404)
                    if shelf['owner_user_id']==user_id:
                        continue
                    shared=conn.execute('SELECT 1 FROM bookshelf_shares WHERE bookshelf_id=? AND user_id=?',(shelf_id,user_id)).fetchone()
                    if shared: abort(403)
                    abort(404)
                current=self._order_revision(conn,user_id)
                if current!=expected:
                    return jsonify(error='Bookshelf order changed',order_revision=current),409
                actual=[row['id'] for row in conn.execute('SELECT id FROM bookshelves WHERE owner_user_id=?',(user_id,))]
                if set(ids)!=set(actual): return jsonify(error='Bookshelf order does not match owned bookshelves'),400
                for position,shelf_id in enumerate(ids):
                    conn.execute('UPDATE bookshelves SET position=? WHERE id=?',(position,shelf_id))
                self._bump_order(conn,user_id)
                updated=self._order_revision(conn,user_id)
            library.publish()
            return jsonify(order_revision=updated,ids=ids)

        @app.get('/api/bookshelves/<shelf_id>')
        def get_bookshelf(shelf_id):
            with self.db() as conn:
                return jsonify(self._detail(conn,self._row(conn,shelf_id,g.current_user['id']),g.current_user['id']))

        @app.put('/api/bookshelves/<shelf_id>')
        def edit_bookshelf(shelf_id):
            data=request.get_json(silent=True) or {}
            try:
                name=valid_name(data.get('name'))
                expected=revision(data.get('expected_revision'))
            except ValueError as exc:
                return jsonify(error=str(exc)),400
            user_id=g.current_user['id']
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                row=self._owned(conn,shelf_id,user_id)
                if row['revision']!=expected:
                    return jsonify(error='Bookshelf changed',current=self._detail(conn,row,user_id)),409
                try: members=self._valid_members(conn,shelf_id,data.get('members'),user_id)
                except ValueError as exc: return jsonify(error=str(exc)),400
                self._replace_members(conn,shelf_id,members)
                conn.execute('UPDATE bookshelves SET name=?,revision=revision+1 WHERE id=?',(name,shelf_id))
                result=self._detail(conn,conn.execute('SELECT * FROM bookshelves WHERE id=?',(shelf_id,)).fetchone(),user_id)
            library.publish()
            return jsonify(result)

        @app.post('/api/bookshelves/<shelf_id>/members')
        def add_member(shelf_id):
            data=request.get_json(silent=True) or {}
            doc_id=data.get('document_id')
            if not isinstance(doc_id,str): return jsonify(error='Document ID is required'),400
            user_id=g.current_user['id']
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                row=self._owned(conn,shelf_id,user_id)
                requested=conn.execute('SELECT * FROM documents WHERE id=?',(doc_id,)).fetchone()
                if requested is None or not library.can_access_document(requested,user_id):
                    abort(404)
                if requested['state'] not in ('ready','ready_with_warning'):
                    return jsonify(error='Every member must be an accessible ready document'),400
                existing=self._members(conn,shelf_id)
                if doc_id not in [member['document_id'] for member in existing]:
                    tokens=[member['document_id'] if member['id'] is not None and library.can_access_document(member,user_id)
                            else {'member_id':member['member_id']} for member in existing]
                    try: selected=self._valid_members(conn,shelf_id,tokens+[doc_id],user_id)
                    except ValueError as exc: return jsonify(error=str(exc)),400
                    self._replace_members(conn,shelf_id,selected)
                    conn.execute('UPDATE bookshelves SET revision=revision+1 WHERE id=?',(shelf_id,))
                result=self._detail(conn,conn.execute('SELECT * FROM bookshelves WHERE id=?',(shelf_id,)).fetchone(),user_id)
            library.publish()
            return jsonify(result)

        @app.delete('/api/bookshelves/<shelf_id>')
        def delete_bookshelf(shelf_id):
            data=request.get_json(silent=True) or {}
            user_id=g.current_user['id']
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                row=self._owned(conn,shelf_id,user_id)
                if data.get('confirm')!=row['name']:
                    return jsonify(error='Confirm deletion with the bookshelf name'),400
                conn.execute('DELETE FROM bookshelves WHERE id=?',(shelf_id,))
                for position,item in enumerate(conn.execute('SELECT id FROM bookshelves WHERE owner_user_id=? ORDER BY position,id',(user_id,))):
                    conn.execute('UPDATE bookshelves SET position=? WHERE id=?',(position,item['id']))
                self._bump_order(conn,user_id)
            library.publish()
            return jsonify(deleted=shelf_id)

        @app.post('/api/bookshelves/<shelf_id>/shares')
        def share_bookshelf(shelf_id):
            data=request.get_json(silent=True) or {}
            username=data.get('username')
            if not isinstance(username,str) or not username.strip(): return jsonify(error='Username is required'),400
            user_id=g.current_user['id']
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                self._owned(conn,shelf_id,user_id)
                target=conn.execute('SELECT id FROM users WHERE username=? COLLATE BINARY AND suspended=0 AND password_hash IS NOT NULL',(username,)).fetchone()
                if target is None or target['id']==user_id: return jsonify(error='Active recipient not found'),400
                conn.execute('INSERT OR IGNORE INTO bookshelf_shares(bookshelf_id,user_id) VALUES (?,?)',(shelf_id,target['id']))
                result=self._detail(conn,conn.execute('SELECT * FROM bookshelves WHERE id=?',(shelf_id,)).fetchone(),user_id)
            library.publish()
            return jsonify(result)

        @app.delete('/api/bookshelves/<shelf_id>/shares/<int:recipient_id>')
        def revoke_bookshelf(shelf_id,recipient_id):
            user_id=g.current_user['id']
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                self._owned(conn,shelf_id,user_id)
                conn.execute('DELETE FROM bookshelf_shares WHERE bookshelf_id=? AND user_id=?',(shelf_id,recipient_id))
                result=self._detail(conn,conn.execute('SELECT * FROM bookshelves WHERE id=?',(shelf_id,)).fetchone(),user_id)
            library.publish()
            return jsonify(result)

        @app.post('/api/bookshelves/<shelf_id>/continue')
        def continue_bookshelf(shelf_id):
            user_id=g.current_user['id']
            with self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                row=self._row(conn,shelf_id,user_id)
                result=self._detail(conn,row,user_id)
                selected=result['continue_document_id']
                if result['bookmark_document_id'] is None:
                    conn.execute('DELETE FROM bookshelf_bookmarks WHERE user_id=? AND bookshelf_id=?',(user_id,shelf_id))
            if selected is None: return jsonify(error='No accessible document has a source file'),409
            return jsonify(document_id=selected)
