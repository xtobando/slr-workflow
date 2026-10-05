"""Optional document and vector adapters. Core commands do not import heavy dependencies."""

from __future__ import annotations

import hashlib
import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

import yaml

from .database import Database, canonical_json, stable_id
from .service import ReviewService


def convert_document(service: ReviewService, report_id: str, pdf: Path) -> dict[str, Any]:
    """Keep original PDF, Docling JSON, Markdown, page/region/element provenance."""
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as error:
        raise ValueError("Install requirements-documents.txt to enable PDF conversion") from error
    service.check_ready()
    pdf_id = service.attach(report_id, pdf, "pdf")
    options = yaml.safe_load((service.config.root / "conversion.yaml").read_text(encoding="utf-8"))
    if (
        not isinstance(options, dict)
        or set(options) != {"pipeline"}
        or not isinstance(options["pipeline"], dict)
    ):
        raise ValueError("conversion.yaml must contain a pipeline options mapping")
    pipeline = PdfPipelineOptions(**options["pipeline"])
    result = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)}
    ).convert(pdf)
    doc = result.document
    output = service.config.root / "data" / "conversion" / pdf_id
    output.mkdir(parents=True, exist_ok=True)
    structured = output / "docling.json"
    markdown = output / "document.md"
    doc.save_as_json(structured)
    doc.save_as_markdown(markdown)
    elements = []
    for item, _ in doc.iterate_items():
        text = getattr(item, "text", None)
        if not text and hasattr(item, "export_to_markdown"):
            text = item.export_to_markdown(doc=doc)
        if not text:
            continue
        provenance = getattr(item, "prov", [])
        anchor = provenance[0] if len(provenance) == 1 else None
        elements.append(
            {
                "id": getattr(item, "self_ref", f"item_{len(elements)}"),
                "page": anchor.page_no if anchor else None,
                "source_pages": sorted({p.page_no for p in provenance}),
                "regions": [p.bbox.model_dump(mode="json") for p in provenance],
                "text": text,
            }
        )
    structured_id = service.attach(report_id, structured, "docling_json", elements)
    markdown_id = service.attach(report_id, markdown, "markdown")
    with service.db.connect(write=True) as connection:
        Database.event(
            connection,
            service.config.revision,
            "document_converted",
            "report",
            report_id,
            {
                "converter": "docling",
                "version": version("docling"),
                "options": options["pipeline"],
                "pdf_id": pdf_id,
                "structured_document_id": structured_id,
                "markdown_id": markdown_id,
            },
        )
    return {
        "pdf_id": pdf_id,
        "structured_document_id": structured_id,
        "markdown_id": markdown_id,
        "elements": len(elements),
        "note": "Review important equations and tables against the original PDF",
    }


def rag_configuration(service: ReviewService) -> dict[str, Any]:
    config = yaml.safe_load((service.config.root / "rag.yaml").read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) != {
        "embedding_model",
        "chunk_characters",
        "overlap_characters",
        "persist_directory",
    }:
        raise ValueError(
            "rag.yaml must define embedding_model, chunk_characters, overlap_characters, persist_directory"
        )
    if not isinstance(config["chunk_characters"], int) or config["chunk_characters"] < 100:
        raise ValueError("chunk_characters must be an integer >= 100")
    if (
        not isinstance(config["overlap_characters"], int)
        or not 0 <= config["overlap_characters"] < config["chunk_characters"]
    ):
        raise ValueError("overlap_characters must be between zero and chunk_characters")
    return config


def included_documents(service: ReviewService) -> list[dict[str, Any]]:
    with service.db.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM documents WHERE text_content IS NOT NULL ORDER BY rowid"
        ).fetchall()
        by_report: dict[str, dict[str, Any]] = {}
        # Prefer structured provenance over plain Markdown; select one representation per publication.
        for row in rows:
            if not service.report_is_included(connection, row["report_id"]):
                continue
            existing = by_report.get(row["report_id"])
            if not existing or row["kind"] == "docling_json" or existing["kind"] != "docling_json":
                by_report[row["report_id"]] = dict(row)
        return list(by_report.values())


def vector_collection(service: ReviewService) -> tuple[Any, list[dict[str, Any]], dict[str, Any]]:
    """Fingerprint the corpus/configuration to prevent stale vector answers after revisions."""
    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    except ImportError as error:
        raise ValueError("Install requirements-rag.txt to enable semantic retrieval") from error
    service.check_ready()
    config = rag_configuration(service)
    documents = included_documents(service)
    fingerprint = hashlib.sha256(
        canonical_json(
            {
                "protocol": service.config.revision,
                "config": config,
                "adapter_versions": {
                    "chromadb": version("chromadb"),
                    "sentence-transformers": version("sentence-transformers"),
                },
                "documents": sorted(d["id"] for d in documents),
            }
        ).encode()
    ).hexdigest()[:24]
    client = chromadb.PersistentClient(path=str(service.config.root / config["persist_directory"]))
    embedding = SentenceTransformerEmbeddingFunction(model_name=config["embedding_model"])
    return (
        client.get_or_create_collection("slr-" + fingerprint, embedding_function=embedding),
        documents,
        config,
    )


def index_corpus(service: ReviewService) -> dict[str, Any]:
    collection, documents, config = vector_collection(service)
    ids, texts, metadata = [], [], []
    for document in documents:
        for element in json.loads(document["elements_json"]):
            text = element["text"]
            stride = config["chunk_characters"] - config["overlap_characters"]
            for start in range(0, len(text), stride):
                fragment = text[start : start + config["chunk_characters"]]
                if not fragment.strip():
                    continue
                ids.append(stable_id("chunk", document["id"] + element["id"] + str(start)))
                texts.append(fragment)
                metadata.append(
                    {
                        "document_id": document["id"],
                        "report_id": document["report_id"],
                        "element_id": element["id"],
                        "page": element.get("page") or 0,
                        "start": start,
                        "end": start + len(fragment),
                    }
                )
    for start in range(0, len(ids), 32):
        collection.upsert(
            ids=ids[start : start + 32],
            documents=texts[start : start + 32],
            metadatas=metadata[start : start + 32],
        )
    return {"collection": collection.name, "documents": len(documents), "chunks": len(ids)}


def retrieve(service: ReviewService, query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not query.strip() or limit < 1:
        raise ValueError("Nonempty query and positive limit required")
    collection, _, _ = vector_collection(service)
    if not collection.count():
        raise ValueError("Current corpus/configuration has no index; run slr index-corpus")
    result = collection.query(query_texts=[query], n_results=min(limit, collection.count()))
    hits = [
        {"chunk_id": chunk_id, "text": text, "distance": distance, **metadata}
        for chunk_id, text, distance, metadata in zip(
            result["ids"][0], result["documents"][0], result["distances"][0], result["metadatas"][0]
        )
    ]
    for hit in hits:
        if hit["page"] == 0:
            hit["page"] = None
    return hits
