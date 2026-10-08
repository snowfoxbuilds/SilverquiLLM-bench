"""Host-local configuration: where this host keeps its Karn locations, plus monitor settings.

Every Karn command resolves each location as its flag, else its environment variable,
else the configuration file (KARN-BENCHMARK-CONTRACT.md, Operator entrypoints); only the
state root has a built-in default. The file also carries the monitor's settings
(RUN-MONITORING.md, Locations and host configuration).
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

import click


class HostConfigError(ValueError):
    """The configuration file is unreadable or malformed, or a required location is unset."""


@dataclass(frozen=True)
class LocationSpec:
    key: str
    label: str
    flag: str
    env: str | None = None
    default: Callable[[], Path] | None = None


LOCATIONS: dict[str, LocationSpec] = {
    spec.key: spec
    for spec in (
        LocationSpec("results_repo", "results repo", "--results-repo", "SILVERQUILLM_RESULTS_REPO"),
        LocationSpec("batches_dir", "batch queue directory", "--batches-dir"),
        LocationSpec("runs_dir", "run directory", "--results-dir"),
        LocationSpec(
            "state_root",
            "state root",
            "--state-root",
            default=lambda: Path.home() / ".local/state/silverquillm",
        ),
    )
}

DEFAULT_USAGE_RATES: dict[str, Decimal] = {"codex": Decimal(5), "claude": Decimal(25)}


@dataclass(frozen=True)
class HostConfig:
    path: Path
    loaded: bool
    locations: Mapping[str, Path] = field(default_factory=dict)
    usage_rates: Mapping[str, Decimal] = field(default_factory=lambda: dict(DEFAULT_USAGE_RATES))
    """Estimated Cost in USD that counts as 1% of a provider's weekly allowance."""
    theme: str | None = None


@dataclass(frozen=True)
class ResolvedLocation:
    key: str
    path: Path | None
    source: str
    """``flag``, ``env``, ``config``, ``default``, or ``unset`` (``path`` is None)."""


def config_path(environ: Mapping[str, str] | None = None) -> Path:
    environ = os.environ if environ is None else environ
    xdg = environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".config"
    return base / "silverquillm" / "config.toml"


def load_host_config(
    path: Path | None = None, environ: Mapping[str, str] | None = None
) -> HostConfig:
    """Read the configuration file; a missing file yields the defaults."""
    path = config_path(environ) if path is None else path
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except FileNotFoundError:
        return HostConfig(path=path, loaded=False)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HostConfigError(f"{path}: {error}") from None
    unknown = sorted(set(document) - set(LOCATIONS) - {"usage_rates", "monitor"})
    if unknown:
        raise HostConfigError(f"{path}: unknown key(s) {', '.join(unknown)}")
    locations = {}
    for key in LOCATIONS:
        if key in document:
            value = document[key]
            if not isinstance(value, str) or not value.strip():
                raise HostConfigError(f"{path}: {key} must be a non-empty path string")
            location = Path(value).expanduser()
            # A relative path is relative to the file, never to whichever directory a command runs in.
            locations[key] = location if location.is_absolute() else path.parent / location
    return HostConfig(
        path=path,
        loaded=True,
        locations=locations,
        usage_rates=_usage_rates(path, document.get("usage_rates", {})),
        theme=_theme(path, document.get("monitor", {})),
    )


def _usage_rates(path: Path, table: object) -> dict[str, Decimal]:
    if not isinstance(table, dict):
        raise HostConfigError(f"{path}: usage_rates must be a table")
    rates = dict(DEFAULT_USAGE_RATES)
    for provider, value in table.items():
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise HostConfigError(f"{path}: usage_rates.{provider} must be a number")
        try:
            rate = Decimal(str(value))
        except InvalidOperation:
            raise HostConfigError(f"{path}: usage_rates.{provider} must be a number") from None
        if not rate.is_finite() or rate <= 0:
            raise HostConfigError(f"{path}: usage_rates.{provider} must be positive")
        rates[provider] = rate
    return rates


def _theme(path: Path, table: object) -> str | None:
    if not isinstance(table, dict):
        raise HostConfigError(f"{path}: monitor must be a table")
    unknown = sorted(set(table) - {"theme"})
    if unknown:
        raise HostConfigError(f"{path}: unknown key(s) monitor.{', monitor.'.join(unknown)}")
    theme = table.get("theme")
    if theme is not None and (not isinstance(theme, str) or not theme.strip()):
        raise HostConfigError(f"{path}: monitor.theme must be a non-empty string")
    return theme


def resolve_location(
    key: str,
    given: Path | str | None = None,
    given_source: str = "flag",
    *,
    environ: Mapping[str, str] | None = None,
    config: HostConfig | None = None,
) -> ResolvedLocation:
    """Resolve one location; ``given`` is a value the caller already holds from a flag or env."""
    spec = LOCATIONS[key]
    if given is not None and str(given).strip():
        return ResolvedLocation(key, Path(given).expanduser(), given_source)
    environ = os.environ if environ is None else environ
    if spec.env and environ.get(spec.env, "").strip():
        return ResolvedLocation(key, Path(environ[spec.env].strip()).expanduser(), "env")
    config = load_host_config(environ=environ) if config is None else config
    if key in config.locations:
        return ResolvedLocation(key, config.locations[key], "config")
    if spec.default is not None:
        return ResolvedLocation(key, spec.default(), "default")
    return ResolvedLocation(key, None, "unset")


def resolve_locations(
    given: Mapping[str, Path | str | None] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    config: HostConfig | None = None,
) -> dict[str, ResolvedLocation]:
    """Every location with its source; an unset one is reported, not raised."""
    config = load_host_config(environ=environ) if config is None else config
    given = given or {}
    return {
        key: resolve_location(key, given.get(key), environ=environ, config=config)
        for key in LOCATIONS
    }


def missing_location_message(key: str, config_file: Path | None = None) -> str:
    spec = LOCATIONS[key]
    config_file = config_path() if config_file is None else config_file
    sources = [f"pass {spec.flag}"]
    if spec.env:
        sources.append(f"set {spec.env}")
    sources.append(f"set {key} in {config_file}")
    return f"no {spec.label}: " + ", ".join(sources[:-1]) + ", or " + sources[-1]


def require(location: ResolvedLocation, config_file: Path | None = None) -> Path:
    if location.path is None:
        raise HostConfigError(missing_location_message(location.key, config_file))
    return location.path


def location_option(key: str, **attrs) -> Callable:
    """A click option for one location that falls back to the configuration file."""
    spec = LOCATIONS[key]

    def callback(ctx: click.Context, param: click.Parameter, value: Path | None) -> Path:
        source = ctx.get_parameter_source(param.name)
        given_source = "env" if source is click.core.ParameterSource.ENVIRONMENT else "flag"
        try:
            return require(resolve_location(key, value, given_source))
        except HostConfigError as error:
            raise click.UsageError(str(error), ctx) from None

    return click.option(
        spec.flag,
        type=click.Path(file_okay=False, path_type=Path),
        default=None,
        envvar=spec.env,
        callback=callback,
        **attrs,
    )
