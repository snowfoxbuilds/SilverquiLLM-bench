"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 — Legendary Creature — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    Prepared: You may cast a copy of Swords to Plowshares (exile target
    creature; its controller gains life equal to its power). Doing so
    unprepares this creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent controls "
            "more creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        """Register the ETB trigger."""
        from engine.triggers import TriggerRegistration
        from engine.events import EntersBattlefieldTriggeredEvent

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _etb_effect(game: Any) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # Choose target player to receive the Inkling token
            try:
                target_player = controller.choose(game.players, "Choose a player to create an Inkling token")
            except Exception:
                target_player = controller

            # Create a 1/1 white and black Inkling with flying
            from engine.game import create_token
            from engine.card import Creature as _Creature

            inkling = _Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            inkling.is_token = True
            create_token(game, target_player, inkling)

            # Count creatures on battlefield now (after token creation)
            opponent_creature_count = 0
            my_creature_count = 0
            for p in game.players:
                bf = game.get_battlefield(p)
                count = sum(
                    1 for obj in bf.get_all()
                    if CardType.CREATURE in getattr(obj, "card_types", set())
                )
                if p is controller:
                    my_creature_count = count
                else:
                    if count > opponent_creature_count:
                        opponent_creature_count = count

            if opponent_creature_count > my_creature_count:
                source.is_prepared = True

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent,
            condition=_condition,
            effect=_etb_effect,
            source=self,
            controller=controller,
        ))

    def cast_prepared_spell(self, game: "GameState", target_creature: Any) -> None:
        """Cast a copy of Swords to Plowshares from the prepared state.

        Exiles target creature; its controller gains life equal to its power.
        Unprepares this card.
        """
        if not self.is_prepared:
            return

        controller = getattr(self, "controller", None)
        if controller is None:
            return

        # Check target is on battlefield
        on_bf = False
        for p in game.players:
            if game.get_battlefield(p).contains(target_creature):
                on_bf = True
                break
        if not on_bf:
            return

        from engine.game import exile

        power = getattr(target_creature, "power", 0)
        target_controller = getattr(target_creature, "controller", None)

        exile(game, target_creature)
        if target_controller is not None:
            target_controller.life += power

        # Unprepare
        self.is_prepared = False

