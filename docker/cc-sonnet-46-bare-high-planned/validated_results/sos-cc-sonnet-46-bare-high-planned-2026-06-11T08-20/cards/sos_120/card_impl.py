"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its mana
    cost at the beginning of each of your first main phases.)

    SOS collector number 120.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first main "
            "phases.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # Main effect: exile top of library until total MV >= 4.
        library = controller.zones[Zone.LIBRARY]
        exiled_cards: list[Any] = []
        total_mv = 0
        while total_mv < 4:
            top = library.top(1)
            if not top:
                break  # library exhausted
            card = top[-1]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(card)
            mc = getattr(card, "mana_cost", None)
            total_mv += mc.cmc if mc is not None else 0

        # You may cast any number of them without paying their mana costs.
        castable = [
            c for c in exiled_cards
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        for card in castable:
            try:
                if controller.choose_yes_no(f"Cast {getattr(card, 'name', 'card')} for free?"):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                pass

        # Paradigm: exile this spell instead of it going to the graveyard.
        self._exile_instead_of_graveyard = True

        # Register recurring Paradigm trigger once per player.
        if not getattr(controller, "_paradigm_capstone_registered", False):
            controller._paradigm_capstone_registered = True  # type: ignore[attr-defined]
            source_ref = self

            def _condition(g: Any, event: Any) -> bool:
                return g.active_player is controller

            def _paradigm_effect(g: Any) -> None:
                copy_card = ImprovisationCapstone()
                copy_card.owner = controller
                copy_card.controller = controller
                controller.zones[Zone.EXILE].add(copy_card)
                try:
                    if controller.choose_yes_no("Cast copy of Improvisation Capstone from exile?"):
                        cast_spell_free(g, controller, copy_card, Zone.EXILE)
                except Exception:
                    pass

            game.trigger_manager.register(TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_paradigm_effect,
                source=source_ref,
                controller=controller,
            ))
