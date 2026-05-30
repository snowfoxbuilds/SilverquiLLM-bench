"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Elder Dragon — Legendary.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1.  (As you cast
    that spell, you may sacrifice a creature with power 1 or greater.  When
    you do, copy the spell and you may choose new targets for the copy.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\nEach instant and sorcery spell you cast has "
            "casualty 1.",
        )
        super().__init__(**kwargs)
        self.colors = ["B", "W"]

    def register_triggers(self, game: "GameState") -> None:
        """Grant casualty 1 to instant/sorcery spells the controller casts."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _is_casualty_spell(game: Any, event: SpellCastTriggeredEvent) -> bool:
            card = event.card
            if card is None:
                return False
            types = getattr(card, "card_types", set())
            if CardType.INSTANT not in types and CardType.SORCERY not in types:
                return False
            if event.controller is not source.controller:
                return False
            # Stash the spell so the (game-only) effect callback can read it.
            source._casualty_spell = event.spell
            return True

        def _casualty_effect(game: "GameState") -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell
            from engine.types import Zone

            spell = getattr(source, "_casualty_spell", None)
            source._casualty_spell = None
            ctrl = source.controller
            if spell is None or ctrl is None:
                return

            eligible = [
                c
                for c in ctrl.zones[Zone.BATTLEFIELD].get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not eligible:
                return

            if not ctrl.choose_yes_no("Casualty 1 — sacrifice a creature?"):
                return

            chosen = ctrl.choose(eligible, "Choose a creature to sacrifice (casualty)")
            if chosen is None or chosen not in eligible:
                return

            sacrifice(game, ctrl, chosen)
            copy_obj = copy_spell(game, spell, ctrl)
            game.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_is_casualty_spell,
                effect=_casualty_effect,
                source=self,
                controller=controller,
            )
        )
