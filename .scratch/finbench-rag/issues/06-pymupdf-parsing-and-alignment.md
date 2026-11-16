# 06: PyMuPDF parsing and alignment check

**What to build:** Filings are parsed page by page into zero-indexed page texts behind the parser interface, with PyMuPDF as the first implementation and results cached per (parser, filing). An alignment check fuzzy-matches each evidence page's `evidence_text` and `evidence_text_full_page` against the parsed text of that page. It reports a match rate per parser and lists the worst pages.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] `finbench parse-check --parser pymupdf` parses the 84 filings and reports the match rate over all evidence pages
- [ ] The check confirms zero-indexing: page n matches better than pages n-1 and n+1 for at least 95% of evidence pages
- [ ] A rerun uses the cache
- [ ] Tests on a tiny generated PDF check page numbering and caching; the real-data check is marked as a data test, which CI skips
