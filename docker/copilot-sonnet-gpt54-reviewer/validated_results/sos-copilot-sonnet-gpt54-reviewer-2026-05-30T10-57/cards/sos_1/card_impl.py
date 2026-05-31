"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar — 7/7

    Reach.
    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.
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
            "Reach.\n"
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant "
            "or sorcery card from your graveyard without paying its mana cost. "
            "If that spell would be put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Return 1 per instant/sorcery card in controller's graveyard."""
        from engine.types import Zone

        controller = self.controller
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD]
        count = 0
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger: cast instant/sorcery from graveyard for free."""
        from engine.casting import cast_spell_free
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration
        from engine.types import Zone

        source = self
        controller = self.controller or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            ctrl = source.controller or game.active_player
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            candidates = [
                c for c in graveyard.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not candidates:
                return
            # Ask the player to choose a spell to cast.
            chosen = ctrl.choose(candidates, "Choose an instant or sorcery to cast from your graveyard")
            if chosen is None:
                return
            # Mark so exile replacement fires on resolution.
            chosen.exile_instead_of_graveyard = True
            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except Exception:
                # Roll back flag on failure.
                chosen.exile_instead_of_graveyard = False

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def register_replacement_effects(self, game: "GameState") -> None:
        """Register exile replacement: redirect flagged spells from graveyard to exile."""
        from engine.replacement_effects import ReplacementEffect
        from engine.events import MoveToGraveyardReplacementEvent

        source = self

        def _condition(game: Any, event: Any) -> bool:
            card = getattr(event, "card_being_moved", None)
            if card is None:
                return False
            return getattr(card, "exile_instead_of_graveyard", False)

        def _replacement(game: Any, event: Any) -> Any:
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=source,
                condition=_condition,
                replacement=_replacement,
                controller=self.controller,
            )
        )
