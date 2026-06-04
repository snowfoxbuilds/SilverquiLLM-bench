"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _instants_and_sorceries(player: "Player") -> list[Any]:
    """Instant/sorcery cards in *player*'s graveyard."""
    return [
        c
        for c in player.zones[Zone.GRAVEYARD].get_all()
        if getattr(c, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}
    ]


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Avatar.

    Costs {1} less per instant/sorcery card in your graveyard.  Reach.
    Whenever it attacks, you may cast target instant or sorcery card from
    your graveyard without paying its mana cost; if that spell would be put
    into your graveyard, exile it instead.
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
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        controller = self.controller
        if controller is None:
            return 0
        return len(_instants_and_sorceries(controller))

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            return getattr(event, "creature", None) is source

        def _effect(g: "GameState") -> None:
            self._cast_from_graveyard(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller,
            )
        )

    def _cast_from_graveyard(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free

        controller = self.controller
        if controller is None:
            return
        candidates = _instants_and_sorceries(controller)
        if not candidates:
            return
        if not controller.choose_yes_no(
            "Cast an instant or sorcery from your graveyard for free?"
        ):
            return
        chosen = controller.choose(candidates, "choose instant/sorcery to cast")
        if chosen is None or chosen not in candidates:
            return
        # Spell is exiled instead of going to the graveyard when it resolves.
        chosen._exile_instead_of_graveyard = True
        cast_spell_free(game, controller, chosen, from_zone=Zone.GRAVEYARD)
