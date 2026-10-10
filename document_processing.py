"""Validate and process one stored document in a bounded child process."""

from __future__ import annotations

import json
import math
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree


def cleaned_title(filename):
    stem = Path(filename.replace("\\", "/").split("/")[-1]).stem
    return re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", stem)).strip() or "Untitled document"


def detect_source(path):
    with path.open("rb") as stream:
        head = stream.read(32)
    if head.startswith(b"%PDF-"):
        from pypdf import PdfReader
        reader = PdfReader(str(path), strict=True)
        count = len(reader.pages)
        if count < 1:
            raise ValueError("PDF has no pages")
        metadata = reader.metadata
        return "pdf", (metadata.title or "") if metadata else "", (metadata.author or "") if metadata else "", count
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            if "mimetype" not in archive.namelist() or archive.read("mimetype") != b"application/epub+zip":
                raise ValueError("Unsupported archive")
            try:
                container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
                rootfile = container.find(".//{*}rootfile")
                if rootfile is None:
                    raise ValueError("EPUB has no package")
                package = ElementTree.fromstring(archive.read(rootfile.attrib["full-path"]))
                title = package.findtext(".//{http://purl.org/dc/elements/1.1/}title") or ""
                author = package.findtext(".//{http://purl.org/dc/elements/1.1/}creator") or ""
                spine = package.find(".//{*}spine")
                if spine is None or not list(spine):
                    raise ValueError("EPUB has no reading order")
                manifest = {item.attrib.get("id"): item.attrib.get("href") for item in package.findall(".//{*}manifest/{*}item")}
                package_dir = posixpath.dirname(rootfile.attrib["full-path"])
                for item in spine:
                    href = manifest.get(item.attrib.get("idref"))
                    if not href or posixpath.normpath(posixpath.join(package_dir, unquote(href))) not in archive.namelist():
                        raise ValueError("EPUB reading order refers to missing content")
            except (KeyError, ElementTree.ParseError) as exc:
                raise ValueError("Invalid EPUB structure") from exc
        return "epub", title, author, None
    try:
        from docling_core.types.doc import DoclingDocument
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("DoclingDocument JSON must be an object")
        document = DoclingDocument.model_validate(raw)
        if not document.name or not (document.texts or document.tables or document.pictures or document.pages):
            raise ValueError("DoclingDocument JSON has no document content")
        return "docling", document.name, "", len(document.pages) or None
    except (UnicodeDecodeError, json.JSONDecodeError, OSError, ImportError) as exc:
        raise ValueError("Unsupported or corrupt document") from exc


def extract_docling(path):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import NativePdfPipelineOptions
    from docling.document_converter import DocumentConverter, NativePdfFormatOption
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.EPUB, InputFormat.JSON_DOCLING],
        format_options={InputFormat.PDF: NativePdfFormatOption(pipeline_options=NativePdfPipelineOptions(parser_threads=2))},
    )
    result = converter.convert(path)
    document = result.document
    return document.export_to_dict(), document.export_to_text()


def make_thumbnail(path, source_type, title, target):
    """Write a first-page PDF image or a generated EPUB cover."""
    if source_type == "pdf":
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(path))
        try:
            page = pdf[0]
            try:
                page.render(scale=1.2).to_pil().convert("RGB").save(target, format="PNG")
            finally:
                page.close()
        finally:
            pdf.close()
    elif source_type == "epub":
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new("RGB", (360, 510), "#234939")
        draw = ImageDraw.Draw(image)
        draw.rectangle((24, 24, 336, 486), outline="#d9c99b", width=3)
        try:
            font = ImageFont.truetype("LiberationSans-Regular.ttf", 36)
            cover_title = title
        except OSError:
            font = ImageFont.load_default(size=36)
            cover_title = title if title.isascii() else "EPUB"
        words = cover_title.split()
        lines = []
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if len(candidate) > 14 and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        draw.multiline_text((48, 135), "\n".join(lines[:7]), fill="white", spacing=12, font=font)
        image.save(target, format="PNG")


def process_document(source, filename, staging):
    source = Path(source)
    staging = Path(staging)
    size = source.stat().st_size
    try:
        source_type, source_title, source_author, exact_pages = detect_source(source)
    except Exception as exc:
        return {"state": "failed", "error": str(exc)}
    title = source_title.strip() or cleaned_title(filename)
    author = source_author.strip() or "Unknown author"
    text = ""
    warning = None
    artifact = None
    page_count = exact_pages
    count_kind = "exact" if exact_pages else "unknown"
    if source_type == "docling":
        from docling_core.types.doc import DoclingDocument
        structured = json.loads(source.read_text(encoding="utf-8"))
        document = DoclingDocument.model_validate(structured)
        text = document.export_to_text()
        artifact = "structured.json"
        (staging / artifact).write_text(json.dumps(document.export_to_dict()), encoding="utf-8")
    else:
        try:
            conversion_input = staging / f"input.{source_type}"
            conversion_input.write_bytes(source.read_bytes())
            structured, text = extract_docling(conversion_input)
            artifact = "structured.json"
            (staging / artifact).write_text(json.dumps(structured), encoding="utf-8")
        except Exception as exc:
            warning = f"Indexing warning: {exc}"
        if source_type == "epub" and not warning:
            words = len(text.split())
            if words:
                page_count = max(1, math.ceil(words / 300))
                count_kind = "estimated"
    thumbnail = None
    try:
        make_thumbnail(source, source_type, title, staging / "thumbnail.png")
        if (staging / "thumbnail.png").is_file():
            thumbnail = "thumbnail.png"
    except Exception:
        pass
    return {
        "state": "ready_with_warning" if warning else "ready",
        "error": warning,
        "source_type": source_type,
        "title": title,
        "author": author,
        "byte_size": size,
        "text": text,
        "page_count": page_count,
        "count_kind": count_kind,
        "artifact": artifact,
        "thumbnail": thumbnail,
    }


def main():
    source, filename, staging = sys.argv[1:4]
    target = Path(staging)
    target.mkdir(parents=True, exist_ok=True)
    try:
        result = process_document(source, filename, target)
    except Exception as exc:
        result = {"state": "failed", "error": str(exc)}
    (target / "result.json").write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
