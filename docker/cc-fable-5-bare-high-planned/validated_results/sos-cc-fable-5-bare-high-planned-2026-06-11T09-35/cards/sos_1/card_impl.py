"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar — 7/7.

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
        # Spells cast via the attack trigger — the exile-instead replacement
        # applies only to these (identity-based).
        self._free_cast_spells: list[Any] = []

    def cost_reduction(self, game: "GameState") -> int:
        """{1} less for each instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        count = 0
        for card in game.get_graveyard(controller).get_all():
            if getattr(card, "card_types", set()) & {
                CardType.INSTANT, CardType.SORCERY,
            }:
                count += 1
        return count

    def register_triggers(self, game: "GameState") -> None:
        """Attack trigger: may cast an instant/sorcery from your graveyard free."""
        from engine.casting import CastingError, cast_spell_free
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            candidates = [
                c for c in game.get_graveyard(controller).get_all()
                if getattr(c, "card_types", set()) & {
                    CardType.INSTANT, CardType.SORCERY,
                }
            ]
            if not candidates:
                return  # "may" with no legal target — nothing happens
            if len(candidates) == 1:
                chosen = candidates[0]  # sole legal target — auto-select
            else:
                chosen = controller.choose_card(
                    candidates,
                    "Cast an instant or sorcery from your graveyard for free? "
                    "(None to decline)",
                )
            if chosen is None or chosen not in candidates:
                return
            try:
                cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)
            except CastingError:
                return  # e.g. counterspell with nothing on the stack
            source._free_cast_spells.append(chosen)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def register_replacement_effects(self, game: "GameState") -> None:
        """Exile-instead replacement for spells cast via the attack trigger.

        Deliberate limitation: the replacement lives only while The Dawning
        Archaic is on the battlefield (it is unregistered when it leaves).
        """
        from engine.events import MoveToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return any(event.card is c for c in source._free_cast_spells)

        def _replacement(game: Any, event: Any) -> Any:
            event.destination = "exile"
            return event

        game.replacement_manager.register(ReplacementEffect(
            event_type=MoveToGraveyardReplacementEvent,
            source=self,
            condition=_condition,
            replacement=_replacement,
            controller=getattr(self, "controller", None),
        ))
