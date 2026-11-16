"""Dataset: FinanceBench download with checksums, and questions as typed objects."""

import hashlib
import json
import random
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any

_RAW_URL = "https://raw.githubusercontent.com/patronus-ai/financebench"
_QUESTIONS = "data/financebench_open_source.jsonl"
_SPLIT_FILE = "splits/financebench.json"
SPLIT_SEED = 0

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


class Split(StrEnum):
    DEV = "dev"
    TEST = "test"


@dataclass(frozen=True)
class SplitAssignment:
    """Question ids of each split, in question-file order."""

    dev: tuple[str, ...]
    test: tuple[str, ...]


class SplitExists(RuntimeError):
    """The split is frozen: a split file already exists."""


def _imbalance(dev: list[Question], test: list[Question]) -> float:
    """Largest gap between the two splits in any question type's share."""
    dev_types = Counter(q.question_type for q in dev)
    test_types = Counter(q.question_type for q in test)
    return max(
        abs(dev_types[name] / len(dev) - test_types[name] / len(test))
        for name in dev_types.keys() | test_types.keys()
    )


def make_split(
    questions: list[Question], seed: int = SPLIT_SEED, dev_share: float = 1 / 3, trials: int = 2000
) -> SplitAssignment:
    """Split by company (ADR-0001), with dev near `dev_share` and question types balanced.

    Random search: shuffle the companies many times, give dev the first companies that fill
    its share, and keep the shuffle whose splits are closest to the size target and type mix.
    """
    rng = random.Random(seed)
    companies = sorted({q.company for q in questions})
    size = Counter(q.company for q in questions)
    dev_target = dev_share * len(questions)

    best_score = float("inf")
    best_dev: set[str] = set()
    for _ in range(trials):
        rng.shuffle(companies)
        dev_companies: set[str] = set()
        dev_size = 0
        for company in companies[:-1]:  # test keeps at least one company
            # Stop before a company that would move dev further from its target.
            if dev_companies and abs(dev_size + size[company] - dev_target) > abs(
                dev_size - dev_target
            ):
                break
            dev_companies.add(company)
            dev_size += size[company]
        dev = [q for q in questions if q.company in dev_companies]
        test = [q for q in questions if q.company not in dev_companies]
        score = _imbalance(dev, test) + abs(dev_size - dev_target) / len(questions)
        if score < best_score:
            best_score, best_dev = score, dev_companies

    return SplitAssignment(
        dev=tuple(q.id for q in questions if q.company in best_dev),
        test=tuple(q.id for q in questions if q.company not in best_dev),
    )


def write_split(root: Path, force: bool = False) -> SplitAssignment:
    """Make the split once and write it. Refuses to overwrite: the split is frozen (ADR-0001)."""
    path = root / _SPLIT_FILE
    if path.exists() and not force:
        raise SplitExists(f"{path} already exists")
    assignment = make_split(load_questions(root))
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps({"seed": SPLIT_SEED, **asdict(assignment)}, indent=2) + "\n"
    path.write_text(content, encoding="utf-8")
    return assignment


def load_split(root: Path, split: Split) -> list[Question]:
    """The questions of one split, in question-file order."""
    ids = set(json.loads((root / _SPLIT_FILE).read_text(encoding="utf-8"))[split])
    return [q for q in load_questions(root) if q.id in ids]
