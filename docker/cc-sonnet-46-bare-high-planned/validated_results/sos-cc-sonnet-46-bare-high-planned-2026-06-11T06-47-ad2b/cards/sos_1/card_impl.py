"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 Legendary Avatar.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
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
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault("keywords", Keyword.REACH)
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
        """Costs {1} less per instant/sorcery in controller's graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        count = sum(
            1 for card in graveyard.get_all()
            if CardType.INSTANT in getattr(card, "card_types", set())
            or CardType.SORCERY in getattr(card, "card_types", set())
        )
        return count

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger: may cast instant/sorcery from graveyard."""
        from engine.casting import cast_spell_free
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            graveyard = game.get_graveyard(ctrl)
            legal = [
                c for c in graveyard.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not legal:
                return
            # "may" — player chooses; script exhaustion or None = decline
            try:
                chosen = ctrl.choose_card(legal, "cast from graveyard for free?")
            except Exception:
                return
            if chosen is None or chosen not in legal:
                return

            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except Exception:
                return

            # Wrap the StackObject's on_resolve so that if the spell goes to
            # the graveyard after resolving, it goes to exile instead.
            # (Card-local limitation: countered spells go to GY, not exile.)
            top_obj = game.stack.peek()
            if top_obj is not None and top_obj.source is chosen:
                _wrap_exile_instead(game, top_obj, chosen, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


def _wrap_exile_instead(
    game: Any, stack_obj: Any, card: Any, controller: Any
) -> None:
    """Wrap stack_obj.on_resolve to move the card to exile if it would go to GY."""
    original = stack_obj.on_resolve

    def _on_resolve_with_exile(g: Any) -> None:
        original(g)
        # After resolution, check if card ended up in graveyard; redirect to exile.
        owner = getattr(card, "owner", controller) or controller
        gy = g.get_graveyard(owner)
        if gy.contains(card):
            gy.remove(card)
            g.get_exile(owner).add(card)

    stack_obj.on_resolve = _on_resolve_with_exile
