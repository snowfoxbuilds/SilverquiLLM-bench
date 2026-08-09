"""Card implementation for Treetop Snarespinner."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class TreetopSnarespinner(Creature):
    """Treetop Snarespinner — {3}{G} — 1/4 — Spider

    Reach
    Deathtouch
    {2}{G}: Put a +1/+1 counter on target creature you control. Activate
    only as a sorcery.

    FDN collector number 114.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Treetop Snarespinner")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("subtypes", {"Spider"})
        kwargs.setdefault("keywords", Keyword.REACH | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Reach\nDeathtouch\n{2}{G}: Put a +1/+1 counter on target "
            "creature you control. Activate only as a sorcery.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _can_activate(game: "GameState", src: Any, controller: Any) -> bool:
            # Legality (rule 602.2a) plus the sorcery-speed timing gate: only
            # during the controller's main phase with an empty stack.
            if controller is None or not _on_battlefield(game, src):
                return False
            if getattr(game, "active_player", None) is not controller:
                return False
            if getattr(game, "phase", None) not in (
                Phase.PRECOMBAT_MAIN,
                Phase.POSTCOMBAT_MAIN,
            ):
                return False
            return game.stack.is_empty()

        def _cost(game: "GameState", src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.get(ManaType.GREEN) < 1:
                return False
            if controller.mana_pool.total() < 3:
                return False
            controller.mana_pool.pay(ManaCost.parse("{2}{G}"))
            return True

        def _targeting(
            game: "GameState", src: Any, controller: Any
        ) -> list[Any] | None:
            # Choose the target at activation (rule 602.2b). Only a creature the
            # controller controls is a legal target.
            creatures = [
                obj
                for obj in game.get_battlefield(controller).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            ]
            if not creatures:
                return None
            target = choose_object(
                game,
                controller,
                creatures,
                "Choose target creature you control",
                source_card=src,
            )
            if target is None:
                return None
            return [target]

        def _effect(
            game: "GameState", targets: list[Any], context: Any = None
        ) -> None:
            from engine.game import add_counter

            target = targets[0] if targets else None
            if target is None or not _on_battlefield(game, target):
                return
            # Revalidate the "creature you control" restriction at resolution.
            if getattr(target, "controller", None) is not source.controller:
                return
            add_counter(game, target, "+1/+1", 1)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                targeting=_targeting,
                can_activate=_can_activate,
                description="{2}{G}: Put a +1/+1 counter on target creature "
                "you control. Activate only as a sorcery.",
            )
        ]
