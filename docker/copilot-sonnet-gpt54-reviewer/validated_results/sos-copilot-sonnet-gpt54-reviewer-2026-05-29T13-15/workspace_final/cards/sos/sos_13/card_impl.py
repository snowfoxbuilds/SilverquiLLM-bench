"""Card implementation for Emeritus of Truce // Swords to Plowshares (sos_13)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} // {W}

    Front: 3/3 Cat Cleric
    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell — Swords to
    Plowshares: Exile target creature. Its controller gains life equal to
    that creature's power. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    # ------------------------------------------------------------------
    # ETB trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register ETB trigger for Inkling token + prepared check."""
        source = self

        def condition(g: "GameState", event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source

        def effect(g: "GameState") -> None:
            _etb_effect(g, source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=condition,
                effect=effect,
                source=self,
                controller=self.controller,
            )
        )

    # ------------------------------------------------------------------
    # Prepared ability (Swords to Plowshares copy)
    # ------------------------------------------------------------------

    def cast_prepared_ability(self, game: "GameState") -> None:
        """Cast a copy of Swords to Plowshares. Unprepares this creature."""
        if not self.is_prepared:
            return
        player = self.controller
        if player is None:
            return

        # Choose target creature
        # Find creatures on battlefield (any player's)
        all_creatures = []
        for p in game.players:
            for obj in game.get_battlefield(p).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    all_creatures.append(obj)

        if not all_creatures:
            self.is_prepared = False
            return

        target = player.choose_card(all_creatures, "Choose target creature for Swords to Plowshares")
        if target is None:
            return

        # Exile the target creature
        target_owner = getattr(target, "owner", None) or getattr(target, "controller", None)
        target_controller = getattr(target, "controller", None) or target_owner

        # Find which zone it's in
        moved = False
        for p in game.players:
            bf = game.get_battlefield(p)
            if bf.contains(target):
                bf.remove(target)
                moved = True
                break

        if moved and target_owner is not None:
            target_owner.zones[Zone.EXILE].add(target)

            # Its controller gains life equal to its power
            if target_controller is not None:
                power = getattr(target, "power", 0)
                if callable(power):
                    power = power()
                target_controller.life += int(power)

        self.is_prepared = False


def _etb_effect(game: "GameState", card: EmeritusOfTruceSwordsToPlowshares) -> None:
    """ETB: create Inkling token, check prepared condition."""
    from engine.game import create_token

    controller = card.controller
    if controller is None:
        return

    # Check prepared condition FIRST (before token creation changes counts)
    controller_creatures = len([
        obj for obj in game.get_battlefield(controller).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    ])

    becomes_prepared = False
    for opponent in game.players:
        if opponent is controller:
            continue
        opp_creatures = len([
            obj for obj in game.get_battlefield(opponent).get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        ])
        if opp_creatures > controller_creatures:
            becomes_prepared = True
            break

    # Choose target player to receive the token
    target_player = controller.choose_card(
        game.players, "Choose a player to create a 1/1 Inkling token"
    )
    if target_player is None:
        target_player = controller

    # Create 1/1 white and black Inkling with flying
    inkling = Creature(
        name="Inkling",
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        base_power=1,
        base_toughness=1,
    )
    create_token(game, target_player, inkling)

    if becomes_prepared:
        card.is_prepared = True
