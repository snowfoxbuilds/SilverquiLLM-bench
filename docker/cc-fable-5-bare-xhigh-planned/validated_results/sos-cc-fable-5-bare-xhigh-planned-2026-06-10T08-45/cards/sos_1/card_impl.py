"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


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
        return sum(
            1
            for card in game.get_graveyard(controller).get_all()
            if _SPELL_TYPES & getattr(card, "card_types", set())
        )

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free
            from engine.replacement_effects import ReplacementEffect

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            legal = [
                c
                for c in game.get_graveyard(ctrl).get_all()
                if _SPELL_TYPES & getattr(c, "card_types", set())
            ]
            if not legal:
                return
            if len(legal) == 1:
                chosen = legal[0]
            else:
                try:
                    chosen = ctrl.choose_card(
                        legal,
                        "Cast an instant or sorcery from your graveyard "
                        "without paying its mana cost (None to decline)",
                    )
                except Exception:
                    chosen = None
            if chosen is None or chosen not in legal:
                return

            # One-shot "exile it instead" for this casting of the spell.
            def _repl_condition(g: Any, ev: Any) -> bool:
                return ev.card is chosen

            def _replacement(g: Any, ev: Any) -> Any:
                ev.destination = "exile"
                g.replacement_manager.unregister(chosen)
                return ev

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=chosen,
                    condition=_repl_condition,
                    replacement=_replacement,
                    controller=ctrl,
                )
            )
            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except CastingError:
                # Spell could not legally be cast — undo the replacement.
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
