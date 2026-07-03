"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar 7/7.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard. Reach. Whenever The Dawning Archaic attacks, you may cast
    target instant or sorcery card from your graveyard without paying its mana
    cost. If that spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost(generic=10))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery card in "
            "your graveyard.\nReach\nWhenever The Dawning Archaic attacks, you may "
            "cast target instant or sorcery card from your graveyard without paying "
            "its mana cost. If that spell would be put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """1 less per instant/sorcery in your graveyard (generic only)."""
        controller = self.controller
        if controller is None:
            return 0
        gy = controller.zones[Zone.GRAVEYARD]
        count = 0
        for card in gy.get_all():
            types = getattr(card, "card_types", set())
            if CardType.INSTANT in types or CardType.SORCERY in types:
                count += 1
        return count

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger — may cast instant/sorcery from graveyard free."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _attack_condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _attack_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Find instant/sorcery cards in controller's graveyard.
            gy = ctrl.zones[Zone.GRAVEYARD]
            legal = [
                c for c in gy.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not legal:
                return

            # Let player choose (or decline by choosing None).
            try:
                chosen = ctrl.choose_card(legal, "Choose an instant/sorcery to cast for free (or None to decline)")
            except Exception:
                return

            if chosen is None or chosen not in legal:
                return

            # Register one-shot exile-instead replacement for this specific spell.
            _register_exile_replacement(game, chosen, ctrl)

            # Cast from graveyard for free.
            from engine.casting import cast_spell_free, CastingError
            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except CastingError:
                # If cast fails (e.g. no legal targets), remove the replacement.
                game.replacement_manager.unregister(chosen)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_attack_condition,
                effect=_attack_effect,
                source=self,
                controller=controller,
            )
        )


def _register_exile_replacement(
    game: "GameState", spell: Any, controller: Any
) -> None:
    """Register a one-shot replacement that exiles *spell* instead of graveyard."""

    def _condition(game: Any, event: Any) -> bool:
        # Only applies to this specific spell card moving to graveyard.
        return getattr(event, "_source_card", None) is spell

    def _replacement(game: Any, event: Any) -> Any:
        event.destination = "exile"
        # Self-unregister after firing once.
        game.replacement_manager.unregister(spell)
        return event

    game.replacement_manager.register(
        ReplacementEffect(
            event_type=MoveToGraveyardReplacementEvent,
            source=spell,
            condition=_condition,
            replacement=_replacement,
            controller=controller,
        )
    )
