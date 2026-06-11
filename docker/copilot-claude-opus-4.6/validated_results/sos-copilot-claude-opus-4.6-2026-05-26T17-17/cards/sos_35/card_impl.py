"""Card implementation for Stirring Hopesinger."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class StirringHopesinger(Creature):
    """Stirring Hopesinger — {2}{W} — Creature — Bird Bard — 1/3.

    Flying, lifelink
    Repartee — Whenever you cast an instant or sorcery spell that targets
    a creature, put a +1/+1 counter on each creature you control.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stirring Hopesinger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Bird", "Bard"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.LIFELINK)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying, lifelink\nRepartee — Whenever you cast an instant or "
            "sorcery spell that targets a creature, put a +1/+1 counter on "
            "each creature you control.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the repartee trigger."""
        source = self

        def _condition(game: Any, event: Any) -> bool:
            # Must be cast by same controller
            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            if caster is not source.controller:
                return False
            # Must be instant or sorcery
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Must target a creature
            if getattr(spell, "targets_creature", False):
                return True
            # Check chosen_targets for creatures
            targets = getattr(event, "targets", None) or getattr(spell, "chosen_targets", None)
            if targets:
                for t in targets:
                    if CardType.CREATURE in getattr(t, "card_types", set()):
                        return True
            return False

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            bf = game.get_battlefield(controller)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.plus_one_counters = getattr(obj, "plus_one_counters", 0) + 1
                    if hasattr(obj, "_base_plus_one_counters"):
                        obj._base_plus_one_counters = obj.plus_one_counters

        trigger = TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=source,
            controller=source.controller,
        )
        game.trigger_manager.register(trigger)

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Handle spell cast events (backup for direct notification)."""
        # Check if this spell triggers repartee
        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if caster is not self.controller:
            return
        spell = getattr(event, "spell", None) or getattr(event, "card", None)
        if spell is None:
            return
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        # Check targets_creature flag
        targets_creature = getattr(spell, "targets_creature", False)
        if not targets_creature:
            targets = getattr(event, "targets", None) or getattr(spell, "chosen_targets", None)
            if targets:
                for t in targets:
                    if CardType.CREATURE in getattr(t, "card_types", set()):
                        targets_creature = True
                        break
        if not targets_creature:
            return
        # Put +1/+1 counter on each creature you control
        controller = self.controller
        if controller is None:
            return
        bf = game.get_battlefield(controller)
        for obj in bf.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                obj.plus_one_counters = getattr(obj, "plus_one_counters", 0) + 1
                if hasattr(obj, "_base_plus_one_counters"):
                    obj._base_plus_one_counters = obj.plus_one_counters
