"""Parsing: filings into zero-indexed page texts, and a check that pages line up with evidence."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

import pymupdf
from rapidfuzz import fuzz

from finbench.dataset import Question, filing_path

MATCH_THRESHOLD = 90.0  # similarity (0-100) from which an evidence page counts as matched


class Parser(Protocol):
    name: str

    def parse(self, pdf: Path) -> list[str]:
        """The text of every page; index 0 is the first page."""
        ...


class PyMuPDFParser:
    name = "pymupdf"

    def parse(self, pdf: Path) -> list[str]:
        with pymupdf.open(pdf) as document:  # type: ignore[no-untyped-call]
            return [page.get_text() for page in document]


class ParserName(StrEnum):
    PYMUPDF = "pymupdf"

    def make(self) -> Parser:
        return {ParserName.PYMUPDF: PyMuPDFParser}[self]()


def parse_filing(parser: Parser, root: Path, filing: str) -> list[str]:
    """A filing's page texts, parsed once per (parser, filing) and then read from the cache."""
    cache_path = root / "cache" / "parsed" / parser.name / f"{filing}.json"
    if cache_path.exists():
        cached: list[str] = json.loads(cache_path.read_text(encoding="utf-8"))
        return cached
    pages = parser.parse(filing_path(root, filing))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # Write then rename, so an interrupted run never leaves a half-written entry.
    part = cache_path.with_name(cache_path.name + ".part")
    part.write_text(json.dumps(pages), encoding="utf-8")
    part.replace(cache_path)
    return pages


@dataclass(frozen=True)
class EvidenceAlignment:
    """How well one evidence page matches the parsed page with the same number (scores 0-100)."""

    question_id: str
    filing: str
    page: int
    text_score: float  # the evidence passage, found anywhere inside the parsed page
    page_score: float  # FinanceBench's full-page text against the parsed page
    neighbor_score: float  # the better full-page score of pages n-1 and n+1

    @property
    def matched(self) -> bool:
        return min(self.text_score, self.page_score) >= MATCH_THRESHOLD

    @property
    def zero_indexed(self) -> bool:
        """Page n beats both neighbours. A tie or a missing page counts as not confirmed."""
        return self.page_score > self.neighbor_score


@dataclass(frozen=True)
class AlignmentReport:
    rows: list[EvidenceAlignment]

    @property
    def match_rate(self) -> float:
        return sum(row.matched for row in self.rows) / len(self.rows)

    @property
    def zero_index_rate(self) -> float:
        """Share of evidence pages that match page n better than pages n-1 and n+1."""
        return sum(row.zero_indexed for row in self.rows) / len(self.rows)

    def worst(self, count: int) -> list[EvidenceAlignment]:
        return sorted(self.rows, key=lambda row: min(row.text_score, row.page_score))[:count]


def _normalize(text: str) -> str:
    # Parsers differ in line breaks and spacing; only the words should count.
    return " ".join(text.split())


def _page_score(page_text: str, parsed: list[str], index: int) -> float:
    """Similarity of a full-page text to parsed page `index`; 0 when there is no such page."""
    if not 0 <= index < len(parsed):
        return 0.0
    return fuzz.ratio(page_text, parsed[index])


def check_alignment(questions: list[Question], pages: Mapping[str, list[str]]) -> AlignmentReport:
    """Fuzzy-match every evidence page against the parsed pages of its filing."""
    rows = []
    for question in questions:
        parsed = [_normalize(page) for page in pages[question.filing]]
        for evidence in question.evidence_pages:
            page_text = _normalize(evidence.page_text)
            n = evidence.page
            text_score = (
                fuzz.partial_ratio(_normalize(evidence.text), parsed[n]) if n < len(parsed) else 0.0
            )
            rows.append(
                EvidenceAlignment(
                    question_id=question.id,
                    filing=question.filing,
                    page=n,
                    text_score=text_score,
                    page_score=_page_score(page_text, parsed, n),
                    neighbor_score=max(
                        _page_score(page_text, parsed, n - 1),
                        _page_score(page_text, parsed, n + 1),
                    ),
                )
            )
    return AlignmentReport(rows)
