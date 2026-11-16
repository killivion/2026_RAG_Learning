# 06: PyMuPDF parsing and alignment check

**What to build:** Filings are parsed page by page into zero-indexed page texts behind the parser interface, with PyMuPDF as the first implementation and results cached per (parser, filing). An alignment check fuzzy-matches each evidence page's `evidence_text` and `evidence_text_full_page` against the parsed text of that page. It reports a match rate per parser and lists the worst pages.

**Blocked by:** 04

**Status:** done

- [x] `finbench parse-check --parser pymupdf` parses the 84 filings and reports the match rate over all evidence pages
- [x] The check confirms zero-indexing: page n matches better than pages n-1 and n+1 for at least 95% of evidence pages
- [x] A rerun uses the cache
- [x] Tests on a tiny generated PDF check page numbering and caching; the real-data check is marked as a data test, which CI skips

## Comments

- 2026-11-16: Implemented in `src/finbench/parsing.py` (`Parser`, `PyMuPDFParser`, `parse_filing`, `check_alignment`), with `finbench parse-check` and `tests/test_parsing.py`. New dependencies: `pymupdf` (parser) and `rapidfuzz` (fuzzy matching).
- **Result for PyMuPDF** (84 filings, 12,013 pages, 189 evidence pages):
  - Match rate 100%: every evidence page scores at least 90 of 100 on both checks.
  - Zero-indexing confirmed for 100%: page n always beats pages n-1 and n+1, and by a wide margin (95 or more against at most about 53).
  - Worst page: `CORNING_2020_10K` page 71, with 90.9 for the evidence text and 95.3 for the full page.
  - The first run takes about 35 s; a rerun from the cache takes about 6 s.
- **How a page is scored.** Whitespace is collapsed first. The full-page score is the edit-distance similarity between FinanceBench's page text and the parsed page. The evidence-text score is the best similarity of the evidence passage to any part of the parsed page. A page counts as matched when both are at least 90.
- **Caveat for ticket 07.** The scores are so close to 100 that FinanceBench's page texts were very likely extracted with PyMuPDF as well. The match rate therefore measures agreement with FinanceBench's own extraction, not parsing quality. pdfplumber will score lower by construction, so the parser comparison needs a second criterion (for example how tables come out, or retrieval results on dev).
- In this dataset `evidence_text` is usually almost the whole page, so the two scores carry nearly the same information.
- The cache is `cache/parsed/<parser>/<filing>.json` (about 44 MB for PyMuPDF, git-ignored). It is keyed by parser name and filing only, so delete the folder after a parser change or a PyMuPDF upgrade.
- Plain `uv run pytest` now runs the `data` test and needs the downloaded data; CI and pre-commit skip it.
