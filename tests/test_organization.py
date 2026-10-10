"""Catalog organization, search, and per-user state checks."""

import importlib
import json
import time

from test_documents import module, pdf_bytes, signed_in
from test_reader import add_document


def card(client, document_id):
    return client.get(f"/api/documents/{document_id}").json


def test_tags_favorites_metadata_and_retry_survive_restart(module, monkeypatch):
    client = signed_in(module)
    first = add_document(module, pdf_bytes(2), "pdf", "Source title")
    second = add_document(module, pdf_bytes(1), "pdf", "Other title")
    source = module.document_library.root / f"sources/{first}.source"
    original = source.read_bytes()
    for document_id, name in ((first, "  History   "), (second, "history")):
        response = client.post(f"/api/documents/{document_id}/tags", json={"tag": name})
        assert response.status_code == 200, response.json
    assert card(client, first)["tags"] == card(client, second)["tags"] == ["History"]
    assert client.get("/api/tags").json["tags"] == ["History"]
    for invalid in ("", " " * 4, "bad,name", "A" * 65, "bad\nname", None):
        assert client.post(f"/api/documents/{first}/tags", json={"tag": invalid}).status_code == 400
    assert client.patch(f"/api/documents/{first}/favorite", json={"favorite": "yes"}).status_code == 400
    assert client.patch(f"/api/documents/{first}/favorite", json={"favorite": True}).json["document"]["favorite"] is True
    assert client.patch(f"/api/documents/{first}/metadata", json={"title": "Corrected History", "author": "Revised Author"}).status_code == 200
    assert client.patch(f"/api/documents/{first}/metadata", json={"title": "", "author": "Wrong"}).status_code == 400
    assert card(client, first)["title"] == "Corrected History"
    assert card(client, first)["author"] == "Revised Author"
    assert card(client, first)["original_filename"] == "fixture.pdf"
    assert source.read_bytes() == original
    assert client.get("/api/documents?q=corrected").json["total"] == 1
    assert client.get("/api/documents?q=revised").json["total"] == 1
    assert client.get("/api/documents?q=fixture.pdf").json["total"] == 2
    assert client.delete(f"/api/documents/{first}/tags", json={"tag": "HISTORY"}).status_code == 200
    assert client.get("/api/tags").json["tags"] == ["History"]
    assert client.delete(f"/api/documents/{second}/tags", json={"tag": "history"}).status_code == 200
    assert client.get("/api/tags").json["tags"] == []
    assert client.post(f"/api/documents/{first}/tags", json={"tag": "History"}).status_code == 200
    with module.db() as conn:
        conn.execute("UPDATE documents SET state='ready_with_warning',error='Indexing warning: controlled',text_content='' WHERE id=?", (first,))
    monkeypatch.setattr(module.document_library, "_run_conversion", lambda path, filename, staging: {
        "state": "ready", "source_type": "pdf", "title": "Reindexed title", "author": "Source author", "byte_size": len(original),
        "text": "Extracted archive", "page_count": 2, "count_kind": "exact"})
    job = client.post(f"/api/documents/{first}/retry")
    assert job.status_code == 202
    from test_documents import wait_job
    wait_job(client, job.json["id"], "ready")
    assert (card(client, first)["title"], card(client, first)["author"], card(client, first)["favorite"], card(client, first)["tags"]) == (
        "Corrected History", "Revised Author", True, ["History"])
    assert client.get("/api/documents?q=EXTRACTED ARCHIVE").json["total"] == 1
    assert source.read_bytes() == original
    reloaded = importlib.reload(module)
    again = reloaded.app.test_client()
    assert again.post("/login", data={"username": "admin", "password": "secret-password"}).status_code == 302
    assert (card(again, first)["title"], card(again, first)["favorite"], card(again, first)["tags"]) == (
        "Corrected History", True, ["History"])


