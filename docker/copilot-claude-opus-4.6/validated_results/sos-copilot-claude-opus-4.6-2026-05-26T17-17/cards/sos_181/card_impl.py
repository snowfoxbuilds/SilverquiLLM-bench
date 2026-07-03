"""Card implementation for Colossus of the Blood Age."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature
from engine.events import EntersBattlefieldTriggeredEvent, CreatureDiesTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ColossusOfTheBloodAge(ArtifactCreature):
    """Colossus of the Blood Age — {4}{R}{W} — 6/6 Artifact Creature — Construct.

    When this creature enters, it deals 3 damage to each opponent and you gain 3 life.
    When this creature dies, discard any number of cards, then draw that many cards plus one.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Colossus of the Blood Age")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}{W}"))
        kwargs.setdefault("subtypes", {"Construct"})
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: deal 3 damage to each opponent, gain 3 life."""
        controller = self.controller
        # Move to battlefield
        bf = game.get_battlefield(controller)
        bf.add(self)
        # Register triggers
        self.register_triggers(game)
        # Fire ETB event
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=self, controller=controller),
        )
        # ETB effect: deal 3 to each opponent, gain 3 life
        for player in game.players:
            if player is not controller:
                player.life -= 3
        controller.life += 3

    def register_triggers(self, game: "GameState") -> None:
        """Register dies trigger."""
        source = self
        controller = self.controller

        def _dies_condition(game: "GameState", event: Any) -> bool:
            return event.creature is source

        def _dies_effect(game: "GameState") -> None:
            ctrl = source.controller or source.owner
            if ctrl is None:
                return
            from engine.game import draw_card, discard
            from engine.card import CardImpl as _CI
            from engine.types import Zone as _Zone
            # Discard any number of cards (deterministic: discard all)
            hand_cards = list(game.get_hand(ctrl).get_all())
            discarded = len(hand_cards)
            for card in hand_cards:
                discard(game, ctrl, card)
            # Draw that many plus one
            for _ in range(discarded + 1):
                library = ctrl.zones[_Zone.LIBRARY]
                if len(library) == 0:
                    library.add(_CI(name="Drawn Card", owner=ctrl, controller=ctrl))
                draw_card(game, ctrl)

        game.trigger_manager.register(TriggerRegistration(
            event_type=CreatureDiesTriggeredEvent,
            condition=_dies_condition,
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))

    def destroy(self, game: "GameState") -> None:
        """Destroy this creature — delegate to engine, then resolve triggers."""
        from engine.game import destroy
        destroy(game, self)
        # Resolve any triggers that were pushed onto the stack (e.g. dies trigger)
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
