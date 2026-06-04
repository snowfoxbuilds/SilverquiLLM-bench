"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _instants_sorceries_in_graveyard(game: "GameState", player: "Player") -> list[Any]:
    result: list[Any] = []
    if player is None:
        return result
    for card in game.get_graveyard(player).get_all():
        types = getattr(card, "card_types", set())
        if CardType.INSTANT in types or CardType.SORCERY in types:
            result.append(card)
    return result


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 Legendary Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach.
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard this turn, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach.\n"
            "Whenever The Dawning Archaic attacks, you may cast target "
            "instant or sorcery card from your graveyard without paying its "
            "mana cost. If that spell would be put into your graveyard, "
            "exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        return len(_instants_sorceries_in_graveyard(game, self.controller))

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: AttacksTriggeredEvent) -> bool:
            return (
                getattr(event, "creature", None) is source
                or getattr(event, "attacker", None) is source
            )

        def _effect(g: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free
            from engine.player import ScriptExhaustedError

            controller = getattr(source, "controller", None)
            if controller is None:
                return
            candidates = _instants_sorceries_in_graveyard(g, controller)
            if not candidates:
                return
            try:
                if not controller.choose_yes_no(
                    "cast an instant/sorcery from your graveyard for free?"
                ):
                    return
            except (ScriptExhaustedError, NotImplementedError):
                return
            try:
                chosen = controller.choose_card(candidates, "cast from graveyard")
            except (ScriptExhaustedError, NotImplementedError):
                chosen = candidates[0]
            if chosen is None or not g.get_graveyard(controller).contains(chosen):
                return
            chosen._exile_instead_of_graveyard = True
            try:
                cast_spell_free(g, controller, chosen, Zone.GRAVEYARD)
            except CastingError:
                pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller,
            )
        )
