"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


def _power_one_creatures(player: Any) -> list[Any]:
    """Return creatures *player* controls with power 1 or greater."""
    result: list[Any] = []
    bf = player.zones[Zone.BATTLEFIELD]
    for obj in bf.get_all():
        if CardType.CREATURE not in getattr(obj, "card_types", set()):
            continue
        if getattr(obj, "power", 0) >= 1:
            result.append(obj)
    return result


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Elder Dragon.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1.

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Grant casualty 1 to the controller's instant/sorcery spells."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            card = getattr(event, "card", None) or getattr(
                getattr(event, "spell", None), "source", None
            )
            if card is None or not _is_instant_or_sorcery(card):
                return False
            if getattr(event, "controller", None) is not source.controller:
                return False
            if not _power_one_creatures(source.controller):
                return False
            # Stash the spell so the effect (which only receives ``game``)
            # can find it when it resolves.
            source._casualty_spell = getattr(event, "spell", None)
            return True

        def _effect(game: "GameState") -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell

            controller = source.controller
            spell_obj = getattr(source, "_casualty_spell", None)
            if controller is None or spell_obj is None:
                return

            creatures = _power_one_creatures(controller)
            if not creatures:
                return

            use = controller.choose_yes_no(
                "Pay casualty 1 — sacrifice a creature with power 1 or "
                "greater to copy the spell?"
            )
            if not use:
                return

            chosen = controller.choose_card(
                creatures, "Choose a creature to sacrifice for casualty"
            )
            if chosen is None or chosen not in creatures:
                return
            sacrifice(game, controller, chosen)

            copy = copy_spell(game, spell_obj, controller)
            game.stack.push(copy)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
