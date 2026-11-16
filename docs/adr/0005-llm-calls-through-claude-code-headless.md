# LLM calls go through headless Claude Code on the Pro subscription, behind a swappable backend

The user wants no spending beyond their Claude Pro subscription, and a Pro subscription includes no API access. So every generator and judge call runs through Claude Code's non-interactive mode: one turn, no tools, our own system prompt, JSON-schema output. The call sits behind an LLM backend interface, so a pay-as-you-go API backend can replace it later as a config change rather than a rewrite.

## Consequences

- **Usage limits, not money, are the budget.** Pro usage windows cap throughput. Every call is cached on disk, keyed by its full request, and runs can resume, so a run that hits a limit continues later without repeating calls.
- **The cost metric is notional.** We report tokens and the CLI's reported cost at API list prices, labelled "notional", rather than euros actually spent.
- **Model choice is limited** to models the subscription offers in Claude Code: generator `claude-sonnet-5-5`, judge `claude-haiku-5-5` (see ADR-0004).
- **There are no sampling controls.** Current models reject `temperature` anyway, so self-consistency relies on the default sampling variation.
- **Terms of use (checked 2026-11-16):** our reading is that this use is allowed, but the terms don't say so in these words.
  - The Consumer Terms (effective 2025-10-08, section 3) forbid automated access "except ... where we otherwise explicitly permit it".
  - Claude Code's "Legal and compliance" page says subscription login is for "ordinary use of Claude Code", and that an end user may sign in to the unmodified Claude Code binary with their own subscription. Its restrictions are aimed at developers who build products on subscription logins or route other people's requests through them. We do neither: one person, their own login, the unmodified CLI, non-commercial research.
  - The headless docs present `claude -p` as the normal mode for scripts.
  - Open points: "ordinary, individual usage" has no number, and Anthropic can enforce it without notice. So keep volumes modest (the cache and `max_llm_calls` do this), never share the login, and switch to the API backend if the project becomes commercial or shared.
- **`--bare` may become the default for `-p`.** The docs say so, and bare mode ignores the subscription login. If a CLI update breaks calls with an authentication error, this is the first thing to check.
