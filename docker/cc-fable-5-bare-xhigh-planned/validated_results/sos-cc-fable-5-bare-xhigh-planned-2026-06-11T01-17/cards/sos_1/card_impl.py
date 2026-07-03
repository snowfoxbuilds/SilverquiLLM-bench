"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

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

    def cost_reduction(self, game: GameState) -> int:
        """{1} less per instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        return sum(
            1
            for c in controller.zones[Zone.GRAVEYARD].get_all()
            if getattr(c, "card_types", set()) & _SPELL_TYPES
        )

    def register_triggers(self, game: GameState) -> None:
        """Attack trigger: may cast an instant/sorcery from the graveyard."""
        from engine.casting import CastingError, cast_spell_free
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            candidates = [
                c
                for c in ctrl.zones[Zone.GRAVEYARD].get_all()
                if getattr(c, "card_types", set()) & _SPELL_TYPES
            ]
            if not candidates:
                return
            # With exactly one legal target, auto-select it instead of
            # prompting; otherwise the answer is the card, or None to decline.
            if len(candidates) == 1:
                chosen = candidates[0]
            else:
                chosen = ctrl.choose_card(
                    candidates,
                    "Cast an instant or sorcery from your graveyard "
                    "without paying its mana cost (None to decline)",
                )
            if chosen is None or chosen not in candidates:
                return

            _register_exile_instead(game, chosen)
            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except CastingError:
                # Cast failed (e.g. no legal targets) — remove the pending
                # exile-instead replacement; the card stays in the graveyard.
                game.replacement_manager.unregister(chosen)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


def _register_exile_instead(game: GameState, spell: Any) -> None:
    """If *spell* would be put into a graveyard, exile it instead (one-shot)."""
    from engine.events import MoveToGraveyardReplacementEvent
    from engine.replacement_effects import ReplacementEffect

    def _condition(game: Any, event: Any) -> bool:
        return event.card is spell

    def _replacement(game: Any, event: Any) -> Any:
        event.destination = "exile"
        # One-shot: once redirected, the effect no longer applies.
        game.replacement_manager.unregister(spell)
        return event

    game.replacement_manager.register(
        ReplacementEffect(
            event_type=MoveToGraveyardReplacementEvent,
            source=spell,
            condition=_condition,
            replacement=_replacement,
            controller=getattr(spell, "controller", None),
        )
    )
