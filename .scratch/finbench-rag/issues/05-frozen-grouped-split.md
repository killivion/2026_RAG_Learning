# 05: Frozen grouped split

**What to build:** A dev/test split made once, grouped by company and balanced by question type, about 50 dev and 100 test questions, with a fixed seed (ADR-0001). It is committed as a small file of question ids. Once that file exists, the split command refuses to overwrite it. Loading a split returns its questions.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] `finbench split` writes the split file and prints sizes, company counts and the question-type mix for each side
- [ ] No company appears in both splits; each question type's share differs by at most 5 percentage points between the splits
- [ ] A second `finbench split` refuses unless forced, and forcing it is documented as a protocol violation
- [ ] Tests on synthetic questions check the grouping, the balance and the overwrite refusal
- [ ] The split summary is added to the spec's Further Notes
