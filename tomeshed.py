"""Tomeshed application shell and account boundary."""

from __future__ import annotations

import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
STARTED = time.monotonic()
app = Flask(__name__)
app.config.update(
    VERSION=VERSION,
    DATABASE=os.environ.get("TOMESHED_DB", str(ROOT / "data" / "tomeshed.db")),
    LIBRARY_DIR=os.environ.get("TOMESHED_LIBRARY_DIR"),
    MAX_UPLOAD_BYTES=int(os.environ.get("TOMESHED_MAX_UPLOAD_BYTES", 100 * 1024 * 1024)),
    CONVERSION_TIMEOUT=int(os.environ.get("TOMESHED_CONVERSION_TIMEOUT", 180)),
    CONVERSION_WORKERS=int(os.environ.get("TOMESHED_CONVERSION_WORKERS", 2)),
    CATALOG_PAGE_SIZE=int(os.environ.get("TOMESHED_CATALOG_PAGE_SIZE", 50)),
    PREVIEW_CACHE_LOCATIONS=int(os.environ.get("TOMESHED_PREVIEW_CACHE_LOCATIONS", 32)),
    PREVIEW_PDF_MAX_WIDTH=int(os.environ.get("TOMESHED_PREVIEW_PDF_MAX_WIDTH", 720)),
    PREVIEW_PDF_MAX_HEIGHT=int(os.environ.get("TOMESHED_PREVIEW_PDF_MAX_HEIGHT", 960)),
    PREVIEW_TEXT_CHARS=int(os.environ.get("TOMESHED_PREVIEW_TEXT_CHARS", 1400)),
    PREVIEW_IMAGE_LIMIT=int(os.environ.get("TOMESHED_PREVIEW_IMAGE_LIMIT", 2)),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


@contextmanager
def db():
    conn = sqlite3.connect(app.config["DATABASE"], timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create or migrate the account schema without replacing existing data."""
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL,
                password_hash TEXT,
                suspended INTEGER NOT NULL DEFAULT 0 CHECK (suspended IN (0, 1)),
                session_version INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role_id INTEGER NOT NULL REFERENCES roles(id),
                PRIMARY KEY (user_id, role_id)
            );
            CREATE TABLE IF NOT EXISTS preferences (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                theme TEXT NOT NULL DEFAULT 'system'
                    CHECK (theme IN ('light', 'dark', 'system')),
                page_size TEXT NOT NULL DEFAULT '10'
                    CHECK (page_size IN ('5', '10', '20', '50', 'endless'))
            );
        """)
        if "page_size" not in {row[1] for row in conn.execute("PRAGMA table_info(preferences)")}:
            conn.execute("""ALTER TABLE preferences ADD COLUMN page_size TEXT NOT NULL DEFAULT '10'
                            CHECK (page_size IN ('5', '10', '20', '50', 'endless'))""")
        for role in ("normal", "admin"):
            conn.execute("INSERT OR IGNORE INTO roles(name) VALUES (?)", (role,))
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            cursor = conn.execute(
                "INSERT INTO users(username, name, created_at) VALUES ('admin', 'Administrator', ?)",
                (time.time(),),
            )
            conn.execute(
                "INSERT INTO user_roles(user_id, role_id) "
                "SELECT ?, id FROM roles WHERE name = 'admin'", (cursor.lastrowid,)
            )
        conn.execute(
            "INSERT OR IGNORE INTO app_config(key, value) VALUES ('secret_key', ?)",
            (secrets.token_hex(32),),
        )
        app.secret_key = conn.execute(
            "SELECT value FROM app_config WHERE key = 'secret_key'"
        ).fetchone()[0]


def user_by_id(conn, user_id):
    if user_id is None:
        return None
    row = conn.execute("""
        SELECT u.*, r.name AS role FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id WHERE u.id = ?
    """, (user_id,)).fetchone()
    return dict(row) if row else None


def public_user(user):
    return {key: user[key] for key in ("id", "username", "name", "role", "suspended")}


def active_admin_count(conn):
    return conn.execute("""
        SELECT COUNT(*) FROM users u JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE r.name = 'admin' AND u.suspended = 0
    """).fetchone()[0]


def initial_admin(conn):
    return conn.execute("""
        SELECT u.id, u.username FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE r.name = 'admin' AND u.password_hash IS NULL
        ORDER BY u.id LIMIT 1
    """).fetchone()


def error(message, status=400):
    return jsonify({"error": message}), status


def normalized_origin(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        if parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            return None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return parsed.scheme, parsed.hostname.lower(), port
    except ValueError:
        return None


@app.before_request
def access_boundary():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("Origin")
        if origin is not None and normalized_origin(origin) != normalized_origin(request.host_url):
            return error("Cross-origin request denied", 403)
        if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
            return error("Cross-origin request denied", 403)
    if request.endpoint in ("login", "health"):
        return None
    if request.endpoint == "static" and request.view_args.get("filename") == "styles.css":
        return None
    with db() as conn:
        user = user_by_id(conn, session.get("user_id"))
    if (user and not user["suspended"] and user["password_hash"]
            and session.get("session_version") == user["session_version"]):
        g.current_user = user
        return None
    session.clear()
    if request.path.startswith("/api/"):
        return error("Authentication required", 401)
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    with db() as conn:
        current = user_by_id(conn, session.get("user_id"))
        if (current and not current["suspended"] and current["password_hash"]
                and session.get("session_version") == current["session_version"]):
            return redirect(url_for("index"))
        setup = initial_admin(conn)
        message = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if setup:
                if username.casefold() != setup["username"].casefold():
                    message = "Complete administrator setup first."
                elif len(password) < 8:
                    message = "Use a password with at least 8 characters."
                elif password != request.form.get("password_confirmation"):
                    message = "Passwords do not match."
                else:
                    changed = conn.execute(
                        "UPDATE users SET password_hash = ?, session_version = session_version + 1 "
                        "WHERE id = ? AND password_hash IS NULL",
                        (generate_password_hash(password), setup["id"]),
                    ).rowcount
                    if changed:
                        user = user_by_id(conn, setup["id"])
                        session.clear()
                        session.update(user_id=user["id"], session_version=user["session_version"])
                        return redirect(url_for("index"))
                    message = "Administrator setup was already completed. Sign in."
            else:
                row = conn.execute(
                    "SELECT id FROM users WHERE username = ?", (username,)
                ).fetchone()
                user = user_by_id(conn, row["id"]) if row else None
                if not user or not user["password_hash"] or not check_password_hash(user["password_hash"], password):
                    message = "Invalid username or password."
                elif user["suspended"]:
                    message = "This account is suspended."
                else:
                    session.clear()
                    session.update(user_id=user["id"], session_version=user["session_version"])
                    return redirect(url_for("index"))
    response = app.make_response(render_template("login.html", setup=setup, error=message, version=VERSION))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
def index():
    response = app.make_response(render_template(
        "index.html", user=public_user(g.current_user), version=VERSION
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/me")
def me():
    return jsonify(public_user(g.current_user))


@app.get("/api/health")
def health():
    response = jsonify(ok=True, version=VERSION, uptime_seconds=int(time.monotonic() - STARTED))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/api/preferences", methods=["GET", "PATCH"])
def preferences():
    with db() as conn:
        if request.method == "PATCH":
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or not data or any(key not in ("theme", "page_size") for key in data):
                return error("Choose a theme or items per page.")
            if "theme" in data and data["theme"] not in ("light", "dark", "system"):
                return error("Choose light, dark, or system.")
            if "page_size" in data and data["page_size"] not in ("5", "10", "20", "50", "endless"):
                return error("Choose 5, 10, 20, 50, or endless scrolling.")
            conn.execute("""
                INSERT OR IGNORE INTO preferences(user_id) VALUES (?)
            """, (g.current_user["id"],))
            if "theme" in data:
                conn.execute("UPDATE preferences SET theme = ? WHERE user_id = ?",
                             (data["theme"], g.current_user["id"]))
            if "page_size" in data:
                conn.execute("UPDATE preferences SET page_size = ? WHERE user_id = ?",
                             (data["page_size"], g.current_user["id"]))
        row = conn.execute(
            "SELECT theme, page_size FROM preferences WHERE user_id = ?", (g.current_user["id"],)
        ).fetchone()
        return jsonify(theme=row["theme"] if row else "system", page_size=row["page_size"] if row else "10")


def require_admin():
    if g.current_user["role"] != "admin":
        return error("Administrator access required", 403)
    return None


@app.route("/api/users", methods=["GET", "POST"])
def users():
    denied = require_admin()
    if denied:
        return denied
    with db() as conn:
        if request.method == "GET":
            rows = conn.execute("SELECT id FROM users ORDER BY id").fetchall()
            return jsonify(users=[public_user(user_by_id(conn, row["id"])) for row in rows], roles=["admin", "normal"])
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error("A JSON object is required")
        username = str(data.get("username", "")).strip()
        name = str(data.get("name", "")).strip() or username
        password = data.get("password", "")
        role = data.get("role", "normal")
        if not username or len(username) > 80 or not isinstance(password, str) or len(password) < 8:
            return error("Enter a username and password with at least 8 characters.")
        if role not in ("admin", "normal"):
            return error("Unknown role")
        try:
            cursor = conn.execute(
                "INSERT INTO users(username, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (username, name, generate_password_hash(password), time.time()),
            )
            conn.execute("INSERT INTO user_roles(user_id, role_id) SELECT ?, id FROM roles WHERE name = ?",
                         (cursor.lastrowid, role))
        except sqlite3.IntegrityError:
            return error("Username already exists")
        return jsonify(public_user(user_by_id(conn, cursor.lastrowid))), 201


@app.route("/api/users/<int:user_id>", methods=["PATCH", "DELETE"])
def user_detail(user_id):
    denied = require_admin()
    if denied:
        return denied
    with db() as conn:
        # Reserve the writer before checking the administrator invariant so
        # concurrent account changes cannot both act on the same old count.
        conn.execute("BEGIN IMMEDIATE")
        target = user_by_id(conn, user_id)
        if not target:
            return error("Unknown user", 404)
        if request.method == "DELETE":
            if user_id == g.current_user["id"]:
                return error("You cannot remove your own account")
            if target["role"] == "admin" and not target["suspended"] and active_admin_count(conn) <= 1:
                return error("An active administrator is required")
            conn.execute("UPDATE documents SET owner_user_id=NULL WHERE owner_user_id=?", (user_id,))
            conn.execute("UPDATE import_jobs SET owner_user_id=NULL WHERE owner_user_id=?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return jsonify(message="User removed", id=user_id)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return error("User changes are required")
        if set(data) - {"name", "username", "password", "role", "suspended"}:
            return error("Unknown user field")
        role = data.get("role", target["role"])
        suspended = data.get("suspended", bool(target["suspended"]))
        if role not in ("admin", "normal") or not isinstance(suspended, bool):
            return error("Invalid role or account status")
        if target["role"] == "admin" and not target["suspended"] and (role != "admin" or suspended) and active_admin_count(conn) <= 1:
            return error("An active administrator is required")
        if user_id == g.current_user["id"] and suspended:
            return error("You cannot suspend your own account")
        username = data.get("username", target["username"])
        name = data.get("name", target["name"])
        if not isinstance(username, str) or not username.strip() or len(username) > 80 or not isinstance(name, str) or not name.strip():
            return error("Enter a name and username")
        password = data.get("password")
        if password is not None and (not isinstance(password, str) or len(password) < 8):
            return error("Use a password with at least 8 characters")
        try:
            conn.execute("""
                UPDATE users SET username = ?, name = ?, suspended = ?,
                password_hash = COALESCE(?, password_hash),
                session_version = session_version + ? WHERE id = ?
            """, (username.strip(), name.strip(), int(suspended),
                  generate_password_hash(password) if password is not None else None,
                  int(password is not None or suspended != bool(target["suspended"])), user_id))
            conn.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
            conn.execute("INSERT INTO user_roles(user_id, role_id) SELECT ?, id FROM roles WHERE name = ?",
                         (user_id, role))
        except sqlite3.IntegrityError:
            return error("Username already exists")
        updated = user_by_id(conn, user_id)
        if user_id == g.current_user["id"]:
            session["session_version"] = updated["session_version"]
        return jsonify(public_user(updated))


from document_library import DocumentLibrary

init_db()
document_library = DocumentLibrary(app, db)

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")))
