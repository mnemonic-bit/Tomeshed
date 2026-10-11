"""Catalog sort fields, directions, and mixed pagination."""

from test_bookshelves import create
from test_documents import module, pdf_bytes, signed_in
from test_reader import add_document


def test_sort_fields_directions_and_mixed_page_boundaries(module):
    client = signed_in(module)
    first = add_document(module, pdf_bytes(1), "pdf", "alpha")
    second = add_document(module, pdf_bytes(1), "pdf", "Bravo")
    third = add_document(module, pdf_bytes(1), "pdf", "ALPHA")
    shelf = create(client, "beta shelf")
    with module.db() as conn:
        for document_id, author, source_type, created_at in (
            (first, "zoe", "pdf", 100),
            (second, "Ada", "epub", 200),
            (third, "", "docling", 100),
        ):
            conn.execute("UPDATE documents SET author=?,source_type=?,created_at=? WHERE id=?",
                         (author, source_type, created_at, document_id))
        conn.execute("UPDATE bookshelves SET created_at=150 WHERE id=?", (shelf["id"],))
    assert client.patch(f"/api/documents/{first}/favorite", json={"favorite": True}).status_code == 200

    def order(field=None, direction=None):
        params = []
        if field:
            params.append(f"sort={field}")
        if direction:
            params.append(f"direction={direction}")
        query = "&".join(params)
        result = client.get(f"/api/documents?{query}")
        assert result.status_code == 200, result.json
        first_page = result.json
        later = client.get(f"/api/documents?{query}&offset=2").json
        assert first_page["total"] == 4
        return [item["id"] for item in first_page["items"] + later["items"]]

    tie = sorted((first, third))
    assert order() == [second, shelf["id"], *tie]
    assert order("date_added", "asc") == [*tie, shelf["id"], second]
    assert order("title", "asc") == [*tie, shelf["id"], second]
    assert order("title", "desc") == [second, shelf["id"], *tie]
    assert order("author", "asc") == [second, first, *sorted((third, shelf["id"]))]
    assert order("author", "desc")[:2] == [first, second]
    assert order("author", "desc")[-2:] == order("author", "asc")[-2:]
    assert order("type", "asc") == [shelf["id"], third, second, first]
    assert order("type", "desc") == [first, second, third, shelf["id"]]
    assert order("favorite", "desc")[0] == first
    assert order("favorite", "asc")[-1] == first
    assert order("newest") == order()
    assert order("favorite") == order("favorite", "desc")
    for query in ("sort=invalid", "direction=sideways", "sort=title&direction=invalid"):
        assert client.get(f"/api/documents?{query}").status_code == 400


def test_shelves_with_same_date_use_name_then_stable_id(module):
    client = signed_in(module)
    zebra = create(client, "Zebra")
    alpha = create(client, "alpha")
    duplicate = create(client, "ALPHA")
    with module.db() as conn:
        conn.execute("UPDATE bookshelves SET created_at=100")
    tied = sorted((alpha["id"], duplicate["id"]))
    ascending = client.get("/api/documents?sort=date_added&direction=asc&limit=2").json
    tail = client.get("/api/documents?sort=date_added&direction=asc&offset=2").json
    assert [item["id"] for item in ascending["items"] + tail["items"]] == [*tied, zebra["id"]]
    descending = client.get("/api/documents?sort=date_added&direction=desc&limit=2").json
    tail = client.get("/api/documents?sort=date_added&direction=desc&offset=2").json
    assert [item["id"] for item in descending["items"] + tail["items"]] == [zebra["id"], *tied]
