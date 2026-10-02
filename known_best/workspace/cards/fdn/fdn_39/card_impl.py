"""Card implementation for Grappling Kraken."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class GrapplingKraken(Creature):
    """Grappling Kraken — {4}{U}{U} — 5/6 — Kraken.

    Landfall — Whenever a land you control enters, tap target creature an
    opponent controls and put a stun counter on it.

    FDN collector number 39.

    This is a genuine triggered ability (not an ETB on the Kraken itself), so
    it is wired through ``register_triggers``. The engine's trigger channel has
    no cast-time targeting, so the target is chosen when the ability resolves
    via ``choose_object`` (a required target — the ability does nothing if no
    opponent creature exists).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Grappling Kraken")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault("subtypes", {"Kraken"})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault(
            "rules_text",
            "Landfall — Whenever a land you control enters, tap target "
            "creature an opponent controls and put a stun counter on it.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the landfall trigger: tap + stun an opponent's creature."""
        from engine.card_queries import choose_object
        from engine.game import add_counter, tap
        from engine.triggers import TriggerRegistration

        source = self

        def _landfall_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            permanent = getattr(event, "permanent", None)
            if permanent is None:
                return False
            if CardType.LAND not in getattr(permanent, "card_types", set()):
                return False
            perm_ctrl = getattr(permanent, "controller", None)
            if perm_ctrl is None:
                return game.get_battlefield(ctrl).contains(permanent)
            return perm_ctrl is ctrl

        def _landfall_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            candidates = [
                obj
                for player in game.players
                if player is not ctrl
                for obj in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            ]
            if not candidates:
                return
            target = choose_object(
                game,
                ctrl,
                candidates,
                "tap target creature an opponent controls",
                source_card=source,
            )
            if target is None:
                return
            # Tap via the engine helper so tap-triggered machinery can fire.
            tap(game, target)
            add_counter(game, target, "stun", 1)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_landfall_condition,
                effect=_landfall_effect,
                source=self,
                controller=controller,
            )
        )
