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
        """{1} less per instant/sorcery card in the caster's graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        gy = game.get_graveyard(controller)
        return sum(
            1
            for c in gy.get_all()
            if getattr(c, "card_types", set()) & _INSTANT_SORCERY
        )

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            gy = game.get_graveyard(ctrl)
            legal = [
                c
                for c in gy.get_all()
                if getattr(c, "card_types", set()) & _INSTANT_SORCERY
            ]
            if not legal:
                return
            # If exactly one legal target, auto-select it; otherwise let the
            # controller choose which (or None to decline the "may").
            if len(legal) == 1:
                target = legal[0]
            else:
                target = ctrl.choose_card(
                    legal,
                    "choose an instant or sorcery to cast from your graveyard",
                )
            if target is None or target not in legal:
                return
            # "If that spell would be put into your graveyard, exile it
            # instead" — per-cast flag honored by _resolve_spell.
            target._exile_instead_of_graveyard = True
            try:
                cast_spell_free(game, ctrl, target, Zone.GRAVEYARD)
            except Exception:
                # No legal targets for the chosen spell, etc. — the "may"
                # simply isn't taken; roll back leaves it in the graveyard.
                target._exile_instead_of_graveyard = False

        from engine.events import AttacksTriggeredEvent

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
