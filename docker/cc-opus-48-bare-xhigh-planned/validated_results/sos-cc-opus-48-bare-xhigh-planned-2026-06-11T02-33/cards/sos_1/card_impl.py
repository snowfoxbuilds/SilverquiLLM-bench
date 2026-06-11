"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Avatar.

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
        """{1} less for each instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(
            1 for c in graveyard.get_all()
            if getattr(c, "card_types", set()) & _SPELL_TYPES
        )

    def register_triggers(self, game: "GameState") -> None:
        """Whenever this attacks, may free-cast an instant/sorcery from GY."""
        from engine.triggers import TriggerRegistration
        from engine.events import AttacksTriggeredEvent

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(game: "GameState") -> None:
            _attack_cast(game, source)

        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


def _attack_cast(game: "GameState", source: Any) -> None:
    """Resolve the attack trigger: free-cast a chosen instant/sorcery from GY.

    If only one legal target exists it is auto-selected (per the build plan);
    with several, the controller chooses one (returning ``None`` declines —
    the "may").  The cast spell is redirected to exile instead of the
    graveyard when it would resolve there.
    """
    from engine.casting import cast_spell_free
    from engine.events import SpellToGraveyardReplacementEvent
    from engine.replacement_effects import ReplacementEffect

    controller = getattr(source, "controller", None)
    if controller is None:
        return

    graveyard = game.get_graveyard(controller)
    legal = [
        c for c in graveyard.get_all()
        if getattr(c, "card_types", set()) & _SPELL_TYPES
    ]
    if not legal:
        return

    if len(legal) == 1:
        chosen = legal[0]
    else:
        chosen = controller.choose_card(
            legal, "cast an instant/sorcery from your graveyard for free"
        )
    if chosen is None or chosen not in legal:
        return

    # "If that spell would be put into your graveyard, exile it instead."
    # Register a one-shot replacement scoped to this specific spell object.
    def _cond(g: Any, ev: Any) -> bool:
        return ev.card is chosen

    def _repl(g: Any, ev: Any) -> Any:
        ev.destination = "exile"
        g.replacement_manager.unregister(chosen)
        return ev

    game.replacement_manager.register(ReplacementEffect(
        event_type=SpellToGraveyardReplacementEvent,
        source=chosen,
        condition=_cond,
        replacement=_repl,
        controller=controller,
    ))

    cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)
