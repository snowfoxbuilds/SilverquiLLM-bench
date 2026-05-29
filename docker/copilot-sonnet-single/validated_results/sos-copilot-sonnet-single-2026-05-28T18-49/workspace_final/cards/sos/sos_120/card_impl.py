"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

# Track cards that have triggered their Paradigm for the first time
# Maps card identity to whether paradigm has been set up
_PARADIGM_SETUP: dict[int, bool] = {}


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among
    them without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its mana
    cost at the beginning of each of your first main phases.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with "
            "total mana value 4 or greater. You may cast any number of spells from "
            "among them without paying their mana costs.\nParadigm (Then exile this "
            "spell. After you first resolve a spell with this name, you may cast a "
            "copy of it from exile without paying its mana cost at the beginning of "
            "each of your first main phases.)",
        )
        super().__init__(**kwargs)
        self._paradigm_active: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Exile top cards until MV ≥ 4; may cast any for free."""
        controller = self.controller
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]
        exile_zone = controller.zones[Zone.EXILE]

        # Exile cards until total MV >= 4
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top = library.top(1)
            if not top:
                break
            card = top[0]
            library.remove(card)
            exile_zone.add(card)
            exiled.append(card)
            card_mv = getattr(getattr(card, "mana_cost", None), "cmc", 0)
            total_mv += card_mv

        # Offer controller to cast any/all exiled spells for free
        from engine.casting import cast_spell_free

        for card in list(exiled):
            # Only castable types (not lands)
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            try:
                cast_it = controller.choose_yes_no(f"Cast {getattr(card, 'name', '?')} for free?")
            except Exception:
                cast_it = False
            if cast_it:
                try:
                    cast_spell_free(game, controller, card, Zone.EXILE)
                    exiled.remove(card)
                except Exception:
                    pass

        # Paradigm: exile this spell (instead of graveyard) and set up the trigger
        # The card is still in the stack zone at this point; exile it
        card_id = id(self)
        paradigm_already_set = _PARADIGM_SETUP.get(card_id, False)

        # Move this card from stack zone to exile (paradigm replacement)
        for p in game.players:
            stack_zone = p.zones[Zone.STACK]
            if stack_zone.contains(self):
                stack_zone.remove(self)
                p_exile = p.zones[Zone.EXILE]
                p_exile.add(self)
                break

        # Set up paradigm recurring trigger if first time
        if not paradigm_already_set:
            _PARADIGM_SETUP[card_id] = True
            self._paradigm_active = True

            # Register a trigger for beginning of each of controller's main phases
            from engine.triggers import TriggerRegistration
            from engine.events import BeginningOfMainPhaseTriggeredEvent
            import copy as _copy

            source_ref = self

            def _paradigm_condition(game: Any, event: Any) -> bool:
                return (
                    getattr(source_ref, "_paradigm_active", False)
                    and getattr(event, "player", None) is controller
                    and getattr(event, "is_precombat", True)
                )

            def _paradigm_effect(game: Any) -> None:
                if not getattr(source_ref, "_paradigm_active", False):
                    return
                try:
                    cast_it = controller.choose_yes_no("Cast Improvisation Capstone copy via Paradigm?")
                except Exception:
                    cast_it = False
                if cast_it:
                    # Create a copy and cast it for free
                    card_copy = _copy.copy(source_ref)
                    card_copy.controller = controller
                    card_copy.owner = controller
                    controller.zones[Zone.EXILE].add(card_copy)
                    try:
                        cast_spell_free(game, controller, card_copy, Zone.EXILE)
                    except Exception:
                        controller.zones[Zone.EXILE].remove(card_copy)

            game.trigger_manager.register(TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_paradigm_condition,
                effect=_paradigm_effect,
                source=self,
                controller=controller,
            ))

