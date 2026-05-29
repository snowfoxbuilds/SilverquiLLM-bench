"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — Legendary Creature — Elder Dragon (4/4).

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1.
    (As you cast that spell, you may sacrifice a creature with power 1 or
    greater. When you do, copy the spell and you may choose new targets for
    the copy.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", {Keyword.FLYING, Keyword.VIGILANCE})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.card import Instant, Sorcery
        from engine.events import SpellCastTriggeredEvent
        from engine.game import sacrifice
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        captured_spell: list[Any] = [None]

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if event.player is not ctrl:
                return False
            if not isinstance(event.card, (Instant, Sorcery)):
                return False
            captured_spell[0] = event.spell
            return True

        def _effect(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            spell = captured_spell[0]
            if spell is None:
                return

            # Find valid casualty targets: creatures controlled by Silverquill's
            # controller with power >= 1
            bf = game.get_battlefield(ctrl)
            candidates = [
                c for c in bf.get_all()
                if isinstance(c, Creature)
                and getattr(c, "base_power", 0) >= 1
            ]
            if not candidates:
                return

            # Ask controller if they want to use casualty
            try:
                want_casualty = ctrl._script.popleft()
            except Exception:
                want_casualty = False
            if not want_casualty:
                return

            # Ask which creature to sacrifice
            try:
                chosen = ctrl._script.popleft()
            except Exception:
                chosen = candidates[0]

            if chosen not in candidates:
                return

            sacrifice(game, ctrl, chosen)

            # Copy the spell and push it to the stack
            copy_obj = copy_spell(game, spell, ctrl)
            game.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=getattr(self, "controller", None),
            )
        )
