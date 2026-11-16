from finbench.chunking import Chunk, FixedSizeChunker
from finbench.retrieval import BM25Retriever, ScoredChunk, to_page_ranking


def words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{number}" for number in range(count))


def test_chunks_have_the_requested_size_and_overlap() -> None:
    chunks = FixedSizeChunker(size=4, overlap=1).chunk("F", [words("w", 10)])

    assert [chunk.text for chunk in chunks] == [
        "w0 w1 w2 w3",
        "w3 w4 w5 w6",
        "w6 w7 w8 w9",
    ]
    assert [chunk.id for chunk in chunks] == ["F:0", "F:1", "F:2"]


def test_chunk_carries_its_filing_and_page_span() -> None:
    pages = [words("a", 3), words("b", 3), words("c", 3)]

    chunks = FixedSizeChunker(size=4, overlap=0).chunk("ACME_2022_10K", pages)

    assert [(c.filing, c.first_page, c.last_page) for c in chunks] == [
        ("ACME_2022_10K", 0, 1),
        ("ACME_2022_10K", 1, 2),
        ("ACME_2022_10K", 2, 2),
    ]


def test_empty_pages_do_not_shift_page_numbers() -> None:
    chunks = FixedSizeChunker(size=10, overlap=0).chunk("F", ["", "", "only words here"])

    assert [(c.first_page, c.last_page) for c in chunks] == [(2, 2)]


CHUNKS = [
    Chunk("ACME:0", "ACME", 0, 0, "cover page of the annual report"),
    Chunk("ACME:1", "ACME", 1, 1, "revenue was 120 and costs were 80"),
    Chunk("ACME:2", "ACME", 2, 2, "the board met in spring"),
    Chunk("GLOBEX:0", "GLOBEX", 0, 0, "revenue revenue revenue grew strongly this quarter"),
    Chunk("GLOBEX:1", "GLOBEX", 1, 1, "cash and equivalents on the balance sheet"),
    Chunk("GLOBEX:2", "GLOBEX", 2, 2, "risk factors and legal proceedings"),
]


def test_shared_index_ranks_chunks_from_every_filing() -> None:
    ranking = BM25Retriever(CHUNKS).retrieve("What was revenue?", filing=None, depth=50)

    assert {scored.chunk.id for scored in ranking} == {"ACME:1", "GLOBEX:0"}
    assert ranking[0].score >= ranking[1].score


def test_filing_scoped_search_only_returns_chunks_of_that_filing() -> None:
    ranking = BM25Retriever(CHUNKS).retrieve("What was revenue?", filing="ACME", depth=50)

    assert [scored.chunk.id for scored in ranking] == ["ACME:1"]


def test_depth_limits_the_number_of_chunks() -> None:
    ranking = BM25Retriever(CHUNKS).retrieve("revenue", filing=None, depth=1)

    assert len(ranking) == 1


def test_page_with_several_chunks_is_counted_once_with_its_best_score() -> None:
    ranking = [
        ScoredChunk(Chunk("F:0", "F", 3, 3, ""), 9.0),
        ScoredChunk(Chunk("F:1", "F", 5, 5, ""), 7.0),
        ScoredChunk(Chunk("F:2", "F", 3, 3, ""), 4.0),
    ]

    assert to_page_ranking(ranking) == [(("F", 3), 9.0), (("F", 5), 7.0)]


def test_chunk_spanning_two_pages_ranks_both_pages() -> None:
    ranking = [
        ScoredChunk(Chunk("F:0", "F", 1, 2, ""), 5.0),
        ScoredChunk(Chunk("F:1", "F", 2, 2, ""), 8.0),
    ]

    assert to_page_ranking(ranking) == [(("F", 2), 8.0), (("F", 1), 5.0)]
