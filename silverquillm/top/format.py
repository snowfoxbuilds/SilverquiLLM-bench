"""Cells and fragments the views draw, as Rich ``Text`` styled by theme role."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from rich.text import Text

from silverquillm.monitor import LiveRun, Score, Stage, WeeklyUsage

from .theme import Theme

DASH = "—"


def duration(seconds: float | None) -> str:
    if seconds is None:
        return DASH
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def short_duration(seconds: float | None) -> str:
    """``4h``, ``1h05``, ``20m``, ``45s``: for dense columns."""
    if seconds is None:
        return DASH
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    if hours:
        return f"{hours}h" if not minutes else f"{hours}h{minutes:02d}"
    return f"{minutes}m" if minutes else f"{seconds}s"


def ago(delta: timedelta | None) -> str:
    if delta is None:
        return "?"
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def when(moment: datetime | None, *, with_day: bool = True) -> str:
    if moment is None:
        return DASH
    local = moment.astimezone()
    return local.strftime("%m-%d %H:%M" if with_day else "%H:%M")


def until(moment: datetime | None, now: datetime) -> str:
    """A countdown such as ``in 2h05m``, or the local time once it has passed."""
    if moment is None:
        return DASH
    seconds = (moment - now).total_seconds()
    return f"in {duration(seconds)}" if seconds > 0 else f"since {when(moment)}"


def money(amount: Decimal | None, theme: Theme, *, provisional: bool = False) -> Text:
    if amount is None:
        return Text(DASH, style=theme.style("muted"))
    prefix = theme.glyph("provisional") if provisional else ""
    style = theme.style("accent") if amount >= 10 else theme.style("text")
    return Text(f"{prefix}${amount:,.2f}", style=style)


def spend(
    amount: Decimal | None,
    theme: Theme,
    *,
    recorded: bool,
    completeness: str | None,
    conflicting: int = 0,
) -> Text:
    """A run's cost: ``~`` while provisional, ``*`` when its record calls it incomplete."""
    text = money(amount, theme, provisional=not recorded)
    if amount is not None and recorded and completeness not in (None, "complete"):
        text.append(theme.glyph("partial"), style=theme.style("muted"))
    if conflicting:
        text.append(f" {theme.glyph('conflict')}{conflicting}", style=theme.style("warn"))
    return text


def count(value: int | None) -> str:
    if value is None:
        return DASH
    for limit, suffix in ((1_000_000_000, "G"), (1_000_000, "M"), (1_000, "k")):
        if value >= limit:
            return f"{value / limit:.1f}{suffix}"
    return str(value)


def bar(fraction: float | None, width: int, theme: Theme) -> Text:
    if fraction is None:
        return Text(" " * width)
    fraction = min(1.0, max(0.0, fraction))
    filled = round(fraction * width)
    role = "bar_hot" if fraction >= 0.9 else "bar_warn" if fraction >= 0.75 else "bar_fill"
    text = Text(theme.glyph("bar_full") * filled, style=theme.style(role))
    text.append(theme.glyph("bar_empty") * (width - filled), style=theme.style("bar_empty"))
    return text


def sparkline(
    points: Sequence[tuple[int, Decimal]], width: int, theme: Theme, *, until_ms: int | None = None
) -> Text:
    """Spend per time bucket across the run so far, one character per bucket."""
    if not points:
        return Text(" " * width)
    start = points[0][0]
    end = max(until_ms or 0, points[-1][0], start + 1)
    span = (end - start) / width
    buckets = [Decimal(0)] * width
    for stamp, usd in points:
        buckets[min(width - 1, int((stamp - start) / span))] += usd
    top = max(buckets)
    ramp = theme.glyph("spark")
    if top <= 0:
        return Text(ramp[0] * width, style=theme.style("muted"))
    chars = "".join(
        ramp[min(len(ramp) - 1, int(bucket / top * (len(ramp) - 1)))] if bucket else " "
        for bucket in buckets
    )
    return Text(chars, style=theme.style("spark"))


