"""Dataset: FinanceBench download with checksums, and questions as typed objects."""

import hashlib
import json
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

_RAW_URL = "https://raw.githubusercontent.com/patronus-ai/financebench"
_QUESTIONS = "data/financebench_open_source.jsonl"

Fetch = Callable[[str], bytes]


@dataclass(frozen=True)
class EvidencePage:
    page: int  # zero-indexed page of the question's filing
    text: str  # the evidence passage the annotator marked
    page_text: str  # FinanceBench's own text of the whole page


@dataclass(frozen=True)
class Question:
    id: str
    company: str
    filing: str
    question_type: str
    question: str
    gold_answer: str
    evidence_pages: tuple[EvidencePage, ...]


@dataclass(frozen=True)
class DataSummary:
    questions: int
    companies: int
    filings: int
    question_types: dict[str, int]
    evidence_page_counts: dict[int, int]  # number of evidence pages -> number of questions


@dataclass(frozen=True)
class Manifest:
    """The upstream files this project uses, each with its git blob hash at a pinned commit."""

    revision: str
    files: dict[str, str]

    @classmethod
    def committed(cls) -> "Manifest":
        text = resources.files("finbench").joinpath("financebench_manifest.json").read_text("utf-8")
        return cls(**json.loads(text))


@dataclass(frozen=True)
class DownloadReport:
    downloaded: int
    skipped: int


class ChecksumMismatch(RuntimeError):
    """A file's content differs from the committed checksum."""


def _git_blob_sha1(content: bytes) -> str:
    # Git's own object hash, so the checksums come straight from the pinned upstream commit.
    return hashlib.sha1(b"blob %d\x00" % len(content) + content).hexdigest()


def _local_path(root: Path, upstream_path: str) -> Path:
    # Upstream `results/` goes under the git-ignored `data/`; `data/` and `pdfs/` keep their place.
    if upstream_path.startswith("results/"):
        return root / "data" / upstream_path
    return root / upstream_path


def fetch_url(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        content: bytes = response.read()
    return content


def download(
    root: Path,
    manifest: Manifest,
    fetch: Fetch = fetch_url,
    on_fetch: Callable[[str], None] = lambda path: None,
) -> DownloadReport:
    """Fetch every manifest file that is missing. A file that fails its checksum raises."""
    downloaded = skipped = 0
    for upstream_path, expected in manifest.files.items():
        target = _local_path(root, upstream_path)
        if target.exists():
            if _git_blob_sha1(target.read_bytes()) != expected:
                raise ChecksumMismatch(f"{target} does not match its checksum; delete it and rerun")
            skipped += 1
            continue
        on_fetch(upstream_path)
        content = fetch(f"{_RAW_URL}/{manifest.revision}/{upstream_path}")
        if _git_blob_sha1(content) != expected:
            raise ChecksumMismatch(f"Upstream {upstream_path} does not match its checksum")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename, so an interrupted run never leaves a truncated file behind.
        part = target.with_name(target.name + ".part")
        part.write_bytes(content)
        part.replace(target)
        downloaded += 1
    return DownloadReport(downloaded=downloaded, skipped=skipped)


def filing_path(root: Path, filing: str) -> Path:
    return root / "pdfs" / f"{filing}.pdf"


def load_questions(root: Path) -> list[Question]:
    """All questions, in file order."""
    # Split on newlines only: page texts may hold other line-break characters.
    lines = (root / _QUESTIONS).read_text(encoding="utf-8").split("\n")
    return [_to_question(json.loads(line)) for line in lines if line]


def _to_question(raw: dict[str, Any]) -> Question:
    return Question(
        id=raw["financebench_id"],
        company=raw["company"],
        filing=raw["doc_name"],
        question_type=raw["question_type"],
        question=raw["question"],
        gold_answer=raw["answer"],
        evidence_pages=tuple(
            EvidencePage(
                page=item["evidence_page_num"],
                text=item["evidence_text"],
                page_text=item["evidence_text_full_page"],
            )
            for item in raw["evidence"]
        ),
    )


def summarize(questions: list[Question]) -> DataSummary:
    return DataSummary(
        questions=len(questions),
        companies=len({q.company for q in questions}),
        filings=len({q.filing for q in questions}),
        question_types=dict(sorted(Counter(q.question_type for q in questions).items())),
        evidence_page_counts=dict(
            sorted(Counter(len(q.evidence_pages) for q in questions).items())
        ),
    )
