"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _instants_and_sorceries(cards: list[Any]) -> list[Any]:
    return [
        c for c in cards
        if getattr(c, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}
    ]


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """{1} less per instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD]
        return len(_instants_and_sorceries(graveyard.get_all()))

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = source.controller
            if ctrl is None:
                return
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            candidates = _instants_and_sorceries(graveyard.get_all())
            if not candidates:
                return
            if len(candidates) == 1:
                # Only one legal target — auto-select it (per plan).
                chosen = candidates[0]
            else:
                chosen = ctrl.choose_card(
                    candidates,
                    "Choose an instant or sorcery card in your graveyard to "
                    "cast without paying its mana cost (None to decline)",
                )
            if chosen is None or not graveyard.contains(chosen):
                return
            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except CastingError:
                return  # e.g. no legal target for the spell — stays put
            _register_exile_instead(game, chosen)

        game.trigger_manager.register(TriggerRegistration(
            event_type=_attacks_event(),
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


def _attacks_event() -> type:
    from engine.events import AttacksTriggeredEvent

    return AttacksTriggeredEvent


def _register_exile_instead(game: "GameState", spell: Any) -> None:
    """One-shot replacement: if *spell* would go to its graveyard from the
    stack after this cast, exile it instead.

    Limitation: a spell countered via a card-local _counter_spell helper
    bypasses move_to_zone and is not redirected.
    """
    from engine.events import MoveToGraveyardReplacementEvent
    from engine.replacement_effects import ReplacementEffect

    def _condition(game: Any, event: Any) -> bool:
        return event.card is spell

    def _replacement(game: Any, event: Any) -> Any:
        event.destination = "exile"
        game.replacement_manager.unregister(spell)  # one-shot
        return event

    game.replacement_manager.register(ReplacementEffect(
        event_type=MoveToGraveyardReplacementEvent,
        source=spell,
        condition=_condition,
        replacement=_replacement,
        controller=getattr(spell, "controller", None),
    ))
