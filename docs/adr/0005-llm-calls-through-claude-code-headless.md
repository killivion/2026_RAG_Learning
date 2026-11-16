# LLM calls go through headless Claude Code on the Pro subscription, behind a swappable backend

The user wants no spending beyond their Claude Pro subscription, and a Pro subscription includes no API access. So every generator and judge call runs through Claude Code's non-interactive mode: one turn, no tools, our own system prompt, JSON-schema output. The call sits behind an LLM backend interface, so a pay-as-you-go API backend can replace it later as a config change rather than a rewrite.

## Consequences

- **Usage limits, not money, are the budget.** Pro usage windows cap throughput. Every call is cached on disk, keyed by its full request, and runs can resume, so a run that hits a limit continues later without repeating calls.
- **The cost metric is notional.** We report tokens and the CLI's reported cost at API list prices, labelled "notional", rather than euros actually spent.
- **Model choice is limited** to models the subscription offers in Claude Code: generator `claude-sonnet-5-5`, judge `claude-haiku-5-5` (see ADR-0004).
- **There are no sampling controls.** Current models reject `temperature` anyway, so self-consistency relies on the default sampling variation.
- **Terms of use:** automated bulk use of a consumer subscription must be checked against Anthropic's consumer terms before the M2 runs. If it isn't allowed, switch to the API backend.
