"""LLM backend: structured-output calls behind one interface, with a disk cache (ADR-0005)."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class LLMRequest:
    """One single-turn call. Every field is part of the cache key."""

    model: str
    system_prompt: str
    user_prompt: str
    schema: JsonObject
    prompt_version: str

    def cache_key(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class LLMResponse:
    output: JsonObject
    input_tokens: int  # includes prompt-cache reads and writes
    output_tokens: int
    notional_cost_usd: float  # API list price; nothing is charged on the subscription
    latency_s: float  # of the original call, also when served from the cache
    cached: bool = False


class LLMBackendError(RuntimeError):
    """The backend failed for a reason other than the usage limit."""


class UsageLimitReached(LLMBackendError):
    """The subscription's usage limit is hit. Stop the run; a rerun resumes from the cache."""


class LLMBackend(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...


class FakeBackend:
    """Scripted backend for tests: returns the next output, or raises the next exception."""

    def __init__(self, script: list[JsonObject | Exception]) -> None:
        self._script = list(script)
        self.calls = 0

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return LLMResponse(
            output=step, input_tokens=0, output_tokens=0, notional_cost_usd=0.0, latency_s=0.0
        )


class CachedBackend:
    """Wraps any backend with a disk cache: one JSON file per request. Failures are not cached."""

    def __init__(self, inner: LLMBackend, cache_dir: Path) -> None:
        self._inner = inner
        self._cache_dir = cache_dir

    def complete(self, request: LLMRequest) -> LLMResponse:
        path = self._cache_dir / f"{request.cache_key()}.json"
        if path.exists():
            stored = json.loads(path.read_text(encoding="utf-8"))
            return replace(LLMResponse(**stored["response"]), cached=True)
        response = self._inner.complete(request)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        entry = {"request": asdict(request), "response": asdict(response)}
        # Write then rename, so an interrupted run never leaves a half-written entry.
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, indent=2), encoding="utf-8")
        tmp.replace(path)
        return response


# Wording of the CLI's usage-limit failure. Not yet seen on the real CLI: see ticket 03.
# HTTP 429 and "rate limit" count as the limit on purpose: stopping and resuming is safe.
_USAGE_LIMIT_MARKERS = ("usage limit", "session limit", "weekly limit", "rate limit")


class ClaudeCodeBackend:
    """Headless Claude Code on the subscription login: one turn, no tools, our system prompt."""

    def __init__(self, timeout_s: float = 300.0) -> None:
        self._timeout_s = timeout_s

    def complete(self, request: LLMRequest) -> LLMResponse:
        executable = shutil.which("claude")
        if executable is None:
            raise LLMBackendError("The `claude` command was not found on PATH")
        command = [
            executable,
            "--print",
            "--model",
            request.model,
            "--system-prompt",
            request.system_prompt,
            "--json-schema",
            json.dumps(request.schema),
            "--output-format",
            "json",
            "--tools",
            "",
            "--no-session-persistence",
            "--strict-mcp-config",
            "--disable-slash-commands",
            # No user or project settings: calls don't depend on local hooks, plugins or CLAUDE.md.
            "--setting-sources",
            "",
        ]
        start = time.perf_counter()
        # The user prompt goes through stdin: filing pages exceed the Windows command-line limit.
        # A neutral working directory keeps the project's CLAUDE.md out of the context.
        try:
            completed = subprocess.run(
                command,
                input=request.user_prompt,
                capture_output=True,
                encoding="utf-8",
                timeout=self._timeout_s,
                cwd=tempfile.gettempdir(),
            )
        except subprocess.TimeoutExpired as err:
            raise LLMBackendError(f"claude timed out after {self._timeout_s:.0f} s") from err
        latency_s = time.perf_counter() - start
        return _parse_result(completed.stdout, completed.stderr, latency_s)


def _parse_result(stdout: str, stderr: str, latency_s: float) -> LLMResponse:
    # The result object is the last line; the CLI may print diagnostics before it.
    lines = [line for line in stdout.splitlines() if line.startswith("{")]
    try:
        result: JsonObject = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError) as err:
        raise LLMBackendError(f"No JSON result from claude: {stdout[:500]} {stderr[:500]}") from err

    if result.get("is_error"):
        message = str(result.get("result", ""))
        if result.get("api_error_status") == 429 or any(
            marker in message.lower() for marker in _USAGE_LIMIT_MARKERS
        ):
            raise UsageLimitReached(message)
        raise LLMBackendError(f"claude failed ({result.get('subtype')}): {message}")

    output = result.get("structured_output")
    if not isinstance(output, dict):
        raise LLMBackendError(f"claude returned no structured output: {result.get('result')}")
    usage = result["usage"]
    return LLMResponse(
        output=output,
        input_tokens=usage["input_tokens"]
        + usage["cache_creation_input_tokens"]
        + usage["cache_read_input_tokens"],
        output_tokens=usage["output_tokens"],
        notional_cost_usd=result["total_cost_usd"],
        latency_s=latency_s,
    )
