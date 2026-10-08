# PDF reading and formal evidence

Use `/slr-read-pdf "PATH.pdf"` inside OpenCode at any stage. In a terminal:

```sh
# macOS/Linux
bash workbench.sh read-pdf "papers/paper.pdf"
```

```powershell
# Windows
.\workbench.ps1 read-pdf "papers\paper.pdf"
```

The underlying command is `python -m slr_workbench read-pdf PATH`. It can run
without protocol/workflow files or an initialized database. `--output-dir PATH`
changes the output parent; otherwise it uses `data/reading/` under `--project`.
Input paths resolve against the current working directory; the project launcher
always runs from the project root. Quote paths containing spaces.

The installed `pdf` extra uses pypdf for embedded text extraction. No provider
login, OCR model, Docling, Pydantic or report identity is required. Each run writes
into a new directory and preserves earlier outputs. The JSON response names the
Markdown, archived original and manifest. Page markers refer to physical PDF
pages starting at 1, not printed page labels. The manifest includes hashes,
converter version and pages without text. `partial`/`no_text` statuses are reading
limitations, not scientific exclusions; a successfully written output need not
contain readable text.

PDF text can have incorrect reading order or missing formulas/tables. The reader
does not reconstruct these with a language model. Compare critical evidence to
the original. pypdf does not perform OCR; for scanned/image pages obtain a trusted
OCR conversion. The optional registered-report Docling adapter supports OCR but
requires extra dependencies/models. See [pypdf's extraction limitations](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).
Encrypted PDFs require an authorized decrypted copy; passwords are not stored.

## Use a conversion as review evidence

After importing and screening the correct report through the normal workflow,
attach both representations (replace paths/IDs with the conversion result):

```sh
python -m slr_workbench attach REPORT_ID data/reading/CONVERSION/original.pdf --kind pdf
python -m slr_workbench attach REPORT_ID data/reading/CONVERSION/document.md --kind markdown
```

Use the returned Markdown document ID and verified exact quote/page anchors in
your draft. The reading manifest remains beside the original for provenance;
it is not itself a review decision. Keep all review gates: neither the reading
utility nor the skill authorizes approval, inclusion or study linking.
