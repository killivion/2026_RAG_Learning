"""Experiment config: one complete choice of pipeline components (see GLOSSARY: Config)."""

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Config(BaseModel):
    """A validated config. Unknown keys and wrong types are rejected on load."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    parser: Literal["pymupdf", "pdfplumber"] = "pymupdf"
    chunker: Literal["fixed", "page", "structure"] = "fixed"
    retriever: Literal["bm25", "dense", "hybrid"] = "bm25"
    scope: Literal["shared", "filing"] = "shared"
    reranker: Literal["none", "cross-encoder"] = "none"
    k: int = Field(default=5, ge=1, le=50)
    prompt_version: str = "v1"
    generator_model: str = "claude-sonnet-5-5"
    judge_model: str = "claude-haiku-5-5"
    backend: Literal["claude-code", "fake"] = "claude-code"
    max_llm_calls: int = Field(default=500, ge=0)

    def config_hash(self) -> str:
        """Stable short hash of every field, used to identify and freeze configs."""
        canonical = json.dumps(self.model_dump(), sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def load_config(path: Path) -> Config:
    """Load and validate a YAML config file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Config.model_validate(raw)