def test_reading_state_is_per_user_and_preview_actions_are_read_only(module):
    first = signed_in(module)
    first.post("/api/users", json={"username": "other", "password": "other-password", "role": "normal"})
    second = module.app.test_client()
    assert second.post("/login", data={"username": "other", "password": "other-password"}).status_code == 302
    document_id = add_document(module, pdf_bytes(2), "pdf")
    base = f"/api/documents/{document_id}"
    assert card(first, document_id)["reading_state"] == "unread"
    for path in (base, f"{base}/source?download=1", f"{base}/reader", f"{base}/preview"):
        assert first.get(path).status_code in (200, 400)
    assert first.get("/api/documents?q=Reader").status_code == 200
    assert card(first, document_id)["reading_state"] == "unread"
    assert first.get(f"{base}/progress").json["position"] is None
    opened = first.post(f"{base}/reader-open")
    assert opened.status_code == 200
    assert opened.json["document"]["reading_state"] == "in_progress"
    assert opened.json["document"]["last_read_at"]
    assert card(second, document_id)["reading_state"] == "unread"
    assert card(second, document_id)["last_read_at"] is None
    first.post(f"{base}/finish")
    assert card(first, document_id)["reading_state"] == "finished"
    first.post(f"{base}/start-over")
    assert card(first, document_id)["reading_state"] == "in_progress"
    assert first.get(f"{base}/progress").json["position"] is None
    with module.db() as conn:
        before = conn.execute("SELECT opened_at FROM reader_opens WHERE user_id=1 AND document_id=?", (document_id,)).fetchone()[0]
    (module.document_library.root / f"sources/{document_id}.source").unlink()
    assert first.post(f"{base}/reader-open").status_code == 404
    with module.db() as conn:
        after = conn.execute("SELECT opened_at FROM reader_opens WHERE user_id=1 AND document_id=?", (document_id,)).fetchone()[0]
    assert after == before
    anon = module.app.test_client()
    for method, path, payload in ((anon.get, "/api/documents?q=Reader", None), (anon.get, "/api/tags", None),
                                  (anon.post, f"{base}/reader-open", None), (anon.patch, f"{base}/favorite", {"favorite": True}),
                                  (anon.post, f"{base}/tags", {"tag": "Test"}), (anon.patch, f"{base}/metadata", {"title": "x", "author": "y"})):
        response = method(path) if payload is None else method(path, json=payload)
        assert response.status_code == 401


def test_combined_filters_pagination_sort_and_access_boundary(module, monkeypatch):
    client = signed_in(module)
    ids = [add_document(module, pdf_bytes(1), "pdf", f"Volume {index}") for index in range(6)]
    with module.db() as conn:
        for index, document_id in enumerate(ids):
            conn.execute("UPDATE documents SET created_at=?,author=?,text_content=?,source_type=? WHERE id=?",
                         (100 + index, "Ada" if index % 2 == 0 else "Bob", "special index text" if index in (2, 4) else "", "epub" if index == 5 else "pdf", document_id))
        conn.execute("UPDATE documents SET state='ready_with_warning',error='Indexing warning',text_content='' WHERE id=?", (ids[0],))
    for index in (0, 2, 4):
        assert client.post(f"/api/documents/{ids[index]}/tags", json={"tag": "History"}).status_code == 200
    for index in (2, 4):
        assert client.post(f"/api/documents/{ids[index]}/tags", json={"tag": "Science"}).status_code == 200
    for index in (0, 4):
        assert client.patch(f"/api/documents/{ids[index]}/favorite", json={"favorite": True}).status_code == 200
    assert client.post(f"/api/documents/{ids[2]}/reader-open").status_code == 200
    filtered = client.get("/api/documents?q=special&type=pdf&author=ada&tag=History&tag=Science&tag_mode=ALL&reading_state=unread")
    assert filtered.json["total"] == 1 and filtered.json["documents"][0]["id"] == ids[4]
    assert client.get("/api/documents?tag=History&tag=Science&tag_mode=ANY").json["total"] == 3
    assert client.get("/api/documents?q=VOLUME 0").json["documents"][0]["id"] == ids[0]
    assert client.get("/api/documents?q=SPECIAL INDEX TEXT").json["total"] == 2
    assert client.get("/api/documents?favorite=true").json["total"] == 2
    result = client.get("/api/documents?sort=favorite&limit=99").json
    assert result["total"] == 6 and len(result["documents"]) == 2 and result["limit"] == 2
    assert [item["id"] for item in result["documents"]] == [ids[4], ids[0]]
    assert client.get("/api/documents?sort=favorite&offset=2").json["documents"][0]["id"] == ids[5]
    original_access = module.document_library.can_access_document
    monkeypatch.setattr(module.document_library, "can_access_document", lambda row, user_id: row["id"] != ids[4])
    visible = client.get("/api/documents?tag=Science").json
    assert visible["total"] == 1 and visible["documents"][0]["id"] == ids[2]
    assert client.get("/api/documents?q=special").json["total"] == 1
    assert client.get(f"/api/documents/{ids[4]}").status_code == 404
    assert client.patch(f"/api/documents/{ids[4]}/favorite", json={"favorite": False}).status_code == 404
    monkeypatch.setattr(module.document_library, "can_access_document", original_access)
