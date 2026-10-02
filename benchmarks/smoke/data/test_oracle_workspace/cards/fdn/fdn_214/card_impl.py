"""Card implementation for Broken Wings."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None

class BrokenWings(Instant):
    """Broken Wings — {2}{G} — Destroy target artifact, enchantment,
    or creature with flying.

    FDN collector number 214.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Broken Wings")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Destroy target artifact, enchantment, or creature with flying.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target artifact, enchantment, or creature with flying."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                card_types = getattr(obj, "card_types", set())
                if CardType.ARTIFACT in card_types or CardType.ENCHANTMENT in card_types:
                    targets.append(obj)
                elif CardType.CREATURE in card_types:
                    kw = getattr(obj, "keywords", Keyword(0))
                    if Keyword.FLYING in kw:
                        targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    bool(getattr(obj, "card_types", set()) & {CardType.ARTIFACT, CardType.ENCHANTMENT})
                    or (CardType.CREATURE in getattr(obj, "card_types", set())
                        and Keyword.FLYING in getattr(obj, "keywords", Keyword(0)))),
                description="target artifact, enchantment, or creature with flying",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                destroy(game, target)
                return
