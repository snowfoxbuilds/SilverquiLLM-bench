"""Card implementation for Emeritus of Truce // Swords to Plowshares (SOS #13)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent, GainsLifeTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 — Legendary Creature — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    (While it's prepared, you may cast a copy of its spell — Swords to
    Plowshares: exile target creature, its controller gains life equal to
    that creature's power. Doing so unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword(0))
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
        # Prepared mechanic state — starts unprepared.
        self.is_prepared: bool = False

    # ------------------------------------------------------------------
    # ETB trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the enters-the-battlefield trigger."""
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            """Only fire when this specific permanent enters."""
            return event.permanent is source

        def _effect(game: "GameState") -> None:
            """Create a 1/1 flying Inkling token for a target player, then
            check if prepared condition is met."""
            from engine.game import create_token

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Choose target player — default to controller if no script.
            target_player = ctrl
            try:
                target_player = ctrl.choose(game.players, "target player")
            except Exception:
                target_player = ctrl

            # Create the 1/1 white and black Inkling creature token with flying.
            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            create_token(game, target_player, token)

            # Check prepared condition: any opponent controls strictly more
            # creatures than this card's controller.
            my_creature_count = _count_creatures(game, ctrl)
            for player in game.players:
                if player is ctrl:
                    continue
                opp_count = _count_creatures(game, player)
                if opp_count > my_creature_count:
                    source.is_prepared = True
                    return
            # No opponent has more — remain unprepared.

        controller = getattr(self, "controller", None) or game.active_player
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
    # Swords to Plowshares spell copy
    # ------------------------------------------------------------------

    def cast_prepared_spell(self, game: "GameState", target_creature: Any) -> None:
        """Cast the Swords to Plowshares copy while prepared.

        If not prepared, this is a no-op.
        If prepared:
        - Exile the target creature from the battlefield.
        - Its controller gains life equal to the creature's base_power.
        - Set is_prepared = False.
        """
        if not self.is_prepared:
            return

        from engine.game import exile

        # Record power BEFORE exile (in case exile modifies state).
        # Use current in-game power (accounts for counters/modifications),
        # falling back to base_power if the power property is not available.
        power = getattr(target_creature, "power", getattr(target_creature, "base_power", 0))
        target_controller = getattr(target_creature, "controller", None)

        # Exile the creature.
        exile(game, target_creature)

        # Grant life to the exiled creature's controller.
        if target_controller is not None and power > 0:
            target_controller.life += power
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=target_controller, amount=power),
            )

        # Unprepare.
        self.is_prepared = False


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _count_creatures(game: "GameState", player: Any) -> int:
    """Return the number of creatures on the battlefield controlled by *player*."""
    battlefield = game.get_battlefield(player)
    count = 0
    for obj in battlefield.get_all():
        if CardType.CREATURE in getattr(obj, "card_types", set()):
            count += 1
    return count
