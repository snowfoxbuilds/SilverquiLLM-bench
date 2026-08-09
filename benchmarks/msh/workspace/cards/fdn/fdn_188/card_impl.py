"""Card implementation for Abrade."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant, Mode
from engine.card_queries import choose_mode
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    return any(game.get_battlefield(p).contains(obj) for p in game.players)


def _is_creature(obj: Any) -> bool:
    """Mode-0 target predicate — a creature. Shared by cast-time targeting and
    resolution revalidation so both enforce one predicate (rule 608.2b)."""
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _is_artifact(obj: Any) -> bool:
    """Mode-1 target predicate — an artifact. Shared by cast-time targeting and
    resolution revalidation so both enforce one predicate (rule 608.2b)."""
    return CardType.ARTIFACT in getattr(obj, "card_types", set())


# Mode indices — the chosen mode determines which target type is legal.
_MODE_DAMAGE = 0
_MODE_DESTROY_ARTIFACT = 1
_MODE_NAMES = ["Damage", "Destroy Artifact"]


class Abrade(Instant):
    """Abrade — {1}{R} — Instant.

    Choose one —
    • Abrade deals 3 damage to target creature.
    • Destroy target artifact.

    FDN collector number 188.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Abrade")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Abrade deals 3 damage to target creature.\n"
            "• Destroy target artifact.",
        )
        super().__init__(**kwargs)
        self._chosen_mode_index: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Damage", description="Abrade deals 3 damage to target creature."),
            Mode(name="Destroy Artifact", description="Destroy target artifact."),
        ]

    def get_targets(self, game: "GameState") -> list[Any]:
        """Choose the mode, then return the matching single-target requirement."""
        controller = self.controller or getattr(self, "owner", None)
        chosen = choose_mode(game, controller, _MODE_NAMES, "Choose one", source_card=self)
        self._chosen_mode_index = _MODE_NAMES.index(chosen)

        if self._chosen_mode_index == _MODE_DAMAGE:
            return [
                TargetRequirement(
                    filter_fn=_is_creature,
                    description="target creature",
                    zone=Zone.BATTLEFIELD,
                )
            ]
        return [
            TargetRequirement(
                filter_fn=_is_artifact,
                description="target artifact",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the chosen mode against the captured target."""
        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None or self._chosen_mode_index is None:
            return

        if self._chosen_mode_index == _MODE_DAMAGE:
            from engine.game import deal_damage

            # Revalidate the FULL original predicate (rule 608.2b): the target
            # must still be a creature on the battlefield, not merely present.
            if _on_battlefield(game, target) and _is_creature(target):
                deal_damage(game, self, target, 3)
        elif self._chosen_mode_index == _MODE_DESTROY_ARTIFACT:
            from engine.game import destroy

            if _on_battlefield(game, target) and _is_artifact(target):
                destroy(game, target)
