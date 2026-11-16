# 10: Dense retrieval with pgvector

**What to build:**
- Postgres with pgvector, started by one docker compose command.
- One small open embedding model, picked from a current leaderboard and pinned in config.
- Embeddings computed once per (chunking config, embedding model) and stored.
- A dense retriever behind the retriever interface, supporting both scopes.
- Dev runs report BM25 and dense side by side.

**Blocked by:** 01 (Docker engine running), 08

**Status:** ready-for-agent

- [ ] `docker compose up -d` gives a working pgvector; an index command embeds the dev filings once, and a rerun is a no-op
- [ ] A dense dev run writes the same metrics as the BM25 dev run
- [ ] The test suite still needs no Docker: the runner tests use an in-memory dense stand-in
- [ ] The embedding model id and the reason for choosing it go in the learning note for this milestone
