# Tomeshed feature plan

**Source:** User-requested first version  
**Status:** Proposed  
**Last refined:** 2026-10-10

Feature files follow VDL's `FEATURES/feature-NNNN-description.md` convention. Each file has its own outcome and acceptance criteria. Build them in number order when a dependency is listed; after Feature 0002, the organization and ingest workflows can be developed separately from the reader.

| Order | Feature | Depends on | Outcome |
| --- | --- | --- | --- |
| 0001 | [App shell, accounts, settings, and version](feature-0001-app-shell-and-access.md) | — | A running, signed-in Tomeshed shell with fixed chrome and honest version state |
| 0002 | [Import and browse documents](feature-0002-import-and-browse-documents.md) | 0001 | Searchable PDF/EPUB catalog with cover cards and Docling extraction |
| 0003 | [Read and resume](feature-0003-read-and-resume-documents.md) | 0002 | In-browser reading that restores each user's position |
| 0004 | [Hover preview](feature-0004-page-through-hover-preview.md) | 0003 | A page-through speech bubble beside a document card |
| 0005 | [Organize and find](feature-0005-organize-and-find-documents.md) | 0002, 0003 | Tags, favorites, reading state, metadata, and richer filters |
| 0006 | [Library file workflows](feature-0006-library-file-workflows.md) | 0002 | Drag-and-drop, direct URL and watched-folder ingest, export, and safe cleanup |
| 0007 | [Personal bookshelves](feature-0007-personal-bookshelves.md) | 0002, 0003 | Ordered collections of books with personal reading continuity |

Features 0001–0004 establish the requested first reading experience. Features 0005–0007 adapt the remaining VDL library capabilities that fit books and PDFs; each can be planned and built as a separate slice after its listed dependencies.

## VDL translation

| VDL capability | Tomeshed destination |
| --- | --- |
| Fixed header/footer, version mismatch, account menu, settings, roles, theme, health | 0001 |
| Thumbnail library, import progress, SQLite catalog, authenticated file access, search | 0002 |
| Media opening and durable playback position | 0003, as document reading position |
| Hover preview | 0004, as an interactive page-through bubble |
| Tags, favorites, view state, filters, Info panel | 0005 |
| Local upload/export and watched inbox | 0006 |
| Personal playlists | 0007, as bookshelves |

Video URL extraction, yt-dlp formats, transcoding, playback controls, continuous or shuffled playback, and the browser extension do not describe reading workflows. They are not carried into these features.

For implementation details, inspect the current VDL source as well as its corresponding feature files: `feature-0017-make-history-the-primary-thumbnail-library.md` for cards and fixed chrome, `feature-0022-move-settings-to-a-searchable-page.md` and `feature-0023-require-authentication-and-manage-users.md` for settings and accounts, `feature-0021-import-and-export-local-videos.md` and `feature-0024-ingest-videos-from-a-watched-folder.md` for ingest, and `feature-0031-add-personal-video-playlists.md` for collections. VDL's files are a reference, not files to edit or copy wholesale.

## Document-format constraint

Docling accepts PDF and EPUB input and can export its structured document as JSON, HTML, and other text-oriented formats. It does not currently list PDF or EPUB among its output formats. Tomeshed therefore retains the original upload for faithful reading and download, and uses Docling output for metadata, indexing, and optional derived views. EPUB pagination can change with screen and font size; show an explicitly estimated page count unless stable publisher page markers are available.

Sources: [Docling supported formats](https://docling-project.github.io/docling/usage/supported_formats/), [Docling EPUB example](https://docling-project.github.io/docling/_generated/examples/epub_conversion/), [W3C EPUB pagination guidance](https://www.w3.org/TR/epub-a11y-explain-12/).
