"""PDF reading is independent of review state and preserves page-level missingness."""

import hashlib
import json
from pathlib import Path

import pytest
from cli_runner import CliRunner

from slr_workbench.cli import app
from slr_workbench.pdf_reader import read_pdf

pypdf = pytest.importorskip("pypdf")
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_pdf(path: Path, *, blank: bool = False, encrypted: bool = False) -> None:
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    if not blank:
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 20 200 Td (Synthetic PDF evidence) Tj ET")
        page[NameObject("/Contents")] = stream
        writer.add_blank_page(width=300, height=300)
    if encrypted:
        writer.encrypt("synthetic-password")
    writer.write(path)


def test_pdf_reading_before_any_configuration(tmp_path: Path) -> None:
    source = tmp_path / "paper with spaces.pdf"
    make_pdf(source)
    result = CliRunner().invoke(app, ["--project", str(tmp_path), "read-pdf", str(source)])
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.output)
    text = Path(receipt["markdown"]).read_text()
    assert "<!-- page: 1 -->" in text and "Synthetic PDF evidence" in text
    assert "<!-- page: 2 -->" in text
    assert receipt["pages_without_text"] == [2]
    assert receipt["status"] == "partial"
    assert receipt["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert Path(receipt["original"]).read_bytes() == source.read_bytes()
    assert not list(tmp_path.rglob("*.sqlite"))
    assert not (tmp_path / "protocol.yaml").exists()


def test_repeated_read_preserves_outputs(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    make_pdf(source)
    first = read_pdf(source, tmp_path / "outputs")
    Path(first["markdown"]).write_text("user notes")
    second = read_pdf(source, tmp_path / "outputs")
    assert first["markdown"] != second["markdown"]
    assert Path(first["markdown"]).read_text() == "user notes"


def test_empty_pages_are_not_claimed_as_read(tmp_path: Path) -> None:
    source = tmp_path / "blank.pdf"
    make_pdf(source, blank=True)
    result = read_pdf(source, tmp_path / "outputs")
    assert result["status"] == "no_text"
    assert result["pages_without_text"] == [1]
    assert result["ocr_performed"] is False


@pytest.mark.parametrize("encrypted", [False, True])
def test_unreadable_input_does_not_write_success(tmp_path: Path, encrypted: bool) -> None:
    source = tmp_path / "bad.pdf"
    if encrypted:
        make_pdf(source, encrypted=True)
    else:
        source.write_bytes(b"not a PDF")
    with pytest.raises(ValueError):
        read_pdf(source, tmp_path / "outputs")
    assert not (tmp_path / "outputs").exists()
