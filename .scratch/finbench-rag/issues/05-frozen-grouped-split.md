# 05: Frozen grouped split

**What to build:** A dev/test split made once, grouped by company and balanced by question type, about 50 dev and 100 test questions, with a fixed seed (ADR-0001). It is committed as a small file of question ids. Once that file exists, the split command refuses to overwrite it. Loading a split returns its questions.

**Blocked by:** 04

**Status:** done

- [x] `finbench split` writes the split file and prints sizes, company counts and the question-type mix for each side
- [x] No company appears in both splits; each question type's share differs by at most 5 percentage points between the splits
- [x] A second `finbench split` refuses unless forced, and forcing it is documented as a protocol violation
- [x] Tests on synthetic questions check the grouping, the balance and the overwrite refusal
- [x] The split summary is added to the spec's Further Notes

## Comments

- 2026-11-16: Implemented in `src/finbench/dataset.py` (`make_split`, `write_split`, `load_split`), with `finbench split` and `tests/test_split.py`. The real split is committed as `splits/financebench.json` (question ids only).
- **Result:** dev 51 questions, 10 companies, 27 filings, types 17/17/17. Test 99 questions, 22 companies, 57 filings, types 33/33/33. No company is in both.
- **Method:** random search with seed 0. The companies are shuffled 2,000 times; each time dev takes the first companies that bring it closest to a third of the questions; the shuffle with the smallest type-share gap plus size error wins. The search sees only company and question type, never questions, answers or results.
- **Not balanced:** the number of evidence pages per question. It came out close anyway (dev 39/11/1, test 76/20/3 for one/two/three evidence items).
- `Split` moved from `runner.py` to `dataset.py`, because the dataset owns the split and the runner imports it.
- `--force` overwrites the split. Its help text and the README call this a protocol violation (ADR-0001).
