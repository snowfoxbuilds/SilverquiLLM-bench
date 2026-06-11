"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Avatar.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost(generic=10))
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic attacks, "
            "you may cast target instant or sorcery card from your graveyard without "
            "paying its mana cost. If that spell would be put into your graveyard, "
            "exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Costs {1} less for each instant or sorcery in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(
            1
            for c in graveyard.get_all()
            if CardType.INSTANT in getattr(c, "card_types", set())
            or CardType.SORCERY in getattr(c, "card_types", set())
        )

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger for graveyard free-cast."""
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

            graveyard = g.get_graveyard(ctrl)
            castable = [
                c
                for c in graveyard.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]

            if not castable:
                return

            # Auto-select if only one legal target; otherwise prompt player.
            if len(castable) == 1:
                chosen = castable[0]
                # Still let player opt in via "may"
                try:
                    if not ctrl.choose_yes_no(
                        f"Cast {getattr(chosen, 'name', 'card')} from graveyard for free?"
                    ):
                        return
                except Exception:
                    return
            else:
                # Player chooses; None means decline
                try:
                    if not ctrl.choose_yes_no("Cast an instant/sorcery from graveyard?"):
                        return
                    chosen = ctrl.choose_card(castable, "Choose instant/sorcery to cast")
                except Exception:
                    return

            if chosen is None:
                return

            # Register exile-instead replacement before casting.
            _register_exile_replacement(g, chosen, source)

            from engine.casting import cast_spell_free
            try:
                cast_spell_free(g, ctrl, chosen, Zone.GRAVEYARD)
            except Exception:
                pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


def _register_exile_replacement(
    game: "GameState", spell: Any, source: Any
) -> None:
    """Register a one-shot replacement: exile *spell* instead of going to graveyard."""
    from engine.events import SpellMovesToGraveyardReplacementEvent
    from engine.replacement_effects import ReplacementEffect

    # Deliberate limitation: uses SpellMovesToGraveyardReplacementEvent so only
    # non-permanent spells resolving from the stack are intercepted.
    active = [True]  # one-shot flag

    def _condition(g: Any, event: Any) -> bool:
        return active[0] and event.spell is spell

    def _replacement(g: Any, event: Any) -> Any:
        active[0] = False
        event.destination = "exile"
        return event

    game.replacement_manager.register(
        ReplacementEffect(
            event_type=SpellMovesToGraveyardReplacementEvent,
            source=source,
            condition=_condition,
            replacement=_replacement,
            controller=getattr(source, "controller", None),
        )
    )
