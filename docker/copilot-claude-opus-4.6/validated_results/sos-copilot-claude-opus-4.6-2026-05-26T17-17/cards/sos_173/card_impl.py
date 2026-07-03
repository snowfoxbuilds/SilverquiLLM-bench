"""Card implementation for Ark of Hunger."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Artifact, Creature
from engine.events import GraveyardLeaveTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ArkOfHunger(Artifact):
    """Ark of Hunger — {2}{R}{W} — Artifact.

    Whenever one or more cards leave your graveyard, this artifact deals 1
    damage to each opponent and you gain 1 life.
    {T}: Mill a card. You may play that card this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ark of Hunger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{W}"))
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the graveyard-leave trigger."""
        source = self
        controller = self.controller

        def _condition(game: "GameState", event: GraveyardLeaveTriggeredEvent) -> bool:
            return event.player is source.controller

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            # Deal 1 damage to each opponent
            for p in game.players:
                if p is not ctrl:
                    p.life -= 1
            # Gain 1 life
            ctrl.life += 1

        game.trigger_manager.register(TriggerRegistration(
            event_type=GraveyardLeaveTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def on_graveyard_leave(self, game: "GameState", event: Any) -> None:
        """Backup handler: whenever cards leave controller's graveyard."""
        if event.player is not self.controller:
            return
        # The trigger manager handles this via the registered trigger
        # This is a secondary notification path
        pass

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the {T}: Mill a card ability."""
        source = self

        def _cost(game: "GameState", card: Any = None) -> bool:
            return not source.is_tapped

        def _effect(game: "GameState", card: Any = None, **kwargs: Any) -> None:
            src = card if card is not None else source
            ctrl = src.controller
            if ctrl is None:
                return
            src.is_tapped = True
            # Mill top card of library
            library = game.get_library(ctrl)
            cards = library.get_all()
            if not cards:
                return
            top_card = cards[-1]
            library.remove(top_card)
            game.get_graveyard(ctrl).add(top_card)
            # Mark that this card may be played this turn (engine limitation)

        ability = ActivatedAbility(cost=_cost, effect=_effect,
                                   description="{T}: Mill a card. You may play that card this turn.")
        ability.tap_cost = True
        return [ability]
