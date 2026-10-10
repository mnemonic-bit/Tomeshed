# Ebook and PDF library

This repository contains Tomeshed, an ebook and PDF library application. The numbered implementation plan is in `FEATURES/README.md`.

## Prototype boundary

`VDL/` is a separate, gitignored video library application. Use it as the read-only technical blueprint for the first version of this app. Inspect its code and documentation when planning or implementing a comparable feature. Make every new code, test, configuration, and documentation change in this repository outside `VDL/`. Never modify files in `VDL/` or run commands there that create or update files.

For structural codebase exploration, use the installed `codebase-memory` skill. Check the current source when a VDL document and implementation disagree.

For any agent-authored output, including session messages, specifications, reports, and state files, follow `AGENT-LANG.md`.

## Feature and bug documentation

- Feature requirements belong in numbered `FEATURES/feature-NNNN-*.md` files. Use `FEATURES/README.md` as the feature index and `FEATURES/evidence/feature-NNNN.md` for implementation evidence.
- Bug reports and fixes belong in numbered `BUGS/bug-NNNN-*.md` files. Before diagnosing a defect, check `BUGS/BUG-INDEX.md` for an existing report. If none exists, add the next numbered report and link it from the index. Record the observed behavior, reproduction, expected behavior, diagnosis, resolution, verification, and current status; update the report and index when the status changes.

## Architecture to adapt from VDL

- Backend: `VDL/vdl.py` is a Flask app containing HTTP routes, authentication, API behavior, SQLite access and schema migration, and library file handling. Use those flows as examples for the new app's boundaries and data lifecycle.
- Browser UI: `VDL/templates/index.html` renders the page shell; `VDL/static/app.js` and `VDL/static/styles.css` implement the client without a build step. Follow this simple web-app shape as the initial reference.
- Persistence and files: VDL keeps library records and preferences in SQLite, stores media on disk, and checks access before serving files. Adapt that separation to ebook/PDF metadata, document storage, and authorized reading or download.
- Live updates: `VDL/vdl.py` exposes Server-Sent Events and the browser refreshes API state when events arrive. Use this pattern if document import or processing needs live progress.
- Delivery and verification: `VDL/Dockerfile`, `VDL/compose.yaml`, and `VDL/tests/` show its container setup and testing approach. Build this app's own deployment and tests in the root repository.

Translate VDL's video-specific behavior into document-library requirements as they are defined. Treat downloading videos, playback, transcoding, and the browser extension as prototype details, not assumed features of this app.

Use Docling for document conversion and extraction in Tomeshed. Preserve source files for faithful reading; Docling's structured output is not a PDF/EPUB replacement.

## Runtime and deployment

- PDFium concurrency: `pypdfium2` cannot run concurrently across Flask request threads. Hold `reader_service.PDFIUM_LOCK` for every PDFium operation in the web process, from opening a document through closing its PDFium resources. The reader and preview paths share this lock.
- Podman deployment: follow `PODMAN.md` when building, starting, or replacing the container. Preserve the `tomeshed-data` and `tomeshed-documents` volumes, then check that `/api/health` reports the version in `VERSION`.

## Version changes

Before completing each distinct requested code change, increment the root `VERSION` file. An uncommitted version change from earlier work does not count for a new code change; increment `VERSION` again.

Use semantic versioning for the change's impact:

- Breaking or incompatible API changes increment `MAJOR` and reset `MINOR` and `PATCH`, including when `MAJOR` is zero.
- Features increment `MINOR` and reset `PATCH`.
- Bug fixes and other code changes increment `PATCH`.

For a change that includes code and documentation, apply one bump at the highest code impact: `MAJOR`, then `MINOR`, then `PATCH`. Documentation-only changes, including specifications and agent-instruction updates, leave `VERSION` unchanged.

## Implementing the feature plan

When asked to implement the numbered feature plan without further intervention, act as the coordinator and follow `IMPLEMENTATION-WORKFLOW.md`. Spawn the project `feature_builder` and `feature_reviewer` agents for each feature as that workflow directs. Record progress in `IMPLEMENTATION-STATE.md`.
