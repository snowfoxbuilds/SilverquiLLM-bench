"""Host configuration: flag, else environment, else ``config.toml`` for every Karn location."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import CliRunner

from silverquillm import host_config as hc
from silverquillm.cli import main


@pytest.fixture
def config_file():
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "silverquillm" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    yield path
    path.unlink(missing_ok=True)


def test_the_file_lives_under_an_absolute_xdg_config_home_else_the_home_config():
    assert hc.config_path({"XDG_CONFIG_HOME": "/xdg"}) == Path("/xdg/silverquillm/config.toml")
    assert hc.config_path({"XDG_CONFIG_HOME": "relative"}) == (
        Path.home() / ".config/silverquillm/config.toml"
    )
    assert hc.config_path({}) == Path.home() / ".config/silverquillm/config.toml"


def test_a_missing_file_gives_the_defaults(tmp_path):
    config = hc.load_host_config(tmp_path / "absent.toml")
    assert not config.loaded
    assert config.locations == {}
    assert config.usage_rates == {"codex": Decimal(5), "claude": Decimal(25)}
    assert config.theme is None


def test_locations_expand_home_and_resolve_relative_to_the_file(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        'results_repo = "~/bench-results"\nbatches_dir = "queue"\nruns_dir = "/abs/runs"\n'
        '[usage_rates]\nclaude = 30\n[monitor]\ntheme = "plain"\n'
    )
    config = hc.load_host_config(path)
    assert config.locations == {
        "results_repo": Path.home() / "bench-results",
        "batches_dir": tmp_path / "queue",
        "runs_dir": Path("/abs/runs"),
    }
    assert config.usage_rates == {"codex": Decimal(5), "claude": Decimal(30)}
    assert config.theme == "plain"


@pytest.mark.parametrize(
    "text, message",
    [
        ('result_repo = "/x"\n', "unknown key(s) result_repo"),
        ("results_repo = 3\n", "results_repo must be a non-empty path string"),
        ('results_repo = " "\n', "results_repo must be a non-empty path string"),
        ("[usage_rates]\ncodex = 0\n", "usage_rates.codex must be positive"),
        ("[usage_rates]\ncodex = true\n", "usage_rates.codex must be a number"),
        ('[usage_rates]\ncodex = "5"\n', "usage_rates.codex must be a number"),
        ("[usage_rates]\ncodex = nan\n", "usage_rates.codex must be positive"),
        ("usage_rates = 5\n", "usage_rates must be a table"),
        ('[monitor]\ncolour = "x"\n', "unknown key(s) monitor.colour"),
        ("[monitor]\ntheme = 1\n", "monitor.theme must be a non-empty string"),
        ("results_repo = \n", "config.toml:"),
    ],
)
def test_a_malformed_file_is_refused_with_its_path(tmp_path, text, message):
    path = tmp_path / "config.toml"
    path.write_text(text)
    with pytest.raises(hc.HostConfigError, match="config.toml") as error:
        hc.load_host_config(path)
    assert message in str(error.value)


def test_a_flag_beats_the_environment_which_beats_the_file(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('results_repo = "/from/config"\n')
    config = hc.load_host_config(path)
    env = {"SILVERQUILLM_RESULTS_REPO": "/from/env"}

    def resolved(given, environ):
        location = hc.resolve_location("results_repo", given, environ=environ, config=config)
        return location.path, location.source

    assert resolved("/from/flag", env) == (Path("/from/flag"), "flag")
    assert resolved(None, env) == (Path("/from/env"), "env")
    assert resolved(None, {"SILVERQUILLM_RESULTS_REPO": "  "}) == (Path("/from/config"), "config")
    assert resolved(None, {}) == (Path("/from/config"), "config")


def test_unset_locations_are_reported_and_only_the_state_root_has_a_default(tmp_path):
    config = hc.load_host_config(tmp_path / "absent.toml")
    locations = hc.resolve_locations(environ={}, config=config)
    assert {key: location.source for key, location in locations.items()} == {
        "results_repo": "unset",
        "batches_dir": "unset",
        "runs_dir": "unset",
        "state_root": "default",
    }
    assert locations["state_root"].path == Path.home() / ".local/state/silverquillm"
    with pytest.raises(hc.HostConfigError) as error:
        hc.require(locations["results_repo"], Path("/c/config.toml"))
    assert str(error.value) == (
        "no results repo: pass --results-repo, set SILVERQUILLM_RESULTS_REPO, "
        "or set results_repo in /c/config.toml"
    )
    assert hc.missing_location_message("runs_dir", Path("/c.toml")) == (
        "no run directory: pass --results-dir, or set runs_dir in /c.toml"
    )


def test_commands_take_an_unflagged_location_from_the_file(tmp_path, config_file, monkeypatch):
    (tmp_path / "queue").mkdir()
    config_file.write_text(f'batches_dir = "{tmp_path / "queue"}"\n')
    monkeypatch.chdir(tmp_path.parent)
    result = CliRunner().invoke(main, ["queue", "ls"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "no batches"


def test_a_command_refuses_an_unset_location_instead_of_using_the_working_directory(
    tmp_path, config_file, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "batches").mkdir()
    result = CliRunner().invoke(main, ["queue", "ls"])
    assert result.exit_code == 2
    assert f"no batch queue directory: pass --batches-dir, or set batches_dir in {config_file}" in (
        result.output
    )


def test_the_environment_still_sets_the_results_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("SILVERQUILLM_RESULTS_REPO", str(tmp_path / "results"))
    result = CliRunner().invoke(main, ["results", "exclusions"])
    assert "no results repo" not in result.output


def test_a_malformed_file_does_not_block_a_fully_flagged_command(tmp_path, config_file):
    config_file.write_text("not toml [")
    (tmp_path / "queue").mkdir()
    result = CliRunner().invoke(main, ["queue", "ls", "--batches-dir", str(tmp_path / "queue")])
    assert result.exit_code == 0, result.output
    config_file.write_text("not toml [")
    result = CliRunner().invoke(main, ["queue", "ls"])
    assert result.exit_code == 2
    assert str(config_file) in result.output
