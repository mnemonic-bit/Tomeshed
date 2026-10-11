# Tomeshed

[![Validation](https://github.com/mnemonic-bit/Tomeshed/actions/workflows/validation.yml/badge.svg?branch=main)](https://github.com/mnemonic-bit/Tomeshed/actions/workflows/validation.yml)
[![CodeQL](https://github.com/mnemonic-bit/Tomeshed/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/mnemonic-bit/Tomeshed/actions/workflows/codeql.yml)
[![Main publication](https://github.com/mnemonic-bit/Tomeshed/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/mnemonic-bit/Tomeshed/actions/workflows/main.yml)
[![Latest release](https://img.shields.io/github/v/release/mnemonic-bit/Tomeshed)](https://github.com/mnemonic-bit/Tomeshed/releases)
[![GHCR image](https://img.shields.io/github/v/release/mnemonic-bit/Tomeshed?label=GHCR)](https://github.com/mnemonic-bit/Tomeshed/pkgs/container/tomeshed)

[GitHub Releases](https://github.com/mnemonic-bit/Tomeshed/releases) · [GHCR package](https://github.com/mnemonic-bit/Tomeshed/pkgs/container/tomeshed)

Tomeshed is a local ebook and PDF library. Signed-in users can upload PDF, EPUB, and DoclingDocument JSON files, organize documents with shared tags and favorites, search extracted text, and read preserved sources. The reader saves each user's position, last-read time, and completion state. Docling extracts structured content for indexing. PDF conversion uses Docling's native text pipeline, which extracts embedded text but does not perform OCR.

## Run locally

Create a Python virtual environment, install `requirements.txt`, and start `tomeshed.py`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tomeshed.py
```

Open `http://127.0.0.1:5000`. On the first visit, set the password for the `admin` account. The SQLite database is stored at `data/tomeshed.db` by default. Set `TOMESHED_DB` to another path to move it. Keep the database and its backups private because it contains account records and the session-signing secret.

The library stores source files, structured JSON artifacts, and thumbnails in `data/library/` by default. Set `TOMESHED_LIBRARY_DIR` to move that storage. `TOMESHED_MAX_UPLOAD_BYTES` defaults to 104857600, `TOMESHED_CONVERSION_TIMEOUT` to 180 seconds, `TOMESHED_CONVERSION_WORKERS` to 2, and `TOMESHED_CATALOG_PAGE_SIZE` to 50. Back up the database and library directory together.

## Run in a container

Run `docker compose up --build` to serve Tomeshed on port 5000. Set `TOMESHED_PORT` to change the host port. The `tomeshed-data` volume stores SQLite; `tomeshed-documents` stores managed source and generated files across container restarts.

For a manual Podman deployment, see [PODMAN.md](PODMAN.md).

For a published image, select an immutable `v<VERSION>` tag, a full commit SHA tag, or a manifest digest from [GHCR](https://github.com/mnemonic-bit/Tomeshed/pkgs/container/tomeshed). Pull and replace with `scripts/podman_replace.sh IMAGE_REFERENCE EXPECTED_VERSION`; see [PODMAN.md](PODMAN.md) for version selection, health verification, inbox mounts, and rollback. Use a digest or full SHA tag when a release tag is unavailable.

## Verify

Install `requirements-dev.txt` and Playwright Chromium, then run the complete validation gate with one command:

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
./tests/run-all.sh
```

The same `tests/run-all.sh` command runs every `tests/test_*.py` module, every `tests/browser_check*.py` script, verifies the locked container dependencies for amd64 and arm64, and builds and tests the shipping image with isolated test volumes. Browser screenshots and reports stay under `/tmp/`.

Inspect a published manifest with `docker buildx imagetools inspect ghcr.io/mnemonic-bit/tomeshed:v<VERSION>`. Use `gh attestation verify oci://ghcr.io/mnemonic-bit/tomeshed@sha256:<DIGEST> --repo mnemonic-bit/Tomeshed` for the manifest and each platform digest printed by the `Main` workflow. Each platform also has an SPDX SBOM attestation. The version shown in the app comes from the root `VERSION` file and the release tag.

## Card previews

Rest the pointer on a document cover, focus it with the keyboard, or press and hold on touch to inspect nearby PDF, EPUB, or Docling content. The preview opens at your saved reading position. Its Previous and Next controls do not change reading progress. Select a cover with one click or tap, then choose **Open**; double-click or press Enter on the cover to open the full reader at the saved position.

Preview rendering is bounded by `TOMESHED_PREVIEW_CACHE_LOCATIONS` (default 32 cached locations), `TOMESHED_PREVIEW_PDF_MAX_WIDTH` (default 720 pixels), `TOMESHED_PREVIEW_PDF_MAX_HEIGHT` (default 960 pixels), `TOMESHED_PREVIEW_TEXT_CHARS` (default 1400 characters per excerpt), and `TOMESHED_PREVIEW_IMAGE_LIMIT` (default 2 EPUB images per excerpt).

## Find and organize

Use **Filters** beside the library search field to narrow by source type, author, tags, favorite status, and your reading state. Selected filters combine with the search query. The tag control can require all selected tags or any selected tag. **Clear filters** resets the filter controls while preserving the query and sort. Use **Sort** beside the search field to choose the result order.

Each document tile shows its cover, title, and favorite star. The reader's document panel lets signed-in users correct the displayed title and author and add or remove tags. These edits belong to the catalog record, survive reindexing, and leave the preserved source file unchanged. Reading state and last-read time belong to each user. A document remains **new** until that user successfully opens its reader.

## File workflows

Choose **Add document** or drop PDF, EPUB, and DoclingDocument JSON files anywhere on the library page. The import drawer registers each file before transfer, shows bytes received and processing state, and offers cancellation or retry for failed browser imports. A failed browser import needs the local file selected again. Choose **Import URL** in the drawer to fetch a direct HTTP or HTTPS PDF or EPUB. Tomeshed checks every redirect and resolved address before connecting; private destinations require an operator CIDR allowlist.

A document's reader panel offers the preserved original download, Docling JSON when extraction produced one, source filename rename, and confirmed removal. The import filename remains searchable after a stored filename rename. Administrators can preview and confirm **Clear library**; an old preview is rejected if the document or managed-file set changes. Failed artifact cleanup remains recorded for an administrator retry through `POST /api/library/cleanup/retry`.

Set `TOMESHED_INGEST_DIR` to an existing read-only inbox directory to watch its top level. The producer should write under a temporary suffix such as `.part`, close the file, and rename it to `.pdf`, `.epub`, or `.json`. A direct copy to a final name is accepted only after three identical file signatures span `TOMESHED_INGEST_SETTLE_SECONDS` (default 60 seconds). Scans run every `TOMESHED_INGEST_SCAN_SECONDS` (default 10 seconds). Receipts in SQLite stop an unchanged source from reimporting after restart or catalog removal. Tomeshed never changes the inbox source.

URL imports use `TOMESHED_URL_CONNECT_TIMEOUT_SECONDS` (default 10), `TOMESHED_URL_TOTAL_TIMEOUT_SECONDS` (default 300), and `TOMESHED_URL_ALLOWED_CIDRS` (comma-separated, empty by default). All time values must be finite and positive; inbox scan and settle values must be at least one second. `TOMESHED_MAX_UPLOAD_BYTES` limits both browser and URL transfers.

The root Compose service runs as UID/GID 10001, persists SQLite in `tomeshed-data` and managed documents in `tomeshed-documents`, and checks `/api/health`. To use an inbox with Compose, set `TOMESHED_INGEST_HOST_DIR` to the host directory and `TOMESHED_INGEST_DIR=/ingest`. Compose mounts the host inbox at `/ingest` read-only. With `TOMESHED_INGEST_DIR` unset, inbox scanning stays disabled.
