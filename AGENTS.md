# Ebook and PDF library

This repository is for Tomeshed, a new ebook and PDF library application. The first app version has not been implemented yet. The numbered implementation plan is in `FEATURES/README.md`.

## Prototype boundary

`VDL/` is a separate, gitignored video library application. Use it as the read-only technical blueprint for the first version of this app. Inspect its code and documentation when planning or implementing a comparable feature. Make every new code, test, configuration, and documentation change in this repository outside `VDL/`. Never modify files in `VDL/` or run commands there that create or update files.

For structural codebase exploration, use the installed `codebase-memory` skill. Check the current source when a VDL document and implementation disagree.

For any agent-authored output, including session messages, specifications, reports, and state files, follow `AGENT-LANG.md`.

## Architecture to adapt from VDL

- Backend: `VDL/vdl.py` is a Flask app containing HTTP routes, authentication, API behavior, SQLite access and schema migration, and library file handling. Use those flows as examples for the new app's boundaries and data lifecycle.
- Browser UI: `VDL/templates/index.html` renders the page shell; `VDL/static/app.js` and `VDL/static/styles.css` implement the client without a build step. Follow this simple web-app shape as the initial reference.
- Persistence and files: VDL keeps library records and preferences in SQLite, stores media on disk, and checks access before serving files. Adapt that separation to ebook/PDF metadata, document storage, and authorized reading or download.
- Live updates: `VDL/vdl.py` exposes Server-Sent Events and the browser refreshes API state when events arrive. Use this pattern if document import or processing needs live progress.
- Delivery and verification: `VDL/Dockerfile`, `VDL/compose.yaml`, and `VDL/tests/` show its container setup and testing approach. Build this app's own deployment and tests in the root repository.

Translate VDL's video-specific behavior into document-library requirements as they are defined. Treat downloading videos, playback, transcoding, and the browser extension as prototype details, not assumed features of this app.

Use Docling for document conversion and extraction in Tomeshed. Preserve source files for faithful reading; Docling's structured output is not a PDF/EPUB replacement.
