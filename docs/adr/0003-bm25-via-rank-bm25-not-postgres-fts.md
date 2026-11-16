# Dense vectors live in pgvector, but BM25 runs in-process with rank-bm25

Postgres full-text ranking (`ts_rank`) is not BM25: it has no IDF term and no length saturation. A baseline labelled "BM25" built on it would be mislabelled. Sparse retrieval therefore uses `rank-bm25` in-process.

Dense retrieval stays in Postgres with pgvector, even though a few tens of thousands of chunks would fit in numpy or FAISS. Learning pgvector is an explicit goal of this project.
