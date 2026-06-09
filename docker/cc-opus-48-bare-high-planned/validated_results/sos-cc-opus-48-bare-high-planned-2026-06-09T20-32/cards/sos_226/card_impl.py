"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1.  (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\nEach instant and sorcery spell you cast has "
            "casualty 1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not ctrl or ctrl is None:
                return False
            spell = getattr(event, "spell", None)
            card = spell.source if spell is not None else getattr(event, "card", None)
            if card is None:
                return False
            if not (getattr(card, "card_types", set())
                    & {CardType.INSTANT, CardType.SORCERY}):
                return False
            if not game.get_battlefield(ctrl).contains(source):
                return False
            source._casualty_spell = spell
            return True

        def _effect(game: "GameState") -> None:
            from engine.game import sacrifice

            ctrl = getattr(source, "controller", None)
            spell_so = getattr(source, "_casualty_spell", None)
            if ctrl is None or spell_so is None:
                return
            candidates = [
                c for c in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not candidates:
                return
            # "you may sacrifice a creature with power 1 or greater"
            if not ctrl.choose_yes_no("Pay casualty 1 (sacrifice a creature)?"):
                return
            chosen = ctrl.choose_card(candidates, "sacrifice a creature (power >= 1)")
            if chosen is None or chosen not in candidates:
                return
            sacrifice(game, ctrl, chosen)
            # "copy the spell"; declining to choose new targets is legal, so the
            # copy keeps the original targets (minimal — no new-target prompt).
            if spell_so in game.stack._items:
                game.stack.push(copy_spell(game, spell_so, ctrl))

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
