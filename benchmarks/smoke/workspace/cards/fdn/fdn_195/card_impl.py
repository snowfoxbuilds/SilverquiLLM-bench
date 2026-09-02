"""Card implementation for Fanatical Firebrand."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.stack import surviving_targets
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _any_targets(game: Any) -> list[Any]:
    """Every "any target": each player, and each creature/planeswalker."""
    targets: list[Any] = []
    for player in game.players:
        targets.append(player)
        for obj in game.get_battlefield(player).get_all():
            types = getattr(obj, "card_types", set())
            if CardType.CREATURE in types or CardType.PLANESWALKER in types:
                targets.append(obj)
    return targets


def _still_legal(game: Any, obj: Any) -> bool:
    """A player is always a legal target; a permanent must still be on the battlefield."""
    if hasattr(obj, "life"):
        return True
    return _on_battlefield(game, obj)


class FanaticalFirebrand(Creature):
    """Fanatical Firebrand — {R} — 1/1 — Goblin Pirate

    Haste
    {T}, Sacrifice this creature: It deals 1 damage to any target.

    FDN collector number 195.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fanatical Firebrand")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault("subtypes", {"Goblin", "Pirate"})
        kwargs.setdefault("keywords", Keyword.HASTE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Haste\n{T}, Sacrifice this creature: It deals 1 damage to "
            "any target.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _can_activate(game: "GameState", src: Any, controller: Any) -> bool:
            # The source must be on the battlefield and untapped to pay {T}.
            # (Haste means summoning sickness never blocks the tap.)
            return (
                controller is not None
                and _on_battlefield(game, src)
                and not getattr(src, "is_tapped", False)
            )

        def _targeting(
            game: "GameState", src: Any, controller: Any
        ) -> list[Any] | None:
            candidates = _any_targets(game)
            if not candidates:
                return None
            target = choose_object(
                game,
                controller,
                candidates,
                "Choose any target for 1 damage",
                source_card=src,
            )
            if target is None:
                return None
            return [target]

        def _cost(game: "GameState", src: Any) -> bool:
            from engine.game import sacrifice

            controller = src.controller
            if controller is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            sacrifice(game, controller, src)
            return True

        def _effect(
            game: "GameState", targets: list[Any], context: Any = None
        ) -> None:
            from engine.game import deal_damage

            # Revalidate via the shared helper: a player is always legal
            # (same_stint short-circuits players); a permanent must still be the
            # same battlefield stint and a legal any-target.
            legal = surviving_targets(
                game, context, targets, is_legal=lambda t: _still_legal(game, t)
            )
            target = legal[0] if legal else None
            if target is None:
                return
            deal_damage(game, source, target, 1)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                targeting=_targeting,
                can_activate=_can_activate,
                description="{T}, Sacrifice this creature: It deals 1 damage "
                "to any target.",
            )
        ]
