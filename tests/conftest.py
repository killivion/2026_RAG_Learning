import shutil
from pathlib import Path

import pymupdf
import pytest

from finbench.dataset import load_questions, write_split

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "financebench"


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """A complete made-up project: three questions, two eight-page filings and a split.

    Every page has exactly ten words, so a ten-word chunker makes one chunk per page. Evidence
    pages hold their evidence texts; the other pages are filler. The split puts the Globex
    question in dev and the two Acme questions in test.
    """
    root = tmp_path / "project"
    shutil.copytree(FIXTURE_ROOT, root)
    (root / "pdfs").mkdir()
    questions = load_questions(root)
    for filing in {q.filing for q in questions}:
        evidence_words: dict[int, list[str]] = {}
        for question in questions:
            if question.filing == filing:
                for evidence in question.evidence_pages:
                    evidence_words.setdefault(evidence.page, []).extend(evidence.page_text.split())
        texts = []
        for number in range(8):
            filler = f"Filler page {number} of the report says nothing in particular"
            page_words = evidence_words.get(number, filler.split())
            texts.append(" ".join(page_words + ["padding"] * (10 - len(page_words))))
        document = pymupdf.open()
        for text in texts:
            document.new_page().insert_text((72, 72), text)
        document.save(root / "pdfs" / f"{filing}.pdf")
    write_split(root)
    return root
