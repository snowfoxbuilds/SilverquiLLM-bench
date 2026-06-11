"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

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

    def cost_reduction(self, game: GameState) -> int:
        """{1} less per instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD]
        return sum(
            1
            for card in graveyard.get_all()
            if getattr(card, "card_types", set())
            & {CardType.INSTANT, CardType.SORCERY}
        )

    def register_triggers(self, game: GameState) -> None:
        """On attack: may cast an instant/sorcery from graveyard for free."""
        from engine.events import (
            AttacksTriggeredEvent,
            MoveToGraveyardReplacementEvent,
        )
        from engine.replacement_effects import ReplacementEffect
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            candidates = [
                c
                for c in graveyard.get_all()
                if getattr(c, "card_types", set())
                & {CardType.INSTANT, CardType.SORCERY}
            ]
            if not candidates:
                return
            if len(candidates) == 1:
                # Sole legal target — auto-select instead of prompting.
                chosen = candidates[0]
            else:
                chosen = ctrl.choose_card(
                    candidates,
                    "Cast an instant or sorcery card from your graveyard "
                    "without paying its mana cost (None to decline)",
                )
            if chosen is None or chosen not in candidates:
                return

            spell = chosen

            def _repl_condition(game: Any, event: Any) -> bool:
                return event.card is spell

            def _replacement(game: Any, event: Any) -> Any:
                event.destination = "exile"
                # One-shot: the redirect applies only to "that spell".
                game.replacement_manager.unregister(spell)
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=spell,
                    condition=_repl_condition,
                    replacement=_replacement,
                    controller=ctrl,
                )
            )

            try:
                cast_spell_free(game, ctrl, spell, Zone.GRAVEYARD)
            except CastingError:
                # Could not legally cast (e.g. no legal target for the
                # spell itself) — withdraw the exile-instead redirect.
                game.replacement_manager.unregister(spell)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