def weekly(usage: WeeklyUsage | None, now: datetime, theme: Theme) -> Text:
    """``41% · resets Thu 14:00 · read 12m ago``, or ``≈ 47%`` when estimated."""
    if usage is None:
        return Text("no rate", style=theme.style("muted"))
    role = "bad" if usage.percent >= 90 else "warn" if usage.percent >= 75 else "text"
    text = Text()
    if usage.estimated:
        text.append(theme.glyph("estimated") + " ", style=theme.style("muted"))
    text.append(f"{usage.percent:.0f}%", style=theme.style(role, bold=True))
    if usage.resets_at is not None:
        reset = usage.resets_at.astimezone().strftime("%a %H:%M")
        text.append(f"{theme.glyph('sep')}resets {reset}", style=theme.style("muted"))
        bound = "" if usage.reading_age_exact else theme.glyph("at_least")
        text.append(
            f"{theme.glyph('sep')}read {bound}{ago(usage.reading_age(now))}",
            style=theme.style("muted"),
        )
    return text


def score(value: Score | None, theme: Theme, *, counts: bool = True) -> Text:
    """A pass rate coloured by rarity: mythic, rare, uncommon, common."""
    if value is None or not value.evaluated or value.pass_rate is None:
        return Text(DASH, style=theme.style("muted"))
    role = theme.rarity_role(value.pass_rate)
    text = Text(f"{value.pass_rate * 100:3.0f}%", style=theme.style(role, bold=True))
    if counts and value.total is not None:
        text.append(f" {value.passed or 0}/{value.total}", style=theme.style("muted"))
    return text


STAGE_ROLES = {
    Stage.RUNNING: "running",
    Stage.GRADING: "grading",
    Stage.STARTING: "starting",
    Stage.RECORDING: "recording",
    Stage.NEEDS_RECOVER: "needs_recover",
    Stage.UNKNOWN: "unknown",
}


REASONS = {
    "no_record": "no record",
    "unconfirmed_stop": "stop unconfirmed",
    "unpublished": "not published",
    "login_settlement_pending": "login unsettled",
    "unreadable_record": "record unreadable",
    "ambiguous_linked_recovery": "recoveries disagree",
    "mismatched_record": "record mismatched",
    "unreadable_published_record": "published record unreadable",
    "ambiguous_published_record": "published records disagree",
}


def reasons(run: LiveRun, theme: Theme) -> Text:
    """Whether its container runs, then why a run needs recovery: ``container up · no record``."""
    # Whether the container still runs comes first: a live workload is the urgent case.
    words = []
    if run.container is not None:
        words.append(f"container {'up' if run.container.running else 'stopped'}")
    words += [REASONS.get(code, code.replace("_", " ")) for code in run.reasons]
    return Text(theme.glyph("sep").join(words), style=theme.style("needs_recover"))


def stage(value: Stage, theme: Theme) -> Text:
    role = STAGE_ROLES[value]
    label = value.value.replace("_", " ")
    return Text(f"{theme.glyph(role)} {label}", style=theme.style(role, bold=True))


STATUS_ROLES = {
    "completed": "good",
    "failed": "bad",
    "deadline": "warn",
    "interrupted": "warn",
    "host_failed": "bad",
}


def status(value: str | None, theme: Theme) -> Text:
    role = STATUS_ROLES.get(value or "", "muted")
    glyph = theme.glyph(value if value in STATUS_ROLES else "status_unknown")
    return Text(f"{glyph} {value or 'unknown'}", style=theme.style(role))


def provider_role(provider: str | None) -> str:
    return provider if provider in ("claude", "codex") else "provider"


def badge(benchmark: str | None, theme: Theme) -> Text:
    symbol = theme.badge(benchmark)
    text = Text(f"{symbol} " if symbol else "", style=theme.style("accent", bold=True))
    text.append(benchmark or DASH, style=theme.style("text"))
    return text
