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

    # ------------------------------------------------------------------
    # Cost reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Return {1} per instant/sorcery in controller's graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        count = 0
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count

    # ------------------------------------------------------------------
    # Attack trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the 'whenever attacks' trigger."""
        from engine.casting import cast_spell_free
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            attacker = getattr(event, "attacker", None) or getattr(event, "creature", None)
            return attacker is source

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            gy = game.get_graveyard(ctrl)
            valid = [
                c for c in gy.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not valid:
                return
            # "You may cast" — player may decline (choose_card returns None).
            spell: Any = None
            try:
                spell = ctrl.choose_card(valid, "Cast instant or sorcery from graveyard for free?")
            except Exception:
                spell = valid[0] if valid else None
            if spell is None:
                return
            # Mark for exile on resolution instead of going to graveyard.
            spell._exile_on_resolution = True  # type: ignore[attr-defined]
            # Cast from graveyard without paying mana cost.
            try:
                cast_spell_free(game, ctrl, spell, Zone.GRAVEYARD)
                # Resolve immediately by popping the stack object.
                if not game.stack.is_empty():
                    stack_obj = game.stack.pop()
                    stack_obj.on_resolve(game)
            except Exception:
                # If casting fails for any reason, clean up the flag.
                if hasattr(spell, "_exile_on_resolution"):
                    del spell._exile_on_resolution  # type: ignore[attr-defined]

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

