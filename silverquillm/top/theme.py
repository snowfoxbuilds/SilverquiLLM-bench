"""Every colour, glyph and border the monitor draws (RUN-MONITORING.md, Look and feel).

Views name roles (``good``, ``claude``, ``tapped``), never colours or characters, so a new
look is a new ``Theme`` here. ``[monitor] theme`` in the host configuration picks one by
name; ``--no-flair`` picks the plain one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Glyphs are East Asian width "N" where a choice exists, so every terminal draws them one
# cell wide and columns stay aligned.
# Magic's five mana colours, softened to read on a dark console.
WHITE_MANA = "#f4ecc2"
BLUE_MANA = "#4aa3df"
BLACK_MANA = "#a58ec2"
RED_MANA = "#ef6b4a"
GREEN_MANA = "#4fbf7f"


@dataclass(frozen=True)
class Theme:
    name: str
    colors: dict[str, str]
    glyphs: dict[str, str]
    benchmark_badges: dict[str, str] = field(default_factory=dict)
    """Benchmark id prefix to a set-symbol-style badge; the longest matching prefix wins."""
    border: str = "round"
    rarity: tuple[tuple[float, str], ...] = ()
    """Pass-rate floors and the rarity role a score at or above each is coloured with."""

    def color(self, role: str) -> str:
        return self.colors.get(role, self.colors["text"])

    def glyph(self, role: str) -> str:
        return self.glyphs.get(role, "?")

    def style(self, role: str, *, bold: bool = False) -> str:
        """A Rich style for text in ``role``; a plain theme uses emphasis instead of colour."""
        color = self.colors.get(role)
        parts = ["bold"] if bold else []
        if color and not color.startswith("ansi_default"):
            parts.append(color)
        elif role in ("muted", "common"):
            parts.append("dim")
        elif role in ("bad", "needs_recover"):
            parts.append("bold reverse" if not bold else "reverse")
        return " ".join(parts) or "none"

    def badge(self, benchmark: str | None) -> str:
        if not benchmark:
            return self.glyph("badge_default")
        matches = [prefix for prefix in self.benchmark_badges if benchmark.startswith(prefix)]
        if not matches:
            return self.glyph("badge_default")
        return self.benchmark_badges[max(matches, key=len)]

    def rarity_role(self, pass_rate: float | None) -> str:
        if pass_rate is None:
            return "muted"
        for floor, role in self.rarity:
            if pass_rate >= floor:
                return role
        return "common"

    def css(self) -> str:
        c = self.color
        return f"""
