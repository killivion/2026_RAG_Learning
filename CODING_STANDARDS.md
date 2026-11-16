# Coding standards

Read at review time. These are the judgement calls; ruff, mypy and pytest already enforce the mechanical rules (`.pre-commit-config.yaml`, `.github/workflows/ci.yml`).

## Reading limits

Review from the diff and the files it names. Leave `data/`, `pdfs/`, `cache/` and `runs/` unopened: they are large, git-ignored and hold non-commercial FinanceBench data.

## Code

- Type hints everywhere; trust the type checker instead of adding runtime checks for what it already proves.
- Readable over clever. Each change does what its ticket asks; an extra feature is a finding unless the ticket comment says what it is and why.
- Fix root causes, not symptoms.
- Modules are deep with small interfaces (spec, "Implementation Decisions"). The CLI only parses arguments.
- Files written to a cache are written to a `.part` file and renamed.

## Tests

- A test exercises behaviour through a public interface and asserts on what a user of the module cares about. It survives a refactor of the internals.
- Expected values come from a hand-worked case or the spec, never from recomputing them the way the code does.
- The seams are fixed in the spec's "Testing Decisions": the experiment runner on the made-up filings, and the pure evaluation functions.
- Tests need no network, Docker or LLM. Real-data tests carry the `data` marker and real LLM calls the `live` marker.

## Research correctness

A wrong number is the worst defect in this project, so check these first:

- **Leakage:** every choice is made on dev (`docs/adr/0001`). Flag any code path where a dev run reads test labels, or where a test-split run is possible without the final flag and a frozen config.
- **Metrics:** they count pages, not chunks (`docs/adr/0002`). Check the definition against the glossary and a hand-worked case.
- **Cache keys:** everything that changes a cached result is part of its key.
- **Reported numbers:** a number in `README.md`, a ticket or a learning note matches a committed file under `results/`, which names its run directory.

## Consistency

This project has no NOTES.md and no presentation notebook. A change is consistent when it agrees with:

- `README.md`, the technical report;
- `GLOSSARY.md`: new terms are added, and code and docs use its vocabulary;
- `.scratch/finbench-rag/spec.md` and the ticket being implemented;
- `docs/adr/`: a new hard-to-reverse decision has an ADR;
- `learning/`, when a note covers the changed concept.

FinanceBench data, PDFs and text never enter git; committed result files hold numbers and question ids only.
