"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _self_etb_condition(source: Any):
    """Return a condition callable that fires only when *source* enters the battlefield."""

    def _condition(game: Any, event: Any) -> bool:
        return event.permanent is source

    return _condition


class EmeritusOfTruce(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} // {W}
    Creature — Cat Cleric // Instant — 3/3

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell — Swords to
    Plowshares. Doing so unprepares it.)

    Swords to Plowshares: Exile target creature. Its controller gains life
    equal to its power.

    SOS collector number 13.
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
            "black Inkling creature token with flying. Then if an opponent controls "
            "more creatures than you, this creature becomes prepared. (While it's "
            "prepared, you may cast a copy of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        # Prepared mechanic state flag.
        self.is_prepared: bool = False

    # ------------------------------------------------------------------
    # Trigger registration
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the ETB trigger for token creation and prepared check."""
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _etb_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Check for pre-set test target; otherwise ask the controller.
            preset = getattr(source, "_etb_target_player", None)
            if preset is not None:
                target_player = preset
                del source._etb_target_player
            else:
                try:
                    target_player = ctrl.choose(game.players, "target player creates an Inkling token")
                except Exception:
                    target_player = ctrl

            _create_inkling_token(game, target_player)

            # Check prepared condition: does an opponent control more creatures?
            my_creatures = _creature_count(game, ctrl)
            for opponent in game.players:
                if opponent is ctrl:
                    continue
                if _creature_count(game, opponent) > my_creatures:
                    source.is_prepared = True
                    break

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_self_etb_condition(self),
                effect=_etb_effect,
                source=self,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Prepared mechanic — Swords to Plowshares
    # ------------------------------------------------------------------

    def cast_swords_to_plowshares(self, game: "GameState", target: Any) -> None:
        """Cast the prepared Swords to Plowshares copy targeting *target*.

        Exiles *target* and gives its controller life equal to its power.
        Unprepares this creature.  Calling this when ``is_prepared`` is
        ``False`` is a no-op.
        """
        if not self.is_prepared:
            return

        self.is_prepared = False

        # Only legal if target is a creature on the battlefield.
        on_bf = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                on_bf = True
                break
        if not on_bf:
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        # Life gain equals the creature's power *before* exile.
        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)

        from engine.game import exile

        exile(game, target)

        if target_controller is not None and power > 0:
            target_controller.life += power


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _create_inkling_token(game: "GameState", player: Any) -> None:
    """Create a 1/1 white-and-black Inkling creature token with flying."""
    from engine.game import create_token

    token = Creature(
        name="Inkling",
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        base_power=1,
        base_toughness=1,
        owner=player,
        controller=player,
    )
    create_token(game, player, token)


def _creature_count(game: "GameState", player: Any) -> int:
    """Return the number of creatures *player* controls on the battlefield."""
    bf = game.get_battlefield(player)
    return sum(
        1 for obj in bf.get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )
