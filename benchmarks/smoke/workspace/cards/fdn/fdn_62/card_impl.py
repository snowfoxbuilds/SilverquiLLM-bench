"""Card implementation for Hungry Ghoul."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class HungryGhoul(Creature):
    """Hungry Ghoul — {1}{B} — 2/2 — Zombie

    {1}, Sacrifice another creature: Put a +1/+1 counter on this creature.

    FDN collector number 62.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hungry Ghoul")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Zombie"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{1}, Sacrifice another creature: Put a +1/+1 counter on "
            "this creature.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _can_activate(game: "GameState", src: Any, controller: Any) -> bool:
            # Legality: the source is on the battlefield (instant speed, so no
            # timing gate). The "another creature" cost is checked when paid.
            return controller is not None and _on_battlefield(game, src)

        def _another_creatures(game: "GameState", controller: Any) -> list[Any]:
            # "another creature" you control — every creature but this one.
            return [
                obj
                for obj in game.get_battlefield(controller).get_all()
                if obj is not source
                and CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "controller", None) is controller
            ]

        def _cost(game: "GameState", src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 1:
                return False
            # "Sacrifice another creature" is a cost: the creature to sacrifice
            # is chosen when the cost is paid, via a Player Query (answered by
            # Intents in tests / the replay-derived intent in validation). No
            # legal creature to sacrifice → the cost cannot be paid.
            candidates = _another_creatures(game, controller)
            if not candidates:
                return False
            sac = choose_object(
                game,
                controller,
                candidates,
                "Choose another creature to sacrifice",
                source_card=src,
            )
            if sac is None or sac is src:
                return False
            controller.mana_pool.pay(ManaCost(generic=1))
            from engine.game import sacrifice

            sacrifice(game, controller, sac)
            return True

        def _effect(game: "GameState") -> None:
            from engine.game import add_counter

            if _on_battlefield(game, source):
                add_counter(game, source, "+1/+1", 1)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                can_activate=_can_activate,
                description="{1}, Sacrifice another creature: Put a +1/+1 "
                "counter on this creature.",
            )
        ]
