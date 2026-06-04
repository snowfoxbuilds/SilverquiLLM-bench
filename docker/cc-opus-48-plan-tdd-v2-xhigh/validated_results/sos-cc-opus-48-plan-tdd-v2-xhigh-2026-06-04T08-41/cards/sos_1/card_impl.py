"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}


def _graveyard_instants_sorceries(game: "GameState", player: Any) -> list:
    if player is None:
        return []
    out = []
    for obj in player.zones[Zone.GRAVEYARD].get_all():
        if getattr(obj, "card_types", set()) & _INSTANT_SORCERY:
            out.append(obj)
    return out


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 Legendary Avatar.

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
        return len(_graveyard_instants_sorceries(game, self.controller))

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _on_attack(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            candidates = _graveyard_instants_sorceries(g, ctrl)
            if not candidates:
                return
            if not ctrl.choose_yes_no(
                "Cast an instant or sorcery from your graveyard?"
            ):
                return
            chosen = ctrl.choose_card(candidates, "Choose a spell to cast")
            if chosen is None or chosen not in candidates:
                return
            chosen._exile_on_resolve = True
            from engine.casting import cast_spell_free

            cast_spell_free(g, ctrl, chosen, Zone.GRAVEYARD)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=lambda g, e: e.creature is source,
                effect=_on_attack,
                source=self,
                controller=controller,
            )
        )
