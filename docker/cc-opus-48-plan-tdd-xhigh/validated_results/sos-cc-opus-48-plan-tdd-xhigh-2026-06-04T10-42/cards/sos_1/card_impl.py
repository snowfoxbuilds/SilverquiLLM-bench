"""Card implementation for The Dawning Archaic (SOS #1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach.
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant "
            "or sorcery card from your graveyard without paying its mana cost. "
            "If that spell would be put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """{1} less per instant/sorcery card in the controller's graveyard."""
        ctrl = self.controller
        if ctrl is None:
            return 0
        return sum(
            1
            for card in ctrl.zones[Zone.GRAVEYARD].get_all()
            if _is_instant_or_sorcery(card)
        )

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _attacks_condition(game: Any, event: Any) -> bool:
            return getattr(event, "creature", None) is source

        def _attacks_effect(game: Any) -> None:
            from engine.casting import cast_spell_free

            ctrl = source.controller
            if ctrl is None:
                return
            spells = [
                card
                for card in ctrl.zones[Zone.GRAVEYARD].get_all()
                if _is_instant_or_sorcery(card)
            ]
            if not spells:
                return
            if not ctrl.choose_yes_no(
                "Cast an instant or sorcery from your graveyard for free?"
            ):
                return
            target = ctrl.choose_card(spells, "instant/sorcery to cast from graveyard")
            if target is None or target not in spells:
                return
            # "If that spell would be put into your graveyard, exile it instead."
            self._register_exile_replacement(game, target)
            cast_spell_free(game, ctrl, target, Zone.GRAVEYARD)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_attacks_condition,
                effect=_attacks_effect,
                source=self,
                controller=controller,
            )
        )

    @staticmethod
    def _register_exile_replacement(game: "GameState", card: Any) -> None:
        from engine.events import SpellResolvesToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        def _condition(game: Any, event: Any) -> bool:
            return getattr(event, "spell", None) is card

        def _replace(game: Any, event: Any) -> Any:
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=SpellResolvesToGraveyardReplacementEvent,
                source=card,
                condition=_condition,
                replacement=_replace,
                controller=getattr(card, "controller", None),
            )
        )
