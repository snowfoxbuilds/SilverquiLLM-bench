"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast
    that spell, you may sacrifice a creature with power 1 or greater. When
    you do, copy the spell and you may choose new targets for the copy.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\nEach instant and sorcery spell you cast has "
            "casualty 1. (As you cast that spell, you may sacrifice a "
            "creature with power 1 or greater. When you do, copy the spell "
            "and you may choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        """Casualty 1 on the controller's instant and sorcery spells."""
        from engine.events import SpellCastTriggeredEvent
        from engine.game import sacrifice
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            spell_card = getattr(event, "card", None)
            if spell_card is None or spell_card is source:
                return False
            if not _SPELL_TYPES & getattr(spell_card, "card_types", set()):
                return False
            # Stash the StackObject for the effect (effects don't receive
            # the event) — fdn_248 pattern.
            source._pending_casualty_spell = event.spell
            return True

        def _effect(game: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            spell_so = getattr(source, "_pending_casualty_spell", None)
            if ctrl is None or spell_so is None:
                return
            source._pending_casualty_spell = None
            candidates = [
                c
                for c in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not candidates:
                return  # no creature with power >= 1 — casualty not taken
            # One prompt: the chosen creature, or None to decline.
            chosen = ctrl.choose_card(
                candidates, "Casualty 1 — sacrifice a creature with power 1 "
                "or greater (None to decline)"
            )
            if chosen is None or chosen not in candidates:
                return
            sacrifice(game, ctrl, chosen)
            # Deliberate limitation: the copy keeps the original's targets
            # (no new-target prompt).
            copy_obj = copy_spell(game, spell_so, ctrl)
            game.stack.push(copy_obj)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
