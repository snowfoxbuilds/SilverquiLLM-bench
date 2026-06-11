"""Card implementation for Lluwen, Exchange Student // Pest Friend."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.casting import is_sorcery_speed
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Supertype, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class PestFriend(Sorcery):
    """Prepared spell copy for Lluwen, Exchange Student."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pest Friend")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B/G}"))
        super().__init__(**kwargs)


class LluwenExchangeStudentPestFriend(Creature):
    """Lluwen, Exchange Student."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lluwen, Exchange Student")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{G}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return PestFriend(owner=self.owner, controller=self.controller)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, card: Creature) -> bool:  # noqa: ARG001
            controller = getattr(source, "controller", None)
            if controller is None or not is_sorcery_speed(game, controller):
                return False

            graveyard_cards = [
                graveyard_card
                for graveyard_card in game.get_graveyard(controller).get_all()
                if CardType.CREATURE in getattr(graveyard_card, "card_types", set())
            ]
            if not graveyard_cards:
                return False

            try:
                chosen = controller.choose_card(graveyard_cards, "Choose a creature card to exile")
            except Exception:
                chosen = graveyard_cards[0]
            if chosen not in graveyard_cards:
                chosen = graveyard_cards[0]

            move_to_zone(game, chosen, Zone.GRAVEYARD, Zone.EXILE)
            return True

        def _effect(_game: GameState) -> None:
            source.become_prepared()

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="Exile a creature card from your graveyard: This creature becomes prepared. Activate only as a sorcery.",
            )
        ]
