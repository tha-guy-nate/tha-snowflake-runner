from pathlib import Path

import pytest

from tha_snowflake_runner.errors import SnowflakeError
from tha_snowflake_runner.profiles import list_profiles


def test_list_profiles_raises_when_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "connections.toml"
    with pytest.raises(SnowflakeError, match="connections_file not found"):
        list_profiles(str(missing))


def test_list_profiles_returns_names(tmp_path: Path) -> None:
    toml_path = tmp_path / "connections.toml"
    toml_path.write_text("[default]\naccount = 'dev'\n\n[prod]\naccount = 'prodorg'\n")
    assert list_profiles(str(toml_path)) == ["default", "prod"]


def test_list_profiles_expands_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    toml_path = tmp_path / "connections.toml"
    toml_path.write_text("[default]\naccount = 'dev'\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert list_profiles("~/connections.toml") == ["default"]


def test_load_all_profiles_skips_non_dict_toml_keys(tmp_path: Path) -> None:
    toml_path = tmp_path / "connections.toml"
    toml_path.write_text('title = "not a profile"\n\n[default]\naccount = "dev"\n')
    assert list_profiles(str(toml_path)) == ["default"]
