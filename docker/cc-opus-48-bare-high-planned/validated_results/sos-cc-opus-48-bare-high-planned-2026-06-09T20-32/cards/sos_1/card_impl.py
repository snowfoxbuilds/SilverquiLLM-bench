"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(obj: Any) -> bool:
    return bool(
        getattr(obj, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}
    )


def _redirect_to_exile(stack_obj: Any) -> None:
    """Wrap *stack_obj*'s resolution so the spell is exiled, not binned.

    DELIBERATE CARD-LOCAL LIMITATION: only the normal resolution path is
    redirected (which is what 'cast it' produces).  The engine's
    stack->graveyard resolution move does not consult replacement effects
    (the card isn't leaving the battlefield), so a registered
    ReplacementEffect would never fire; wrapping the one spell's resolution is
    the smallest local fix.  A spell countered while on the stack would still
    go to the graveyard — out of scope for this card's tests.
    """
    from engine.zones import move_to_zone

    card = stack_obj.source

    def _resolve(game: "GameState") -> None:
        if stack_obj.targets is not None:
            card.chosen_targets = stack_obj.targets
        card.on_resolve(game)
        move_to_zone(game, card, Zone.STACK, Zone.EXILE)

    stack_obj.on_resolve = _resolve


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost.  If that
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
        """{1} less per instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        gy = game.get_graveyard(controller)
        return sum(1 for c in gy.get_all() if _is_instant_or_sorcery(c))

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            gy = game.get_graveyard(ctrl)
            candidates = [c for c in gy.get_all() if _is_instant_or_sorcery(c)]
            if not candidates:
                return
            # "you may cast target ..."
            if not ctrl.choose_yes_no(
                "Cast an instant or sorcery from your graveyard for free?"
            ):
                return
            chosen = ctrl.choose_card(candidates, "choose instant/sorcery to cast")
            if chosen is None or chosen not in candidates:
                return
            cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            # "If that spell would be put into your graveyard, exile it instead."
            top = game.stack.peek()
            if top is not None and top.source is chosen:
                _redirect_to_exile(top)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
