"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost.  If
    that spell would be put into your graveyard, exile it instead.

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
        return sum(
            1
            for c in game.get_graveyard(controller).get_all()
            if getattr(c, "card_types", set()) & _INSTANT_SORCERY
        )

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.events import (
            AttacksTriggeredEvent,
            MoveToGraveyardReplacementEvent,
        )
        from engine.replacement_effects import ReplacementEffect
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            graveyard = game.get_graveyard(ctrl)
            candidates = [
                c
                for c in graveyard.get_all()
                if getattr(c, "card_types", set()) & _INSTANT_SORCERY
            ]
            if not candidates:
                return

            # Target selection: a single legal target is auto-selected; the
            # "may" is one prompt either way (yes/no, or choose-with-decline).
            if len(candidates) == 1:
                spell = candidates[0]
                if not ctrl.choose_yes_no(
                    f"Cast {spell.name} from your graveyard without paying "
                    "its mana cost?"
                ):
                    return
            else:
                spell = ctrl.choose_card(
                    candidates,
                    "Cast target instant or sorcery card from your graveyard "
                    "without paying its mana cost (None to decline)",
                )
                if spell is None or spell not in candidates:
                    return

            try:
                cast_spell_free(game, ctrl, spell, Zone.GRAVEYARD)
            except CastingError:
                return

            # One-shot delayed replacement: if that spell would be put into
            # your graveyard, exile it instead.
            sentinel = object()

            def _repl_condition(g: Any, event: Any) -> bool:
                return event.card is spell

            def _replacement(g: Any, event: Any) -> Any:
                event.destination = "exile"
                g.replacement_manager.unregister(sentinel)
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=sentinel,
                    condition=_repl_condition,
                    replacement=_replacement,
                    controller=ctrl,
                )
            )

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
