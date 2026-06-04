"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _spell_card_types(spell: Any) -> set:
    """Extract the card types from a stack object or raw card."""
    card_types = getattr(spell, "card_types", None)
    if card_types:
        return card_types
    source = getattr(spell, "source", None)
    if source is not None:
        return getattr(source, "card_types", set())
    return set()


def _copy_spell_obj(game: "GameState", spell: Any, controller: Any) -> Any:
    """Build a stack object that is a copy of *spell*.

    Handles both the normal case where *spell* is a
    :class:`~engine.stack.StackObject` and the degenerate case where a raw
    card is supplied.
    """
    from engine.stack import StackObject, copy_spell

    if isinstance(spell, StackObject):
        return copy_spell(game, spell, controller)

    import copy as _copy

    copied = _copy.copy(spell)
    copied.controller = controller
    copied.owner = getattr(spell, "owner", controller)
    targets = list(getattr(spell, "chosen_targets", []) or [])
    obj = StackObject(source=copied, controller=controller, targets=targets)

    def _resolve(g: "GameState") -> None:
        copied.chosen_targets = obj.targets
        copied.on_resolve(g)

    obj.on_resolve = _resolve
    return obj


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon.

    Flying, vigilance. Each instant and sorcery spell you cast has casualty 1.

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
            "casualty 1. (As you cast that spell, you may sacrifice a creature "
            "with power 1 or greater. When you do, copy the spell and you may "
            "choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        # LIFO queue of spells awaiting casualty resolution. Because casualty
        # triggers always sit directly above their spell on the stack and the
        # stack resolves LIFO, popping from the end matches each trigger to the
        # spell that produced it (even with spells cast in response).
        pending: list[Any] = []

        def _condition(game: Any, event: Any) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            spell = getattr(event, "spell", None)
            if spell is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            spell_controller = getattr(spell, "controller", None)
            if spell_controller is not controller:
                return False
            types = _spell_card_types(spell)
            if not (CardType.INSTANT in types or CardType.SORCERY in types):
                return False
            pending.append(spell)
            return True

        def _effect(game: "GameState") -> None:
            if not pending:
                return
            spell = pending.pop()
            controller = source.controller
            if controller is None:
                return

            bf = controller.zones[Zone.BATTLEFIELD]
            creatures = [
                c
                for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not creatures:
                return

            # Casualty is optional ("you may").
            try:
                pay = controller.choose_yes_no(
                    "Pay casualty 1? (sacrifice a creature with power 1+ to copy the spell)"
                )
            except Exception:
                pay = False
            if not pay:
                return

            try:
                victim = controller.choose_card(
                    creatures, "Choose a creature to sacrifice for casualty"
                )
            except Exception:
                victim = None
            if victim is None or victim not in creatures:
                return

            from engine.game import sacrifice as _sacrifice

            _sacrifice(game, controller, victim)

            copy_obj = _copy_spell_obj(game, spell, controller)
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
