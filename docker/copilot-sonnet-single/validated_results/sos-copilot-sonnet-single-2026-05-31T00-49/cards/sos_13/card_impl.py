"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares.

    Front face: Emeritus of Truce — {1}{W}{W} — Creature — Cat Cleric — 3/3.
    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    While prepared, you may cast a copy of its spell (Swords to Plowshares):
    Exile target creature. Its controller gains life equal to its power.
    Doing so unprepares it.

    ENGINE LIMITATION: DFC casting mechanics are not fully supported.
    The Prepared ability is implemented as an activated method
    ``cast_swords_to_plowshares(game, target)`` that can be invoked while
    ``self.is_prepared`` is True.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("supertypes", set())
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature becomes "
            "prepared. (While it's prepared, you may cast a copy of its "
            "spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    # ------------------------------------------------------------------
    # ETB trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the enters-the-battlefield trigger."""
        from engine.card import Creature as CreatureCard
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.game import create_token
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Determine target player (default: controller; scripted answer if available).
            target_player = ctrl
            try:
                target_player = ctrl.choose(game.players, "Choose target player for Inkling token")
            except Exception:
                target_player = ctrl

            # Create 1/1 Inkling token with flying.
            inkling = CreatureCard(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
                owner=target_player,
                controller=target_player,
            )
            create_token(game, target_player, inkling)

            # Become prepared if an opponent controls more creatures than you.
            # Exclude source itself (as it "just entered" the battlefield check).
            my_bf = game.get_battlefield(ctrl)
            my_creatures = sum(
                1 for c in my_bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and c is not source
            )
            for opp in game.players:
                if opp is ctrl:
                    continue
                opp_bf = game.get_battlefield(opp)
                opp_creatures = sum(
                    1 for c in opp_bf.get_all()
                    if CardType.CREATURE in getattr(c, "card_types", set())
                )
                if opp_creatures > my_creatures:
                    source.is_prepared = True
                    break

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Swords to Plowshares (Prepared spell)
    # ------------------------------------------------------------------

    def cast_swords_to_plowshares(self, game: "GameState", target: Any) -> bool:
        """Cast a copy of Swords to Plowshares if prepared.

        Exiles *target* creature and gives its controller life equal to its power.
        Unprepares this card on success.

        Returns True on success, False if not prepared or target is invalid.
        """
        if not self.is_prepared:
            return False

        # Validate target is a creature on the battlefield.
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                break
        else:
            return False

        # Exile the creature.
        target_controller = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        # Remove from battlefield and put in exile.
        from engine.zones import move_to_zone
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)
        # Give life to target's controller.
        if target_controller is not None and power > 0:
            target_controller.life += power

        self.is_prepared = False
        return True

