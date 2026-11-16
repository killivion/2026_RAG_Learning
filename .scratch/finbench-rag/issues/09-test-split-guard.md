# 09: Test-split guard

**What to build:** The runner mechanically prevents test leakage (ADR-0001). A run on the test split is refused unless the final flag is given and the config's hash is in the committed frozen-configs list. The refusal says why.

**Blocked by:** 08

**Status:** ready-for-agent

- [ ] A test-split run without the final flag is refused
- [ ] A test-split run with the final flag but an unfrozen config is refused
- [ ] A frozen config with the final flag runs, and the run directory records that it was a final run
- [ ] Runner tests cover all three cases
