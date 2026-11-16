import random
import shutil
from collections import Counter
from pathlib import Path

import pytest
from typer.testing import CliRunner

from finbench.cli import app
from finbench.dataset import (
    Question,
    Split,
    SplitExists,
    load_questions,
    load_split,
    make_split,
    write_split,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "financebench"
TYPES = ("domain-relevant", "metrics-generated", "novel-generated")


def synthetic_questions() -> list[Question]:
    """150 questions over 30 companies of uneven size, each with its own mix of types."""
    rng = random.Random(7)
    sizes = [rng.randint(1, 9) for _ in range(30)]
    sizes[0] += 150 - sum(sizes)
    questions = []
    for company_index, size in enumerate(sizes):
        for _ in range(size):
            questions.append(
                Question(
                    id=f"q{len(questions):03d}",
                    company=f"company{company_index:02d}",
                    filing=f"company{company_index:02d}_10K",
                    question_type=rng.choice(TYPES),
                    question="?",
                    gold_answer="!",
                    evidence_pages=(),
                )
            )
    return questions


def test_split_covers_every_question_once_with_about_a_third_in_dev() -> None:
    questions = synthetic_questions()

    assignment = make_split(questions)

    assert sorted(assignment.dev + assignment.test) == sorted(q.id for q in questions)
    assert 45 <= len(assignment.dev) <= 55


def test_no_company_appears_in_both_splits() -> None:
    questions = synthetic_questions()
    company = {q.id: q.company for q in questions}

    assignment = make_split(questions)

    dev_companies = {company[i] for i in assignment.dev}
    test_companies = {company[i] for i in assignment.test}
    assert dev_companies.isdisjoint(test_companies)


def test_question_type_shares_differ_by_at_most_five_points() -> None:
    questions = synthetic_questions()
    question_type = {q.id: q.question_type for q in questions}

    assignment = make_split(questions)

    dev = Counter(question_type[i] for i in assignment.dev)
    test = Counter(question_type[i] for i in assignment.test)
    for name in TYPES:
        dev_share = dev[name] / len(assignment.dev)
        test_share = test[name] / len(assignment.test)
        assert abs(dev_share - test_share) <= 0.05


def test_split_is_the_same_every_time() -> None:
    questions = synthetic_questions()

    assert make_split(questions) == make_split(questions)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A project root holding a copy of the fixture data and no split yet."""
    shutil.copytree(FIXTURE_ROOT, tmp_path, dirs_exist_ok=True)
    return tmp_path


def test_written_split_loads_back_as_questions(root: Path) -> None:
    assignment = write_split(root)

    dev = load_split(root, Split.DEV)
    test = load_split(root, Split.TEST)
    assert [q.id for q in dev] == list(assignment.dev)
    assert [q.id for q in test] == list(assignment.test)
    assert sorted(q.id for q in dev + test) == [q.id for q in load_questions(root)]


def test_existing_split_is_not_overwritten(root: Path) -> None:
    write_split(root)
    frozen = (root / "splits" / "financebench.json").read_text()

    with pytest.raises(SplitExists):
        write_split(root)

    assert (root / "splits" / "financebench.json").read_text() == frozen


def test_split_command_prints_both_sides_then_refuses_a_second_run(root: Path) -> None:
    args = ["split", "--root", str(root)]

    first = CliRunner().invoke(app, args)
    second = CliRunner().invoke(app, args)

    assert first.exit_code == 0, first.output
    assert "dev:" in first.output
    assert "test:" in first.output
    assert second.exit_code == 1
    assert "already exists" in second.output
