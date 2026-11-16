# 07: pdfplumber parser and comparison

**What to build:** A second parser (pdfplumber) behind the same interface. The alignment check reports both parsers side by side, overall and for evidence pages that contain tables, so that the parser choice for M2 is made on evidence.

**Blocked by:** 06

**Status:** done

- [x] `finbench parse-check --parser pdfplumber` works and reuses the cache
- [x] A comparison table (overall match rate, table-page match rate, parse time) is written as a committed results file
- [x] The chosen default parser is set in config, with its reason in the learning note for this milestone

## Comments

- 2026-11-16: Implemented in `src/finbench/parsing.py` (`PdfplumberParser`, `compare_parsers`), with `finbench parse-compare`, which writes `results/parser_comparison.csv`. New dependency: `pdfplumber`.
- **Change of criterion, agreed with the user.** The match rate favours PyMuPDF by construction (see ticket 06), so the default parser was chosen on dev BM25 retrieval and parse time instead.
- **Alignment:** PyMuPDF matches 100% of the 189 evidence pages, pdfplumber 97.9% (table pages: 100% against 99.2%). Both confirm zero-indexing for every page.
- **Parse time:** PyMuPDF 34 s, pdfplumber 2,607 s (43 min) for the 84 filings.
- **Dev BM25** (51 questions): the shared index gives recall@10 of 0.157 with both parsers; filing-scoped search gives 0.412 with PyMuPDF and 0.373 with pdfplumber, a gap of two questions.
- **Decision:** PyMuPDF stays the default parser in the config. Retrieval is tied within noise and PyMuPDF is about 77 times faster. The full tables, run directories and limits are in `learning/01-parser-comparison.md`.
- A table page is an evidence page where at least a fifth of the tokens are numbers (122 of 189 pages). It is judged on FinanceBench's text, so it is the same set for both parsers.
- The parse cache now also stores the parse time, so the comparison can be rewritten from the cache in seconds.
