"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar 7/7.

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
        """Costs {1} less per instant/sorcery in controller's graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD]
        return sum(
            1 for c in graveyard.get_all()
            if CardType.INSTANT in getattr(c, "card_types", set())
            or CardType.SORCERY in getattr(c, "card_types", set())
        )

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free, CastingError
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            graveyard = ctrl.zones[Zone.GRAVEYARD]
            candidates = [
                c for c in graveyard.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not candidates:
                return

            # Player chooses which instant/sorcery to cast (or None to decline).
            chosen = ctrl.choose_card(candidates, "Cast instant/sorcery from graveyard for free?")
            if chosen is None:
                return

            # Mark the spell: if it would go to graveyard on resolution, exile instead.
            chosen._exile_instead_of_graveyard = True
            try:
                cast_spell_free(g, ctrl, chosen, Zone.GRAVEYARD)
            except (CastingError, Exception):
                # Rollback the flag if casting fails (e.g. no legal targets).
                chosen._exile_instead_of_graveyard = False

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