Screen {{ background: {c("background")}; color: {c("text")}; overflow: hidden; }}
* {{
    scrollbar-background: {c("surface")};
    scrollbar-background-hover: {c("surface")};
    scrollbar-background-active: {c("surface")};
    scrollbar-color: {c("border")};
    scrollbar-color-hover: {c("border_focus")};
    scrollbar-color-active: {c("title")};
    scrollbar-corner-color: {c("surface")};
    scrollbar-size-vertical: 1;
    scrollbar-size-horizontal: 1;
}}
#switcher {{ height: 1fr; }}
#dashboard, #history, #details {{ height: 1fr; }}
#topbar {{ height: 1; background: {c("bar")}; color: {c("text")}; }}
#keys {{ height: 1; background: {c("bar")}; color: {c("muted")}; }}
.pane {{
    border: {self.border} {c("border")};
    border-title-color: {c("title")};
    border-title-style: bold;
    border-subtitle-color: {c("muted")};
    background: {c("surface")};
    padding: 0 1;
}}
.pane:focus-within {{ border: {self.border} {c("border_focus")}; }}
#status {{ height: auto; max-height: 16; }}
#where {{ width: 1fr; max-width: 64; margin-right: 2; }}
#counts {{ width: 22; margin-right: 3; padding-left: 2; border-left: solid {c("border")}; }}
#pools {{ width: 1fr; min-width: 44; }}
#lower {{ height: 1fr; }}
#running {{ width: 3fr; }}
#queued {{ width: 1fr; min-width: 34; max-width: 56; }}
.narrow #lower {{ layout: vertical; }}
.narrow #where {{ max-width: 44; }}
.narrow #running {{ width: 1fr; height: 2fr; }}
.narrow #queued {{ width: 1fr; max-width: 100%; height: 1fr; }}
#nav {{ width: 40; }}
#runs {{ width: 1fr; }}
#detail-head {{ height: auto; max-height: 12; }}
#detail-tabs {{ height: 1fr; }}
DataTable {{ background: {c("surface")}; }}
DataTable > .datatable--header {{ background: {c("surface")}; color: {c("title")}; text-style: bold; }}
DataTable > .datatable--cursor {{ background: {c("cursor")}; color: {c("text")}; }}
DataTable > .datatable--hover {{ background: {c("hover")}; }}
Tree {{ background: {c("surface")}; }}
Tree > .tree--cursor {{ background: {c("cursor")}; }}
RichLog {{ background: {c("surface")}; }}
TabbedContent ContentTabs {{ background: {c("surface")}; }}
Tab.-active {{ color: {c("title")}; text-style: bold; }}
.empty {{ color: {c("muted")}; padding: 1 2; }}
"""


MTG = Theme(
    name="mtg",
    colors={
        "background": "#0d0f14",
        "surface": "#12151c",
        "bar": "#1b1f2a",
        "border": "#3a4152",
        "border_focus": "#c9a227",
        "title": "#e8c35a",
        "text": "#d8dce6",
        "muted": "#7a8296",
        "cursor": "#2a3142",
        "hover": "#1e2330",
        "accent": "#e8c35a",
        "good": GREEN_MANA,
        "warn": "#e8b04a",
        "bad": RED_MANA,
        "live": "#5ee08a",
        "running": GREEN_MANA,
        "grading": BLUE_MANA,
        "starting": WHITE_MANA,
        "needs_recover": RED_MANA,
        "unknown": "#7a8296",
        "claude": "#e0875f",
        "codex": "#4fbf9f",
        "provider": BLACK_MANA,
        "mythic": "#f07a2a",
        "rare": "#d9b44a",
        "uncommon": "#b8c4d6",
        "common": "#7a8296",
        "message": "#d8dce6",
        "thinking": BLACK_MANA,
        "tool": BLUE_MANA,
        "result": "#9aa3b5",
        "task": WHITE_MANA,
        "limit": "#e8b04a",
        "system": "#7a8296",
        "done": GREEN_MANA,
        "error": RED_MANA,
        "raw": "#7a8296",
        "bar_fill": GREEN_MANA,
        "bar_warn": "#e8b04a",
        "bar_hot": RED_MANA,
        "bar_empty": "#2e3442",
        "spark": "#e8c35a",
    },
    glyphs={
        "logo": "✦ SILVERQUILLM",
        "tapped": "↷",
        "untapped": "◦",
        "pending": "⚠",
        "lock_unknown": "?",
        "running": "▸",
        "grading": "⚖",
        "starting": "◌",
        "needs_recover": "✖",
        "unknown": "?",
        "completed": "✔",
        "failed": "✖",
        "deadline": "⧖",
        "interrupted": "⏸",
        "host_failed": "⚠",
        "status_unknown": "·",
        "live": "◉ LIVE",
        "needs_recover_badge": "⚠ NEEDS RECOVER",
        "historical": "◼ HISTORICAL",
        "queued": "◷",
        "finished": "✔",
        "batch": "⬢",
        "needs_ack": "⚠ needs ack",
        "excluded": "⊘",
        "bar_full": "▰",
        "bar_empty": "▱",
        "spark": "▁▂▃▄▅▆▇█",
        "sep": " · ",
        "badge_default": "✦",
        "estimated": "≈",
        "provisional": "~",
        "message": "❝",
        "thinking": "✧",
        "tool": "⚒",
        "result": "↳",
        "task": "⚑",
        "limit": "⌁",
        "system": "⚙",
        "done": "✦",
        "error": "✖",
        "raw": "·",
        "commit": "◉",
        "snapshot": "◫",
    },
    benchmark_badges={
        "smoke": "✧",
        "hob": "❦",
        "fra": "✠",
        "sos": "☾",
        "fdn": "✪",
    },
    rarity=((0.9, "mythic"), (0.7, "rare"), (0.4, "uncommon")),
)

PLAIN = Theme(
    name="plain",
    colors={role: "ansi_default" for role in MTG.colors} | {"bar": "ansi_default"},
    glyphs={
        "logo": "SILVERQUILLM",
        "tapped": "*",
        "untapped": "-",
        "pending": "!",
        "lock_unknown": "?",
        "running": ">",
        "grading": "=",
        "starting": ".",
        "needs_recover": "X",
        "unknown": "?",
        "completed": "ok",
        "failed": "FAIL",
        "deadline": "TIME",
        "interrupted": "INT",
        "host_failed": "HOST",
        "status_unknown": "-",
        "live": "[LIVE]",
        "needs_recover_badge": "[NEEDS RECOVER]",
        "historical": "[HISTORICAL]",
        "queued": "o",
        "finished": "v",
        "batch": "#",
        "needs_ack": "! needs ack",
        "excluded": "x",
        "bar_full": "#",
        "bar_empty": ".",
        "spark": "_.-=*#",
        "sep": " | ",
        "badge_default": "",
        "estimated": "~",
        "provisional": "~",
        "message": ">",
        "thinking": "?",
        "tool": "$",
        "result": "<",
        "task": "+",
        "limit": "%",
        "system": "-",
        "done": "*",
        "error": "!",
        "raw": " ",
        "commit": "o",
        "snapshot": "s",
    },
    border="ascii",
    rarity=(),
)

THEMES = {theme.name: theme for theme in (MTG, PLAIN)}
DEFAULT_THEME = MTG.name


def theme_named(name: str | None, *, no_flair: bool = False) -> tuple[Theme, str | None]:
    """The selected theme and, for an unknown name, why the default was used instead."""
    if no_flair:
        return PLAIN, None
    if not name:
        return THEMES[DEFAULT_THEME], None
    if name in THEMES:
        return THEMES[name], None
    known = ", ".join(sorted(THEMES))
    return THEMES[DEFAULT_THEME], f"unknown theme {name!r} (known: {known})"
