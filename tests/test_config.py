import pytest
from pydantic import ValidationError

from finbench.config import Config


def test_config_hash_is_stable_and_changes_with_the_config() -> None:
    a = Config(name="a")
    assert a.config_hash() == Config(name="a").config_hash()
    assert a.config_hash() != Config(name="a", k=6).config_hash()


@pytest.mark.parametrize(
    "fields",
    [{"name": "x", "extra": 1}, {"name": "x", "k": 0}, {"name": ""}, {"name": "x", "scope": "all"}],
)
def test_config_rejects_unknown_keys_and_invalid_values(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Config.model_validate(fields)
