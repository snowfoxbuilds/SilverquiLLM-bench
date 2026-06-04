"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    Costs {1} less to cast for each instant and sorcery card in your
    graveyard. Reach. Whenever The Dawning Archaic attacks, you may cast
    target instant or sorcery card from your graveyard without paying its
    mana cost. If that spell would be put into your graveyard, exile it
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
        controller = self.controller
        if controller is None:
            return 0
        gy = game.get_graveyard(controller)
        return sum(1 for c in gy.get_all() if _is_instant_or_sorcery(c))

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return getattr(event, "creature", None) is source

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            gy = game.get_graveyard(ctrl)
            eligible = [c for c in gy.get_all() if _is_instant_or_sorcery(c)]
            if not eligible:
                return
            if not ctrl.choose_yes_no(
                "Cast an instant or sorcery from your graveyard for free?"
            ):
                return
            chosen = ctrl.choose_card(eligible, "Choose a spell to cast for free")
            if chosen is None:
                return

            cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            self._redirect_to_exile(game, chosen)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    @staticmethod
    def _redirect_to_exile(game: "GameState", spell_card: Any) -> None:
        """Wrap the just-cast spell so it is exiled instead of going to a
        graveyard when it resolves."""
        spell_obj = game.stack.peek()
        if spell_obj is None or getattr(spell_obj, "source", None) is not spell_card:
            return

        original = spell_obj.on_resolve

        def _wrapped(g: "GameState") -> None:
            from engine.game import exile

            original(g)
            owner = getattr(spell_card, "owner", None)
            if owner is not None and g.get_graveyard(owner).contains(spell_card):
                exile(g, spell_card)

        spell_obj.on_resolve = _wrapped
