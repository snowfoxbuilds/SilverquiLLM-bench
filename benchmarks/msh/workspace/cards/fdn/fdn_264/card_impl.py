"""Card implementation for Rogue's Passage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.card_queries import choose_object
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    ContinuousEffect,
    Layer,
)
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class RoguesPassage(Land):
    """Rogue's Passage — Land.

    {T}: Add {C}.
    {4}, {T}: Target creature can't be blocked this turn.

    FDN collector number 264.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rogue's Passage")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{4}, {T}: Target creature can't be blocked this turn.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            )
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 4:
                return False
            controller.mana_pool.pay(ManaCost(generic=4))
            src.is_tapped = True
            return True

        def _effect(game: "GameState") -> None:
            target = getattr(source, "_current_target", None)
            if target is None:
                creatures = [
                    obj
                    for player in game.players
                    for obj in game.get_battlefield(player).get_all()
                    if CardType.CREATURE in getattr(obj, "card_types", set())
                ]
                if not creatures:
                    return
                controller = source.controller or source.owner
                target = choose_object(
                    game,
                    controller,
                    creatures,
                    "Choose target creature that can't be blocked this turn",
                    source_card=source,
                )
            if target is not None and _is_on_battlefield(game, target):
                chosen = target

                def _apply(game: "GameState") -> None:
                    chosen._cant_be_blocked = True

                # Applied as an until-end-of-turn continuous effect: the
                # _cant_be_blocked flag is reset on every apply_all() pass,
                # so a bare assignment would not survive re-application.
                chosen._cant_be_blocked = True
                game.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.ABILITY,
                        apply=_apply,
                        duration=DURATION_END_OF_TURN,
                    )
                )

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{4}, {T}: Target creature can't be blocked this turn.",
            )
        ]
