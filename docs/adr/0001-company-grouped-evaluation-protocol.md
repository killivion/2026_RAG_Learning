# Company-grouped splits, and the test split is used only for reporting

The 150 FinanceBench questions cover 32 companies (1 to 11 questions each). We split them once, with a fixed seed, into a dev split of about 50 and a test split of about 100. No company appears in both splits, and the three question types are balanced. The split file is committed. Grouping prevents tuning chunking or prompts on a company's filings and then testing on that same company. Grouping by filing would allow exactly that, because a company's 10-K and 10-Q share layout and wording.

The conformal calibration/evaluation splits inside test are grouped by company for the same reason: questions from one company are not exchangeable with each other. Every choice (config, prompt, judge prompt, which confidence signal to prefer) is made on dev. On test, every confidence signal is reported and no winner is picked there.

## Consequences

- With roughly 20 test companies, each calibration half holds about 10 companies, so the reported conformal coverage distribution will be wide. That width is the honest result.
