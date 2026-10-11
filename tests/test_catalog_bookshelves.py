"""Unified catalog pages include only accessible bookshelves and document data."""

from test_bookshelves import create, user
from test_documents import module, pdf_bytes, signed_in
from test_reader import add_document


def test_catalog_combines_authorized_bookshelves_before_pagination(module):
    admin = signed_in(module)
    recipient, _ = user(module, admin, "shelfreader")
    outsider, _ = user(module, admin, "shelfoutsider")
    visible = add_document(module, pdf_bytes(1), "pdf", "Visible document")
    private = add_document(module, pdf_bytes(1), "pdf", "Secret document")
    assert admin.patch(f"/api/documents/{private}/visibility", json={"visibility": "private"}).status_code == 200
    shared = create(admin, "Reading circle", [visible, private])
    owned = create(recipient, "Personal shelf")
    assert admin.post(f"/api/bookshelves/{shared['id']}/shares", json={"username": "shelfreader"}).status_code == 200
    with module.db() as conn:
        conn.execute("UPDATE documents SET created_at=100 WHERE id=?", (visible,))
        conn.execute("UPDATE bookshelves SET created_at=200 WHERE id=?", (shared["id"],))
        conn.execute("UPDATE bookshelves SET created_at=300 WHERE id=?", (owned["id"],))

    page = recipient.get("/api/documents?limit=2").json
    assert page["total"] == 3
    assert len(page["items"]) == 2
    assert [item["id"] for item in page["items"]] == [owned["id"], shared["id"]]
    second = recipient.get("/api/documents?limit=2&offset=2").json
    assert len(second["items"]) == 1
    assert {item["id"] for item in page["items"] + second["items"]} == {visible, shared["id"], owned["id"]}
    assert sum(item["kind"] == "bookshelf" for item in page["items"] + second["items"]) == 2
    assert private not in str(page["items"] + second["items"])
    shared_result = next(item for item in page["items"] + second["items"] if item["id"] == shared["id"])
    assert shared_result["owned"] is False and shared_result["count"] == 1
    assert private not in str(shared_result)

    shelf_search = recipient.get("/api/documents?q=reading%20circle").json
    assert [item["id"] for item in shelf_search["items"]] == [shared["id"]]
    assert recipient.get("/api/documents?q=reading%20circle&scope=documents").json["total"] == 0
    assert recipient.get("/api/documents?q=reading%20circle&scope=bookshelves").json["total"] == 1
    assert recipient.get("/api/documents?scope=bookshelves").json["total"] == 2
    assert recipient.get("/api/documents?scope=documents").json["total"] == 1
    assert recipient.get("/api/documents?q=Secret").json["total"] == 0
    assert recipient.get("/api/documents?scope=invalid").status_code == 400
    assert outsider.get("/api/documents?q=reading%20circle&scope=bookshelves").json["total"] == 0
    assert admin.patch(f"/api/documents/{visible}/favorite", json={"favorite": True}).status_code == 200
    favorite_page = recipient.get("/api/documents?sort=favorite&limit=2").json
    assert favorite_page["items"][0]["id"] == visible
    assert favorite_page["total"] == 3
