"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
    Reach
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
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic attacks, "
            "you may cast target instant or sorcery card from your graveyard "
            "without paying its mana cost. If that spell would be put into your "
            "graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce cost by 1 for each instant/sorcery in controller's graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD]
        count = 0
        for card in graveyard.get_all():
            ctypes = getattr(card, "card_types", set())
            if CardType.INSTANT in ctypes or CardType.SORCERY in ctypes:
                count += 1
        return count

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger."""
        from engine.triggers import TriggerRegistration
        from engine.events import AttacksTriggeredEvent

        source = self

        def _condition(game: Any, event: Any) -> bool:
            attacker = getattr(event, "creature", None) or getattr(event, "attacker", None)
            return attacker is source

        def _attack_effect(game: Any) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # Find instant/sorcery cards in controller's graveyard
            gy = controller.zones[Zone.GRAVEYARD]
            candidates = [
                c for c in gy.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not candidates:
                return

            # Ask controller if they want to cast one
            try:
                cast_it = controller.choose_yes_no("Cast an instant/sorcery from your graveyard?")
            except Exception:
                cast_it = False
            if not cast_it:
                return

            try:
                chosen = controller.choose_card(candidates, "Choose an instant or sorcery to cast")
            except Exception:
                chosen = candidates[0] if candidates else None
            if chosen is None:
                return

            # Mark the chosen card for exile instead of graveyard on resolution.
            chosen._exile_on_resolve = True  # type: ignore[attr-defined]

            # Cast the chosen card for free from the graveyard, then resolve it.
            try:
                from engine.casting import cast_spell_free, resolve_top
                cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)
                # Resolve the spell immediately (exile-on-resolve flag is read
                # by _resolve_spell to send it to exile instead of graveyard).
                resolve_top(game)
            except Exception:
                # If casting/resolving fails, clean up the exile flag.
                if hasattr(chosen, "_exile_on_resolve"):
                    del chosen._exile_on_resolve

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_attack_effect,
            source=self,
            controller=controller,
        ))

