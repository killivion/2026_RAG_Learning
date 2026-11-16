# 07: pdfplumber parser and comparison

**What to build:** A second parser (pdfplumber) behind the same interface. The alignment check reports both parsers side by side, overall and for evidence pages that contain tables, so that the parser choice for M2 is made on evidence.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] `finbench parse-check --parser pdfplumber` works and reuses the cache
- [ ] A comparison table (overall match rate, table-page match rate, parse time) is written as a committed results file
- [ ] The chosen default parser is set in config, with its reason in the learning note for this milestone
