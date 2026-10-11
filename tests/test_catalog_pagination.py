"""Per-user page size and authorized mixed-result page boundaries."""

from test_bookshelves import create, user
from test_documents import module, pdf_bytes, signed_in
from test_reader import add_document


def test_page_size_preference_is_per_user_validated_and_survives_migration(module):
    admin = signed_in(module)
    reader, _ = user(module, admin, "page-reader")
    assert admin.get("/api/preferences").json == {"theme": "system", "page_size": "10"}
    for choice in ("5", "10", "20", "50", "endless"):
        assert admin.patch("/api/preferences", json={"page_size": choice}).json["page_size"] == choice
        assert admin.get("/api/preferences").json["page_size"] == choice
    assert reader.get("/api/preferences").json["page_size"] == "10"
    assert admin.patch("/api/preferences", json={"theme": "dark"}).json == {"theme": "dark", "page_size": "endless"}
    for invalid in (None, 5, "0", "25", "all", "500"):
        assert admin.patch("/api/preferences", json={"page_size": invalid}).status_code == 400
    assert admin.get("/api/preferences").json["page_size"] == "endless"
    module.init_db()
    assert admin.get("/api/preferences").json == {"theme": "dark", "page_size": "endless"}
    assert reader.patch("/api/preferences", json={"page_size": "20"}).json["page_size"] == "20"
    assert admin.get("/api/preferences").json["page_size"] == "endless"


def test_catalog_supports_fifty_items_and_counts_authorized_shelves(module):
    client = signed_in(module)
    module.app.config["CATALOG_PAGE_SIZE"] = 50
    document_ids = [add_document(module, pdf_bytes(1), "pdf", f"Page {index:02}") for index in range(11)]
    shelf_ids = [create(client, f"Shelf {index}")["id"] for index in range(2)]
    first = client.get("/api/documents?limit=5&offset=0").json
    second = client.get("/api/documents?limit=5&offset=5").json
    third = client.get("/api/documents?limit=5&offset=10").json
    assert all(page["total"] == 13 for page in (first, second, third))
    assert [len(page["items"]) for page in (first, second, third)] == [5, 5, 3]
    assert {item["id"] for page in (first, second, third) for item in page["items"]} == set(document_ids + shelf_ids)
    assert client.get("/api/documents?limit=50").json["limit"] == 50
    assert client.get("/api/documents?scope=bookshelves&limit=5").json["total"] == 2
    assert client.get("/api/documents?q=Page%200&limit=5").json["total"] == 10
    assert client.get("/api/documents?offset=-1").status_code == 400
