"""Card implementation for Rubble Rouser."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, ManaAbility
from benchmarks.sos.workspace.engine.game import deal_damage, discard, draw_card, exile
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RubbleRouser(Creature):
    """Rubble Rouser."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rubble Rouser")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Sorcerer"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        hand = game.get_hand(controller).get_all()
        if not hand:
            return
        if not controller.choose_yes_no("Discard a card for Rubble Rouser?"):
            return
        chosen = controller.choose_card(hand, "card to discard")
        if chosen not in hand:
            return
        discard(game, controller, chosen)
        draw_card(game, controller)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: GameState, card: Creature) -> bool:
            controller = source.controller
            if controller is None or card.is_tapped:
                return False
            graveyard = game.get_graveyard(controller).get_all()
            if not graveyard:
                return False
            chosen = controller.choose_card(graveyard, "card to exile")
            if chosen not in graveyard:
                return False
            card.is_tapped = True
            exile(game, chosen)
            return True

        def _mana_produced(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            controller.mana_pool.add(ManaType.RED, 1)
            for player in game.players:
                if player is not controller:
                    deal_damage(game, source, player, 1)

        return [
            ManaAbility(
                cost=_cost,
                mana_produced=_mana_produced,
                description="{T}, Exile a card from your graveyard: Add {R}. When you do, this creature deals 1 damage to each opponent.",
            )
        ]
