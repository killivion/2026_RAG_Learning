"""Parsing: filings into zero-indexed page texts, and a check that pages line up with evidence."""

import csv
import json
import re
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from pathlib import Path
from statistics import mean
from typing import Protocol

import pdfplumber
import pymupdf
from rapidfuzz import fuzz

from finbench.dataset import Question, filing_path, load_questions

MATCH_THRESHOLD = 90.0  # similarity (0-100) from which an evidence page counts as matched
TABLE_NUMBER_SHARE = 0.2  # share of numeric tokens from which a page counts as a table page
_NUMBER = re.compile(r"[($]*\d[\d,.]*[)%]*")
_COMPARISON_FILE = "results/parser_comparison.csv"


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


class PdfplumberParser:
    name = "pdfplumber"

    def parse(self, pdf: Path) -> list[str]:
        with pdfplumber.open(pdf) as document:
            return [page.extract_text() for page in document.pages]


class ParserName(StrEnum):
    PYMUPDF = "pymupdf"
    PDFPLUMBER = "pdfplumber"

    def make(self) -> Parser:
        parsers: dict[ParserName, type[Parser]] = {
            ParserName.PYMUPDF: PyMuPDFParser,
            ParserName.PDFPLUMBER: PdfplumberParser,
        }
        return parsers[self]()


@dataclass(frozen=True)
class ParsedFiling:
    pages: list[str]
    parse_seconds: float  # of the original parse, also when read from the cache


def parse_filing(parser: Parser, root: Path, filing: str) -> ParsedFiling:
    """A filing's page texts, parsed once per (parser, filing) and then read from the cache."""
    cache_path = root / "cache" / "parsed" / parser.name / f"{filing}.json"
    if cache_path.exists():
        return ParsedFiling(**json.loads(cache_path.read_text(encoding="utf-8")))
    start = time.perf_counter()
    pages = parser.parse(filing_path(root, filing))
    parsed = ParsedFiling(pages=pages, parse_seconds=time.perf_counter() - start)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # Write then rename, so an interrupted run never leaves a half-written entry.
    part = cache_path.with_name(cache_path.name + ".part")
    part.write_text(json.dumps(asdict(parsed)), encoding="utf-8")
    part.replace(cache_path)
    return parsed


@dataclass(frozen=True)
class EvidenceAlignment:
    """How well one evidence page matches the parsed page with the same number (scores 0-100)."""

    question_id: str
    filing: str
    page: int
    text_score: float  # the evidence passage, found anywhere inside the parsed page
    page_score: float  # FinanceBench's full-page text against the parsed page
    neighbor_score: float  # the better full-page score of pages n-1 and n+1
    is_table_page: bool  # judged on FinanceBench's page text, so it is the same for every parser

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
    def mean_page_score(self) -> float:
        return mean(row.page_score for row in self.rows)

    @property
    def zero_index_rate(self) -> float:
        """Share of evidence pages that match page n better than pages n-1 and n+1."""
        return sum(row.zero_indexed for row in self.rows) / len(self.rows)

    def worst(self, count: int) -> list[EvidenceAlignment]:
        return sorted(self.rows, key=lambda row: min(row.text_score, row.page_score))[:count]

    def table_pages(self) -> "AlignmentReport":
        return AlignmentReport([row for row in self.rows if row.is_table_page])


def _normalize(text: str) -> str:
    # Parsers differ in line breaks and spacing; only the words should count.
    return " ".join(text.split())


def _is_table_page(text: str) -> bool:
    """A page counts as a table page when a fifth or more of its tokens are numbers."""
    tokens = text.split()
    numbers = sum(_NUMBER.fullmatch(token) is not None for token in tokens)
    return bool(tokens) and numbers / len(tokens) >= TABLE_NUMBER_SHARE


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
                    is_table_page=_is_table_page(page_text),
                )
            )
    return AlignmentReport(rows)


@dataclass(frozen=True)
class ParserComparison:
    """One parser's row in the comparison table. Scores are 0-100, rates 0-1."""

    parser: str
    filings: int
    pages: int
    parse_seconds: float
    evidence_pages: int
    match_rate: float
    mean_page_score: float
    zero_index_rate: float
    table_pages: int
    table_match_rate: float
    table_mean_page_score: float


def compare_parsers(root: Path) -> list[ParserComparison]:
    """Parse every filing with every parser and score each against the evidence pages."""
    questions = load_questions(root)
    comparisons = []
    for name in ParserName:
        parser = name.make()
        parsed = {
            filing: parse_filing(parser, root, filing)
            for filing in sorted({q.filing for q in questions})
        }
        report = check_alignment(questions, {f: p.pages for f, p in parsed.items()})
        tables = report.table_pages()
        comparisons.append(
            ParserComparison(
                parser=name,
                filings=len(parsed),
                pages=sum(len(p.pages) for p in parsed.values()),
                parse_seconds=round(sum(p.parse_seconds for p in parsed.values()), 1),
                evidence_pages=len(report.rows),
                match_rate=round(report.match_rate, 4),
                mean_page_score=round(report.mean_page_score, 2),
                zero_index_rate=round(report.zero_index_rate, 4),
                table_pages=len(tables.rows),
                table_match_rate=round(tables.match_rate, 4),
                table_mean_page_score=round(tables.mean_page_score, 2),
            )
        )
    return comparisons


def write_parser_comparison(root: Path) -> Path:
    """Write the comparison table as a results file; it holds numbers only, no filing text."""
    path = root / _COMPARISON_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, [field.name for field in fields(ParserComparison)])
        writer.writeheader()
        writer.writerows(asdict(row) for row in compare_parsers(root))
    return path
