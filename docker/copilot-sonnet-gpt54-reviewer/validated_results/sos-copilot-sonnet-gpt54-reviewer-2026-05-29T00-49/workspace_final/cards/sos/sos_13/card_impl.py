"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell — Swords to Plowshares — doing so
    unprepares it.)

    sos collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
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

    def register_triggers(self, game: "GameState") -> None:
        """Register the ETB trigger that creates an Inkling token and potentially prepares."""
        from engine.triggers import TriggerRegistration

        source = self

        def _self_etb_condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _etb_effect(game: "GameState") -> None:
            # Determine target player: prefer chosen_targets on the trigger event,
            # fall back to the source's controller.
            controller = getattr(source, "controller", None)
            if controller is None:
                controller = game.players[0]
            # If a target player was explicitly chosen (e.g. via trigger resolution),
            # use that; otherwise default to the controller.
            target_player = getattr(source, "_etb_target_player", None) or controller

            # Step 1: Create 1/1 white and black Inkling token with flying
            from engine.game import create_token

            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                base_power=1,
                base_toughness=1,
                keywords=Keyword.FLYING,
            )
            # Set colors on the token (white and black) as an attribute
            token.colors = {"white", "black"}

            create_token(game, target_player, token)

            # Step 2: Check if any opponent controls more creatures than you
            my_creatures = sum(
                1
                for obj in game.get_battlefield(controller).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )
            opponent_has_more = False
            for player in game.players:
                if player is controller:
                    continue
                opp_creatures = sum(
                    1
                    for obj in game.get_battlefield(player).get_all()
                    if CardType.CREATURE in getattr(obj, "card_types", set())
                )
                if opp_creatures > my_creatures:
                    opponent_has_more = True
                    break

            if opponent_has_more:
                source.is_prepared = True

        controller = getattr(self, "controller", None) or (game.players[0] if game.players else None)
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_self_etb_condition,
                effect=_etb_effect,
                source=self,
                controller=controller,
                immediate=True,
            )
        )

    def on_resolve_swords_to_plowshares(self, game: "GameState") -> None:
        """Resolve a copy of Swords to Plowshares from the prepared state.

        Exiles the target creature and grants its controller life equal to
        the creature's power. Unprepares this creature.
        """
        chosen = getattr(self, "chosen_targets", [])
        if not chosen:
            self.is_prepared = False
            return

        target = chosen[0]

        # Determine the target's effective power before exiling (includes counters)
        power = getattr(target, "power", None)
        if power is None:
            power = getattr(target, "base_power", 0)

        # Exile the target creature
        from engine.game import exile, gain_life

        exile(game, target)

        # Target's controller gains life equal to target's power (via gain_life helper)
        target_controller = getattr(target, "controller", None)
        if target_controller is not None and power > 0:
            gain_life(game, target_controller, power)

        # Unprepare this creature
        self.is_prepared = False
