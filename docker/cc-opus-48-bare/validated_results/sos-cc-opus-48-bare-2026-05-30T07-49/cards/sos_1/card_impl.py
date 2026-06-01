"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_instant_or_sorcery(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


def _graveyard_castables(game: Any, player: Any) -> list[Any]:
    return [
        c
        for c in game.get_graveyard(player).get_all()
        if _is_instant_or_sorcery(c)
    ]


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.  Reach.  Whenever The Dawning Archaic attacks, you may
    cast target instant or sorcery card from your graveyard without paying
    its mana cost.  If that spell would be put into your graveyard, exile it
    instead.

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
        """{1} less per instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        return len(_graveyard_castables(game, controller))

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            if not _is_on_battlefield(g, source):
                return False
            return getattr(event, "creature", None) is source

        def _effect(g: "GameState") -> None:
            source._attack_cast(g)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _attack_cast(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free

        controller = self.controller
        if controller is None:
            return

        candidates = _graveyard_castables(game, controller)
        if not candidates:
            return

        if not controller.choose_yes_no(
            "Cast an instant or sorcery from your graveyard for free?"
        ):
            return

        chosen = controller.choose_card(
            candidates, "instant or sorcery to cast from graveyard"
        )
        if chosen is None or chosen not in candidates:
            return

        # "If that spell would be put into your graveyard, exile it instead."
        chosen._exile_instead_of_graveyard = True
        cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)
