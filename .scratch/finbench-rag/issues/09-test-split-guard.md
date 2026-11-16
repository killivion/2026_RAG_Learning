# 09: Test-split guard

**What to build:** The runner mechanically prevents test leakage (ADR-0001). A run on the test split is refused unless the final flag is given and the config's hash is in the committed frozen-configs list. The refusal says why.

**Blocked by:** 08

**Status:** done

- [x] A test-split run without the final flag is refused
- [x] A test-split run with the final flag but an unfrozen config is refused
- [x] A frozen config with the final flag runs, and the run directory records that it was a final run
- [x] Runner tests cover all three cases

## Comments

- 2026-11-16: Implemented in `runner.py` (`TestSplitRefused`, checked before any work), with the `--final` flag on `finbench run` and five tests in `tests/test_runner.py`.
- The frozen-configs list is `configs/frozen.txt`: one config hash per line, with the config name as a comment. It is committed and currently empty, so no test-split run is possible yet.
- Every run's `manifest.json` now has a `final` field; it is true only for a test-split run.
- There is no command that adds a config to the list. Freezing is a deliberate manual edit plus commit, which happens once in M3.
- The guard checks that the hash is in the file, not that the file is committed. Committing it before the final run stays a rule for the person running it.
