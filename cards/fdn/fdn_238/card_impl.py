"""Card implementation for Consuming Aberration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class ConsumingAberration(Creature):
    """Consuming Aberration — {3}{U}{B} — */* — Horror.

    Consuming Aberration's power and toughness are each equal to the
    number of cards in your opponents' graveyards.
    Whenever you cast a spell, each opponent reveals cards from the top
    of their library until they reveal a land card, then puts those
    cards into their graveyard.

    FDN collector number 238.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Consuming Aberration")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{B}"))
        kwargs.setdefault("subtypes", {"Horror"})
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 0)
        kwargs.setdefault(
            "rules_text",
            "Consuming Aberration's power and toughness are each equal "
            "to the number of cards in your opponents' graveyards.\n"
            "Whenever you cast a spell, each opponent reveals cards from "
            "the top of their library until they reveal a land card, then "
            "puts those cards into their graveyard.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register CDA for P/T and spell-cast mill trigger."""
        from engine.triggers import EventType, TriggerRegistration
        from engine.zones import move_to_zone

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # Characteristic-defining ability: P/T = cards in opponents' graveyards
        def _apply_cda(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or not _is_on_battlefield(game, source):
                return
            count = 0
            for player in game.players:
                if player is not ctrl:
                    gy = player.zones[Zone.GRAVEYARD]
                    count += len(list(gy.get_all()))
            source.base_power = count
            source.base_toughness = count

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.CHARACTERISTIC_DEFINING,
            apply=_apply_cda,
            duration=DURATION_PERMANENT,
        ))

        # Spell-cast trigger: mill opponents
        def _condition(game: Any, data: dict) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = data.get("player") or data.get("controller")
            return caster is ctrl

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            for player in game.players:
                if player is ctrl:
                    continue
                library = player.zones[Zone.LIBRARY]
                lib_cards = list(library.get_all())
                # Reveal from top (end of list) until a land card
                while lib_cards:
                    card = lib_cards.pop()  # top of library
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
                    card_types = getattr(card, "card_types", set())
                    if CardType.LAND in card_types:
                        break

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.SPELL_CAST,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
