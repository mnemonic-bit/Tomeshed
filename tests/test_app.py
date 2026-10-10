import importlib
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from werkzeug.security import check_password_hash


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMESHED_DB", str(tmp_path / "library.db"))
    import tomeshed
    module = importlib.reload(tomeshed)
    module.app.config.update(TESTING=True)
    return module


def setup_admin(client, password="secret-password"):
    return client.post("/login", data={
        "username": "admin", "password": password,
        "password_confirmation": password,
    })


def test_initial_setup_is_one_time_and_hashes_password(app_module):
    client = app_module.app.test_client()
    assert "Set administrator password" in client.get("/login").text
    with app_module.db() as conn:
        admin = conn.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
        assert admin["password_hash"] is None
        assert [r["name"] for r in conn.execute("SELECT name FROM roles ORDER BY name")] == ["admin", "normal"]
    assert "Passwords do not match" in client.post("/login", data={
        "username": "admin", "password": "secret-password", "password_confirmation": "different"
    }).text
    assert setup_admin(client).status_code == 302
    with app_module.db() as conn:
        first_hash = conn.execute("SELECT password_hash FROM users WHERE username = 'admin'").fetchone()[0]
    assert check_password_hash(first_hash, "secret-password")
    another = app_module.app.test_client()
    assert "Invalid username or password" in another.post("/login", data={
        "username": "admin", "password": "new-password", "password_confirmation": "new-password"
    }).text
    with app_module.db() as conn:
        assert conn.execute("SELECT password_hash FROM users WHERE username = 'admin'").fetchone()[0] == first_hash


def test_private_boundary_logout_and_public_health(app_module):
    client = app_module.app.test_client()
    assert client.get("/").status_code == 302
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/preferences").status_code == 401
    assert client.get("/api/users").status_code == 401
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/app.js").status_code == 302
    assert client.get("/static/book.svg").status_code == 302
    health = client.get("/api/health").json
    assert health["version"] == app_module.VERSION
    assert isinstance(health["uptime_seconds"], int)
    assert not {"users", "library", "preferences", "secret_key"}.intersection(health)
    setup_admin(client)
    assert client.get("/").status_code == 200
    assert client.post("/logout").status_code == 302
    assert client.get("/").status_code == 302
    assert client.get("/api/me").status_code == 401


def test_accounts_permissions_last_admin_and_session_revocation(app_module):
    admin = app_module.app.test_client()
    setup_admin(admin)
    created = admin.post("/api/users", json={"username": "reader", "name": "Reader", "password": "reader-pass", "role": "normal"})
    assert created.status_code == 201
    user_id = created.json["id"]
    reader = app_module.app.test_client()
    assert reader.post("/login", data={"username": "reader", "password": "reader-pass"}).status_code == 302
    assert "settings-users" not in reader.get("/").text
    assert reader.get("/api/users").status_code == 403
    assert reader.post("/api/users", json={"username": "x"}).status_code == 403
    assert reader.patch(f"/api/users/{user_id}", json={"name": "X"}).status_code == 403
    assert reader.delete(f"/api/users/{user_id}").status_code == 403
    with app_module.db() as conn:
        admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    assert admin.patch(f"/api/users/{admin_id}", json={"suspended": True}).status_code == 400
    assert admin.patch(f"/api/users/{admin_id}", json={"role": "normal"}).status_code == 400
    assert admin.delete(f"/api/users/{admin_id}").status_code == 400
    assert admin.patch(f"/api/users/{user_id}", json={"suspended": True}).status_code == 200
    assert reader.get("/api/me").status_code == 401
    assert admin.patch(f"/api/users/{user_id}", json={"suspended": False}).status_code == 200
    assert admin.patch(f"/api/users/{user_id}", json={"password": "new-reader-pass"}).status_code == 200
    assert reader.post("/login", data={"username": "reader", "password": "reader-pass"}).status_code == 200
    assert reader.post("/login", data={"username": "reader", "password": "new-reader-pass"}).status_code == 302
    assert admin.delete(f"/api/users/{user_id}").status_code == 200
    assert reader.get("/api/me").status_code == 401


def test_concurrent_admin_suspensions_keep_one_active_admin(app_module, monkeypatch):
    first = app_module.app.test_client()
    setup_admin(first)
    created = first.post("/api/users", json={
        "username": "second-admin", "name": "Second Admin",
        "password": "second-password", "role": "admin",
    })
    assert created.status_code == 201
    second = app_module.app.test_client()
    assert second.post("/login", data={
        "username": "second-admin", "password": "second-password",
    }).status_code == 302
    with app_module.db() as conn:
        first_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    second_id = created.json["id"]

    # If both reads can run before either write, both sessions can otherwise
    # suspend the other administrator and leave no active administrator.
    count_gate = threading.Barrier(2)
    request_gate = threading.Barrier(2)
    original_count = app_module.active_admin_count

    def delayed_count(conn):
        count = original_count(conn)
        if count == 2:
            try:
                count_gate.wait(timeout=0.3)
            except threading.BrokenBarrierError:
                pass
        return count

    monkeypatch.setattr(app_module, "active_admin_count", delayed_count)

    def suspend(client, target_id):
        request_gate.wait(timeout=2)
        return client.patch(f"/api/users/{target_id}", json={"suspended": True}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_result = pool.submit(suspend, first, second_id)
        second_result = pool.submit(suspend, second, first_id)
        statuses = {first_result.result(), second_result.result()}

    assert 200 in statuses
    assert statuses.issubset({200, 400, 401})
    with app_module.db() as conn:
        assert original_count(conn) == 1


def test_preferences_secret_and_session_survive_reinitialization(app_module):
    client = app_module.app.test_client()
    setup_admin(client)
    assert client.patch("/api/preferences", json={"theme": "dark"}).json == {"theme": "dark"}
    with app_module.db() as conn:
        before = conn.execute("SELECT value FROM app_config WHERE key = 'secret_key'").fetchone()[0]
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    app_module.app.secret_key = "temporary"
    app_module.init_db()
    assert app_module.app.secret_key == before
    assert client.get("/api/me").status_code == 200
    assert client.get("/api/preferences").json == {"theme": "dark"}
    with app_module.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == user_count
    client.post("/logout")
    client.post("/login", data={"username": "admin", "password": "secret-password"})
    assert client.get("/api/preferences").json == {"theme": "dark"}


def test_cross_site_mutations_and_cookie_attributes(app_module):
    client = app_module.app.test_client()
    blocked = client.post("/login", data={}, headers={"Origin": "https://elsewhere.example"})
    assert blocked.status_code == 403
    assert client.post("/login", data={}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/login", data={}, headers={"Origin": "http://localhost"}).status_code == 200
    response = setup_admin(client)
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert client.patch("/api/preferences", json={"theme": "dark"}, headers={"Origin": "https://elsewhere.example"}).status_code == 403
    assert client.patch("/api/preferences", json={"theme": "dark"}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.patch("/api/preferences", json={"theme": "light"}, headers={"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin"}).status_code == 200
