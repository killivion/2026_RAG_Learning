import csv
import shutil
from pathlib import Path

import pymupdf
import pytest
from typer.testing import CliRunner

from finbench.cli import app
from finbench.dataset import EvidencePage, Question, load_questions
from finbench.parsing import ParserName, check_alignment, parse_filing

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "financebench"
PAGE_TEXTS = [
    "Cover page of the Acme annual report",
    "Income statement: revenue 120, costs 80, profit 40",
    "Balance sheet: cash 15, total assets 500",
]
TABLE_PAGE = "Revenue 120 130 Costs 80 85 Profit 40 45"


def write_pdf(path: Path, page_texts: list[str]) -> None:
    document = pymupdf.open()
    for text in page_texts:
        document.new_page().insert_text((72, 72), text)
    document.save(path)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A project root with one generated three-page filing."""
    (tmp_path / "pdfs").mkdir()
    write_pdf(tmp_path / "pdfs" / "ACME_2022_10K.pdf", PAGE_TEXTS)
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


@pytest.mark.parametrize("parser", list(ParserName))
def test_pages_are_zero_indexed(root: Path, parser: ParserName) -> None:
    pages = parse_filing(parser.make(), root, "ACME_2022_10K").pages

    assert len(pages) == 3
    assert "Cover page" in pages[0]
    assert "Balance sheet" in pages[2]


@pytest.mark.parametrize("parser", list(ParserName))
def test_second_parse_is_served_from_the_cache(root: Path, parser: ParserName) -> None:
    first = parse_filing(parser.make(), root, "ACME_2022_10K")
    (root / "pdfs" / "ACME_2022_10K.pdf").unlink()

    second = parse_filing(parser.make(), root, "ACME_2022_10K")

    assert second == first


def test_each_parser_has_its_own_cache(root: Path) -> None:
    parse_filing(ParserName.PYMUPDF.make(), root, "ACME_2022_10K")
    (root / "pdfs" / "ACME_2022_10K.pdf").unlink()

    with pytest.raises(FileNotFoundError):
        parse_filing(ParserName.PDFPLUMBER.make(), root, "ACME_2022_10K")


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


def test_table_pages_are_the_number_heavy_evidence_pages() -> None:
    pages = {"ACME_2022_10K": [PAGE_TEXTS[0], TABLE_PAGE]}
    prose, table = question(0, PAGE_TEXTS[0]), question(1, TABLE_PAGE)

    report = check_alignment([prose, table], pages)

    assert [row.page for row in report.table_pages().rows] == [1]


def test_parse_compare_writes_one_row_per_parser(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE_ROOT, tmp_path, dirs_exist_ok=True)
    (tmp_path / "pdfs").mkdir()
    for question in load_questions(tmp_path):
        # Each filing gets eight pages, with the evidence page texts on their own pages.
        texts = [f"Filler page {number}" for number in range(8)]
        for same_filing in load_questions(tmp_path):
            if same_filing.filing == question.filing:
                for evidence in same_filing.evidence_pages:
                    texts[evidence.page] = evidence.page_text.replace("\n", " ")
        write_pdf(tmp_path / "pdfs" / f"{question.filing}.pdf", texts)

    result = CliRunner().invoke(app, ["parse-compare", "--root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    with (tmp_path / "results" / "parser_comparison.csv").open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert [row["parser"] for row in rows] == ["pymupdf", "pdfplumber"]
    assert [row["filings"] for row in rows] == ["2", "2"]
    assert [row["evidence_pages"] for row in rows] == ["4", "4"]
    assert [row["zero_index_rate"] for row in rows] == ["1.0", "1.0"]


@pytest.mark.data
def test_pymupdf_pages_line_up_with_financebench_evidence_pages() -> None:
    root = Path(__file__).parents[1]
    questions = load_questions(root)
    parser = ParserName.PYMUPDF.make()
    pages = {
        filing: parse_filing(parser, root, filing).pages for filing in {q.filing for q in questions}
    }

    report = check_alignment(questions, pages)

    assert len(report.rows) == 189
    assert report.zero_index_rate >= 0.95
    assert report.match_rate >= 0.95
