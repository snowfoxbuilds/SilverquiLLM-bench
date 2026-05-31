"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon — 4/4.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1.
    (As you cast that spell, you may sacrifice a creature with power 1 or
    greater. When you do, copy the spell and you may choose new targets
    for the copy.)
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
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1.\n"
            "(As you cast that spell, you may sacrifice a creature with power "
            "1 or greater. When you do, copy the spell and you may choose new "
            "targets for the copy.)",
        )
        super().__init__(**kwargs)

    def grant_casualty_to_spell(self, spell: Any) -> None:
        """Grant casualty 1 to an instant or sorcery spell."""
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
            spell.has_casualty = True
            spell.casualty_power_req = 1

    def pay_casualty(
        self, game: "GameState", spell: Any, sacrifice_target: Any
    ) -> None:
        """Pay casualty by sacrificing a creature; copy the spell onto the stack.

        Parameters:
            game: Current game state.
            spell: The spell being cast (instant/sorcery with casualty).
            sacrifice_target: The creature to sacrifice.
        """
        from engine.game import sacrifice
        from engine.stack import StackObject, copy_spell

        controller = self.controller
        if controller is None:
            controller = getattr(spell, "controller", None)

        # Sacrifice the creature.
        sac_player = getattr(sacrifice_target, "controller", controller)
        sacrifice(game, sac_player, sacrifice_target)

        # Find the spell's StackObject on the stack.
        spell_obj = None
        for obj in game.stack.objects():
            if obj.source is spell:
                spell_obj = obj
                break

        if spell_obj is not None and controller is not None:
            # Create a copy and push it onto the stack.
            copy_obj = copy_spell(game, spell_obj, controller)
            game.stack.push(copy_obj)

    def register_triggers(self, game: "GameState") -> None:
        """Register SpellCast trigger to grant casualty to instants/sorceries."""
        source = self

        def _condition(game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            controller = source.controller
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            spell_controller = getattr(spell, "controller", None)
            if spell_controller is not controller:
                return False
            card_types = getattr(spell, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _effect(game: "GameState") -> None:
            # Grant casualty is done at cast-time (see cast pipeline).
            pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller,
            )
        )
