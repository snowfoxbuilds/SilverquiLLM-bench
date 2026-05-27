"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent, GainsLifeTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares.

    {1}{W}{W} — Creature — Cat Cleric — 3/3

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

    Swords to Plowshares — Exile target creature. Its controller gains life
    equal to its power.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        self.prepared: bool = False

    # ------------------------------------------------------------------
    # ETB trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the ETB trigger for Inkling token creation and prepared check."""
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # Shared mutable state: target player chosen at announcement time.
        # Following the on_announce pattern from KEY_DECISIONS.md (established
        # for sos_1): targets must be fixed when the trigger is put on the stack,
        # before opponents receive priority.
        announcement_state: dict[str, Any] = {"target_player": None}

        def _condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _on_announce(game: "GameState", event: Any) -> None:
            """Fix the target player when the trigger is announced onto the stack.

            Per KEY_DECISIONS.md, targets for triggered abilities are chosen at
            announcement time (when put onto the stack), before opponents receive
            priority.  If no scripted choice is available (e.g. direct unit-test
            invocations), we leave the target as None so that ``_effect`` falls
            back to choosing interactively at resolution.
            """
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            try:
                target_player = ctrl.choose(
                    game.players, "Choose a player to create an Inkling token for"
                )
                announcement_state["target_player"] = target_player
            except Exception:
                # No scripted answer available (direct test firing); target will
                # be chosen at resolution time inside _effect.
                announcement_state["target_player"] = None

        def _effect(game: "GameState") -> None:
            from engine.game import create_token

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Use the target player fixed at announcement time; fall back to
            # a fresh choice only when called directly (e.g. in unit tests that
            # invoke _effect without going through fire_event/on_announce).
            target_player = announcement_state["target_player"]
            if target_player is None:
                target_player = ctrl.choose(
                    game.players, "Choose a player to create an Inkling token for"
                )

            # Create the 1/1 white-and-black Inkling token with flying.
            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            token.colors = {"W", "B"}
            create_token(game, target_player, token)

            # Reset target so a second direct invocation (tests) re-prompts.
            announcement_state["target_player"] = None

            # Check prepared condition: an opponent controls strictly more
            # creatures than the controller does.
            my_creature_count = sum(
                1
                for obj in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )
            opp_max = max(
                (
                    sum(
                        1
                        for obj in game.get_battlefield(p).get_all()
                        if CardType.CREATURE in getattr(obj, "card_types", set())
                    )
                    for p in game.players
                    if p is not ctrl
                ),
                default=0,
            )
            if opp_max > my_creature_count:
                source.prepared = True

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                on_announce=_on_announce,
            )
        )

    # ------------------------------------------------------------------
    # Swords to Plowshares (prepared spell copy)
    # ------------------------------------------------------------------

    def can_cast_prepared(self, game: "GameState", player: "Player") -> bool:
        """Return True if this card is prepared and *player* is its controller.

        This is the guard check for the Prepared mechanic: the controller
        may cast the Swords to Plowshares copy only while ``prepared`` is True.
        """
        ctrl = getattr(self, "controller", None)
        return bool(self.prepared and ctrl is player)

    def cast_prepared(self, game: "GameState", player: "Player") -> None:
        """Cast the Swords to Plowshares copy as a prepared spell.

        The controller must choose a target creature; the spell is placed on
        the stack and resolves normally via the engine pipeline.  This method
        handles target selection and wires up ``resolve_prepared_spell`` as the
        ``on_resolve`` callback on the stack object.
        """
        from engine.stack import StackObject

        # Choose a target creature from any battlefield.
        creatures = [
            obj
            for p in game.players
            for obj in game.get_battlefield(p).get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        ]
        if not creatures:
            return

        target = player.choose(creatures, "Choose a target creature for Swords to Plowshares")
        if target not in creatures:
            return

        source = self

        def _on_resolve(g: "GameState") -> None:
            source.chosen_targets = [target]
            source.resolve_prepared_spell(g)

        stack_obj = StackObject(
            source=self,
            controller=player,
            on_resolve=_on_resolve,
        )
        game.stack.push(stack_obj)

    def resolve_prepared_spell(self, game: "GameState") -> None:
        """Resolve the Swords to Plowshares copy effect.

        Exiles the first target in ``chosen_targets`` and grants its
        controller life equal to its power.  Fires ``GainsLifeTriggeredEvent``
        so other cards observing life-gain triggers work correctly.
        Unprepares this card afterward.
        """
        from engine.game import exile

        targets = getattr(self, "chosen_targets", [])
        if targets:
            target = targets[0]
            power = getattr(target, "power", 0)
            target_controller = getattr(target, "controller", None)
            exile(game, target)
            if target_controller is not None and power > 0:
                target_controller.life += power
                game.trigger_manager.fire_event(
                    game, GainsLifeTriggeredEvent(player=target_controller, amount=power)
                )

        self.prepared = False

