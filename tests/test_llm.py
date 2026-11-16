import json
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from finbench.cli import app
from finbench.llm import (
    CachedBackend,
    ClaudeCodeBackend,
    FakeBackend,
    LLMRequest,
    UsageLimitReached,
)

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "integer"}},
    "required": ["answer"],
    "additionalProperties": False,
}
REQUEST = LLMRequest(
    model="claude-haiku-5-5",
    system_prompt="You are a calculator.",
    user_prompt="What is 2+3?",
    schema=SCHEMA,
    prompt_version="v1",
)


def test_second_identical_call_is_served_from_cache(tmp_path: Path) -> None:
    fake = FakeBackend([{"answer": 5}])
    backend = CachedBackend(fake, tmp_path)

    first = backend.complete(REQUEST)
    second = backend.complete(REQUEST)

    assert first.output == {"answer": 5}
    assert not first.cached
    assert second.output == {"answer": 5}
    assert second.cached
    assert fake.calls == 1


def test_cache_survives_a_new_process(tmp_path: Path) -> None:
    CachedBackend(FakeBackend([{"answer": 5}]), tmp_path).complete(REQUEST)

    fresh = FakeBackend([])
    response = CachedBackend(fresh, tmp_path).complete(REQUEST)

    assert response.output == {"answer": 5}
    assert response.cached
    assert fresh.calls == 0


def test_prompt_version_change_misses_the_cache(tmp_path: Path) -> None:
    fake = FakeBackend([{"answer": 5}, {"answer": 6}])
    backend = CachedBackend(fake, tmp_path)

    backend.complete(REQUEST)
    bumped = backend.complete(replace(REQUEST, prompt_version="v2"))

    assert bumped.output == {"answer": 6}
    assert not bumped.cached
    assert fake.calls == 2


def test_usage_limit_stops_and_rerun_resumes_from_cache(tmp_path: Path) -> None:
    second_request = replace(REQUEST, user_prompt="What is 3+3?")
    interrupted = CachedBackend(FakeBackend([{"answer": 5}, UsageLimitReached("limit")]), tmp_path)
    interrupted.complete(REQUEST)
    with pytest.raises(UsageLimitReached):
        interrupted.complete(second_request)

    # The rerun repeats both calls; only the one that never finished reaches the backend.
    rerun_fake = FakeBackend([{"answer": 6}])
    rerun = CachedBackend(rerun_fake, tmp_path)
    assert rerun.complete(REQUEST).cached
    assert rerun.complete(second_request).output == {"answer": 6}
    assert rerun_fake.calls == 1


def test_llm_ping_command_prints_output_and_caches(tmp_path: Path) -> None:
    args = ["llm-ping", "--backend", "fake", "--cache-dir", str(tmp_path)]

    first = json.loads(CliRunner().invoke(app, args).stdout)
    second = json.loads(CliRunner().invoke(app, args).stdout)

    assert first["output"] == {"reply": "OK"}
    assert first["cached"] is False
    assert second["cached"] is True
    assert {"input_tokens", "output_tokens", "notional_cost_usd", "latency_s"} <= first.keys()


@pytest.mark.live
def test_claude_code_backend_makes_one_real_call() -> None:
    response = ClaudeCodeBackend().complete(REQUEST)

    assert response.output == {"answer": 5}
    assert response.input_tokens > 0
    assert response.output_tokens > 0
    assert response.notional_cost_usd > 0
