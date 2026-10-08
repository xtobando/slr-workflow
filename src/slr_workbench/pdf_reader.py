"""Stage-independent PDF reading; never mutates the review database."""

from __future__ import annotations

import hashlib
import json
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Any


def read_pdf(pdf: Path, output_dir: Path) -> dict[str, Any]:
    """Extract native text into page-anchored Markdown and an audit manifest."""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError as error:
        raise ValueError(
            "PDF reader is missing. Rerun setup or install the 'pdf' extra."
        ) from error
    source = pdf.resolve(strict=True)
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    from io import BytesIO

    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Encrypted PDF: provide an authorized decrypted copy first.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PyPdfError, NotImplementedError) as error:
        raise ValueError(f"PDF extraction failed: {error}") from error
    if not pages:
        raise ValueError("The PDF contains no pages.")
    empty = [i for i, text in enumerate(pages, 1) if not text.strip()]
    warnings = ["Verify reading order, tables, formulas and quotations against the original PDF."]
    if empty:
        warnings.append(f"No text on physical pages {empty}; these may need OCR or be blank.")
    # A unique directory preserves previous conversions, even for identical source bytes.
    output_dir.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix=f"{digest[:12]}-", dir=output_dir))
    original = target / "original.pdf"
    original.write_bytes(data)
    markdown = target / "document.md"
    # Plain extracted text, without generated summaries or reconstructed scientific claims.
    markdown.write_text(
        "\n\n".join(f"<!-- page: {i} -->\n{text}" for i, text in enumerate(pages, 1)) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "source_name": source.name,
        "source_sha256": digest,
        "original": str(original.resolve()),
        "markdown": str(markdown.resolve()),
        "markdown_sha256": hashlib.sha256(markdown.read_bytes()).hexdigest(),
        "converter": "pypdf",
        "converter_version": version("pypdf"),
        "page_numbering": "physical PDF pages, starting at 1",
        "pages": len(pages),
        "pages_without_text": empty,
        "status": "no_text"
        if len(empty) == len(pages)
        else "partial"
        if empty
        else "text_extracted",
        "ocr_performed": False,
        "warnings": warnings,
    }
    receipt = target / "manifest.json"
    receipt.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {**manifest, "manifest": str(receipt.resolve())}
