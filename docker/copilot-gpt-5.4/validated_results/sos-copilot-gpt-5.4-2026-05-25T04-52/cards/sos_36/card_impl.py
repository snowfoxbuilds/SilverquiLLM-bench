"""Card implementation for Stone Docent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.casting import is_sorcery_speed
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class StoneDocent(Creature):
    """Stone Docent."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stone Docent")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Spirit", "Chimera"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "{W}, Exile this card from your graveyard: You gain 2 life. Surveil 1. "
            "Activate only as a sorcery.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self
        activation_cost = ManaCost.parse("{W}")

        def _cost(game: GameState, card: Creature) -> bool:
            owner = getattr(card, "owner", None)
            if owner is None:
                return False
            if not is_sorcery_speed(game, owner):
                return False
            if not game.get_graveyard(owner).contains(card):
                return False
            if not owner.mana_pool.can_pay(activation_cost):
                return False
            owner.mana_pool.pay(activation_cost)
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.EXILE)
            return True

        def _effect(game: GameState) -> None:
            owner = getattr(source, "owner", None)
            if owner is None:
                return
            owner.life += 2
            library = game.get_library(owner)
            if len(library) == 0:
                return
            top_card = library.top(1)[0]
            if owner.choose_yes_no("Put the top card of your library into your graveyard?"):
                move_to_zone(game, top_card, Zone.LIBRARY, Zone.GRAVEYARD)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{W}, Exile this card from your graveyard: You gain 2 life. Surveil 1.",
            )
        ]
