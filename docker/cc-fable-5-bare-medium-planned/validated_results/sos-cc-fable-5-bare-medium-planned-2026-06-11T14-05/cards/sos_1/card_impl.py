"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


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
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
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
        """{1} less per instant/sorcery card in your graveyard (generic only)."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(1 for c in graveyard.get_all() if _is_instant_or_sorcery(c))

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            attacker = getattr(event, "attacker", None) or getattr(event, "creature", None)
            return attacker is source

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            graveyard = game.get_graveyard(ctrl)
            candidates = [c for c in graveyard.get_all() if _is_instant_or_sorcery(c)]
            if not candidates:
                return

            # "You may cast target ..." — with a single legal target it is
            # auto-selected; otherwise the controller picks (None declines).
            if len(candidates) == 1:
                chosen = candidates[0]
            else:
                try:
                    chosen = ctrl.choose_card(
                        candidates,
                        "cast an instant or sorcery from your graveyard for free",
                    )
                except Exception:
                    chosen = candidates[0]
            if chosen is None:
                return

            _register_exile_instead(game, chosen)

            from engine.casting import CastingError, cast_spell_free

            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except CastingError:
                # Spell could not legally be cast (e.g. counterspell with no
                # spell on the stack) — it stays in the graveyard.
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


def _register_exile_instead(game: "GameState", spell: Any) -> None:
    """One-shot replacement: if *spell* would hit a graveyard, exile it instead."""
    from engine.events import MoveToGraveyardReplacementEvent
    from engine.replacement_effects import ReplacementEffect

    def _condition(game: Any, event: Any) -> bool:
        return event.card is spell

    def _replacement(game: Any, event: Any) -> Any:
        event.destination = "exile"
        # Applies only to this cast of the spell.
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
