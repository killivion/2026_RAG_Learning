# The LLM judge comes from the same model family as the generator

The plan preferred a judge from a different model family, to avoid self-preference bias. We accept a same-family judge (Claude) to keep a single API provider and a single budget. To mitigate this:
- the judge is a different model version from the generator;
- the judge never sees the config name or the retrieved context;
- the judge prompt is tuned only on dev-question annotations from FinanceBench's human-labelled completions, and agreement is reported on test-question annotations.

Self-preference bias is listed as a limitation.
