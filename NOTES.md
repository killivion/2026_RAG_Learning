# Notes

My notes for learning and explaining this project, for example in an interview. Each concept gets one section, a learning note. Claude drafts it at the end of a milestone and I rewrite it in my own words; the rewriting is where the learning happens. Vocabulary follows `GLOSSARY.md`, and decisions link to `docs/adr/` instead of repeating them.

## Pitch

_The two-minute spoken pitch, updated at the end of every milestone. The first version is written at the M1 close-out (ticket 11)._

## Parser comparison (PyMuPDF vs pdfplumber)

_Draft by Claude at the end of ticket 07. Rewrite in your own words._

### What it is

A parser turns a filing's PDF into one text per page. Two parsers sit behind the same interface: PyMuPDF and pdfplumber. The comparison asks which one to use for everything that follows, and answers it with measurements on the dev split.

### Why it is used here

Every later stage (chunking, retrieval, the generator's context) sees only what the parser produced, so a bad parser caps the whole system. SEC filings are full of tables, which is where parsers differ most.

Three things were measured:

- **Alignment with FinanceBench.** Each evidence page's FinanceBench text is fuzzy-matched against the parsed page with the same number. This mainly proves that page numbers line up (zero-indexing).
- **Retrieval on dev.** The same BM25 config is run once per parser. This is the criterion that counts.
- **Parse time** for all 84 filings.

The alignment score alone would have been a biased criterion. PyMuPDF's scores are almost exactly 100, which means FinanceBench's page texts were very likely made with PyMuPDF. pdfplumber would lose on that measure even if its text were better.

### What the experiment showed

Alignment and speed, all 84 filings and 189 evidence pages (`results/parser_comparison.csv`):

| Parser | Match rate | Mean page score | Match rate on 122 table pages | Zero-indexing confirmed | Parse time |
|---|---|---|---|---|---|
| PyMuPDF | 100% | 99.5 | 100% | 100% | 34 s |
| pdfplumber | 97.9% | 98.8 | 99.2% | 100% | 2,607 s (43 min) |

BM25 on dev, 51 questions, 300-word chunks with 50 words overlap:

| Scope | Parser | recall@5 | recall@10 | MRR |
|---|---|---|---|---|
| Shared index | PyMuPDF | 0.118 | 0.157 | 0.114 |
| Shared index | pdfplumber | 0.118 | 0.157 | 0.112 |
| Filing-scoped search | PyMuPDF | 0.294 | 0.412 | 0.211 |
| Filing-scoped search | pdfplumber | 0.275 | 0.373 | 0.205 |

Every number in this table is in `results/retrieval_runs.csv`, which also names each run directory.

**Decision: PyMuPDF is the default parser.** Retrieval is the same within noise: the largest gap, recall@10 with filing-scoped search, is two questions out of 51. PyMuPDF is about 77 times faster, which matters every time the cache is rebuilt.

Limits of this result:

- 51 questions cannot separate two parsers this close. The decision rests on "no measurable difference, so take the fast one", not on "PyMuPDF retrieves better".
- BM25 only counts words. It cannot tell whether a table's rows and columns stay readable, and that may matter for the generator. If table questions fail in M2 because of garbled tables, this choice should be looked at again.
- A "table page" is defined by a rule of thumb: at least a fifth of the page's tokens are numbers.

### Interview questions

- Q: Why not just pick the parser with the higher match rate against the benchmark's text?
  A: The benchmark's text was very likely produced by one of the two parsers, so that measure rewards agreement with it, not quality. I used it only to confirm page numbering and chose on dev retrieval and parse time.
- Q: How do you know your page numbers match the labels?
  A: For every evidence page, the benchmark's page text matches parsed page n far better than pages n-1 and n+1 (about 95 or more against at most about 53 out of 100). That holds for all 189 evidence pages with both parsers.
- Q: Is a two-question difference on 51 questions meaningful?
  A: No. With 51 questions, one question is two percentage points. I treat the parsers as tied on retrieval.
- Q: What could change this decision later?
  A: Evidence from generation that tables are garbled, for example table-heavy questions failing in the oracle condition, where retrieval cannot be the cause.
