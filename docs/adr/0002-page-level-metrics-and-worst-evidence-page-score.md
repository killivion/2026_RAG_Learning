# Retrieval is scored on pages, and the conformal score is the worst-ranked evidence page

Chunks are what gets retrieved, but FinanceBench labels pages, and the chunking strategies being compared produce different numbers of chunks. So every chunk ranking is converted into a page ranking (each page takes its best chunk's score), and k counts distinct pages. This keeps recall@k comparable across chunkers.

35 of the 150 questions have two or three evidence pages:
- Recall@k and MRR count a hit when *any* evidence page is retrieved, and an "all evidence pages" recall is reported alongside.
- The conformal nonconformity score uses the rank of the *worst*-ranked evidence page, so the coverage guarantee means "the set contains all the evidence".
- The oracle condition receives all evidence pages.
