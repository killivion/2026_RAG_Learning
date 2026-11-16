import hashlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from finbench.cli import app
from finbench.dataset import (
    ChecksumMismatch,
    EvidencePage,
    Manifest,
    download,
    filing_path,
    load_questions,
    summarize,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "financebench"

UPSTREAM = {
    "data/financebench_open_source.jsonl": b'{"q": 1}\n',
    "results/gpt-4_oracle.jsonl": b'{"label": "Correct Answer"}\n',
    "pdfs/ACME_2022_10K.pdf": b"%PDF-fake",
}


def git_blob_sha1(content: bytes) -> str:
    return hashlib.sha1(b"blob %d\x00" % len(content) + content).hexdigest()


MANIFEST = Manifest(
    revision="abc123", files={path: git_blob_sha1(body) for path, body in UPSTREAM.items()}
)


class FakeUpstream:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.fetched: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.fetched.append(url)
        return next(body for path, body in self.files.items() if url.endswith(path))


def test_questions_load_as_typed_objects() -> None:
    questions = load_questions(FIXTURE_ROOT)

    assert [q.id for q in questions] == ["fixture_001", "fixture_002", "fixture_003"]
    second = questions[1]
    assert second.company == "Acme"
    assert second.filing == "ACME_2022_10K"
    assert second.question_type == "novel-generated"
    assert second.question == "Did Acme's margin improve in FY2022?"
    assert second.gold_answer == "Yes, from 30% to 33%."
    assert second.evidence_pages == (
        EvidencePage(page=3, text="Margin 33%", page_text="Income statement\nMargin 33%"),
        EvidencePage(page=7, text="Margin 30%", page_text="Prior year\nMargin 30%"),
    )


def test_summary_counts_questions_companies_filings_types_and_evidence() -> None:
    summary = summarize(load_questions(FIXTURE_ROOT))

    assert summary.questions == 3
    assert summary.companies == 2
    assert summary.filings == 2
    assert summary.question_types == {
        "domain-relevant": 1,
        "metrics-generated": 1,
        "novel-generated": 1,
    }
    assert summary.evidence_page_counts == {1: 2, 2: 1}


def test_data_summary_command_prints_the_counts() -> None:
    result = CliRunner().invoke(app, ["data-summary", "--root", str(FIXTURE_ROOT)])

    assert result.exit_code == 0, result.output
    assert "Questions: 3" in result.output
    assert "Companies: 2" in result.output
    assert "Filings: 2" in result.output


def test_download_puts_every_file_in_its_place(tmp_path: Path) -> None:
    report = download(tmp_path, MANIFEST, FakeUpstream(UPSTREAM))

    assert report.downloaded == 3
    assert report.skipped == 0
    assert (tmp_path / "data" / "financebench_open_source.jsonl").read_bytes() == b'{"q": 1}\n'
    assert (tmp_path / "data" / "results" / "gpt-4_oracle.jsonl").exists()
    assert filing_path(tmp_path, "ACME_2022_10K").read_bytes() == b"%PDF-fake"


def test_download_fetches_from_the_pinned_revision(tmp_path: Path) -> None:
    upstream = FakeUpstream(UPSTREAM)

    download(tmp_path, MANIFEST, upstream)

    assert all("/abc123/" in url for url in upstream.fetched)


def test_rerun_skips_files_whose_checksum_matches(tmp_path: Path) -> None:
    download(tmp_path, MANIFEST, FakeUpstream(UPSTREAM))
    upstream = FakeUpstream(UPSTREAM)

    report = download(tmp_path, MANIFEST, upstream)

    assert report.downloaded == 0
    assert report.skipped == 3
    assert upstream.fetched == []


def test_changed_upstream_file_fails_and_is_not_kept(tmp_path: Path) -> None:
    changed = UPSTREAM | {"pdfs/ACME_2022_10K.pdf": b"%PDF-changed"}

    with pytest.raises(ChecksumMismatch, match="ACME_2022_10K"):
        download(tmp_path, MANIFEST, FakeUpstream(changed))

    assert not filing_path(tmp_path, "ACME_2022_10K").exists()


def test_locally_modified_file_fails_loudly(tmp_path: Path) -> None:
    download(tmp_path, MANIFEST, FakeUpstream(UPSTREAM))
    filing_path(tmp_path, "ACME_2022_10K").write_bytes(b"corrupted")

    with pytest.raises(ChecksumMismatch, match="ACME_2022_10K"):
        download(tmp_path, MANIFEST, FakeUpstream(UPSTREAM))


def test_committed_manifest_lists_every_file_the_project_needs() -> None:
    paths = list(Manifest.committed().files)

    assert sum(p.startswith("pdfs/") for p in paths) == 84
    assert sum(p.startswith("results/") for p in paths) == 16
    assert "data/financebench_open_source.jsonl" in paths
    assert "data/financebench_document_information.jsonl" in paths
