"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return bool(types & {CardType.INSTANT, CardType.SORCERY})


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
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """{1} less for each instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        gy = game.get_graveyard(controller)
        return sum(1 for c in gy.get_all() if _is_instant_or_sorcery(c))

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return getattr(event, "creature", None) is source

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            gy = game.get_graveyard(ctrl)
            candidates = [c for c in gy.get_all() if _is_instant_or_sorcery(c)]
            if not candidates:
                return
            # "may" — optional.
            if not ctrl.choose_yes_no(
                "Cast an instant or sorcery from your graveyard for free?"
            ):
                return
            chosen = ctrl.choose_card(candidates, "Choose a spell to cast")
            if chosen is None or not gy.contains(chosen):
                return
            _free_cast_with_exile(game, ctrl, chosen)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


def _free_cast_with_exile(game: "GameState", controller: Any, spell: Any) -> None:
    """Cast *spell* from the graveyard for free; if it would go to the
    graveyard on resolution, exile it instead.

    Implemented card-local by wrapping the spell's stack resolution: the
    engine does not route a spell's stack->graveyard move through the
    replacement system, so a replacement effect would never fire here.
    LIMITATION: a *countered* free-cast copy still goes to the graveyard
    (only the resolve path is redirected) — an edge of an edge.
    """
    from engine.casting import cast_spell_free
    from engine.game import exile

    try:
        cast_spell_free(game, controller, spell, Zone.GRAVEYARD)
    except Exception:
        return

    stack_obj = game.stack.peek()
    if stack_obj is None or stack_obj.source is not spell:
        return

    original = stack_obj.on_resolve

    def _wrapped(g: "GameState") -> None:
        original(g)
        gy = controller.zones[Zone.GRAVEYARD]
        if gy.contains(spell):
            exile(g, spell)

    stack_obj.on_resolve = _wrapped
