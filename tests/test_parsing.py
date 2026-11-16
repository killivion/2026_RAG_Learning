from pathlib import Path

import pymupdf
import pytest

from finbench.dataset import EvidencePage, Question, load_questions
from finbench.parsing import ParserName, PyMuPDFParser, check_alignment, parse_filing

PAGE_TEXTS = [
    "Cover page of the Acme annual report",
    "Income statement: revenue 120, costs 80, profit 40",
    "Balance sheet: cash 15, total assets 500",
]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A project root with one generated three-page filing."""
    (tmp_path / "pdfs").mkdir()
    document = pymupdf.open()
    for text in PAGE_TEXTS:
        document.new_page().insert_text((72, 72), text)
    document.save(tmp_path / "pdfs" / "ACME_2022_10K.pdf")
    return tmp_path


def question(page: int, page_text: str) -> Question:
    return Question(
        id="q1",
        company="Acme",
        filing="ACME_2022_10K",
        question_type="metrics-generated",
        question="?",
        gold_answer="!",
        evidence_pages=(EvidencePage(page=page, text=page_text, page_text=page_text),),
    )


def test_pages_are_zero_indexed(root: Path) -> None:
    pages = parse_filing(PyMuPDFParser(), root, "ACME_2022_10K")

    assert len(pages) == 3
    assert "Cover page" in pages[0]
    assert "Balance sheet" in pages[2]


def test_second_parse_is_served_from_the_cache(root: Path) -> None:
    first = parse_filing(PyMuPDFParser(), root, "ACME_2022_10K")
    (root / "pdfs" / "ACME_2022_10K.pdf").unlink()

    second = parse_filing(PyMuPDFParser(), root, "ACME_2022_10K")

    assert second == first


def test_alignment_matches_evidence_on_its_own_page() -> None:
    report = check_alignment([question(1, PAGE_TEXTS[1])], {"ACME_2022_10K": PAGE_TEXTS})

    assert report.match_rate == 1.0
    assert report.zero_index_rate == 1.0


def test_alignment_exposes_an_off_by_one_page_number() -> None:
    one_indexed = question(2, PAGE_TEXTS[1])

    report = check_alignment([one_indexed], {"ACME_2022_10K": PAGE_TEXTS})

    assert report.match_rate == 0.0
    assert report.zero_index_rate == 0.0
    assert report.worst(1)[0].question_id == "q1"


def test_alignment_ignores_whitespace_differences() -> None:
    reflowed = PAGE_TEXTS[1].replace(" ", "\n  ")

    report = check_alignment([question(1, reflowed)], {"ACME_2022_10K": PAGE_TEXTS})

    assert report.match_rate == 1.0


def test_evidence_page_beyond_the_filing_counts_as_a_miss() -> None:
    report = check_alignment([question(9, PAGE_TEXTS[1])], {"ACME_2022_10K": PAGE_TEXTS})

    assert report.match_rate == 0.0


@pytest.mark.data
def test_pymupdf_pages_line_up_with_financebench_evidence_pages() -> None:
    root = Path(__file__).parents[1]
    questions = load_questions(root)
    parser = ParserName.PYMUPDF.make()
    pages = {filing: parse_filing(parser, root, filing) for filing in {q.filing for q in questions}}

    report = check_alignment(questions, pages)

    assert len(report.rows) == 189
    assert report.zero_index_rate >= 0.95
    assert report.match_rate >= 0.95
