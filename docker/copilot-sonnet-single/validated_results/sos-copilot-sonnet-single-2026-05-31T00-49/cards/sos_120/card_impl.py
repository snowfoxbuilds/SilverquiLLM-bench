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

    ENGINE LIMITATION: The Paradigm "at the beginning of each of your first
    main phases" trigger for re-casting is stored as a flag
    ``game._paradigm_capstone_active`` checked by a registered trigger.

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
            "spells from among them without paying their mana costs.\nParadigm "
            "(Then exile this spell. After you first resolve a spell with this "
            "name, you may cast a copy of it from exile without paying its "
            "mana cost at the beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)

    # Paradigm: exile this spell on resolution instead of graveyard.
    def on_cast(self, game: "GameState") -> None:
        """Mark this spell to go to exile on resolution (Paradigm)."""
        self._exile_on_resolution = True  # type: ignore[attr-defined]

    def on_resolve(self, game: "GameState") -> None:
        """Exile cards from library until total MV ≥ 4, then free-cast."""
        from engine.casting import cast_spell_free

        controller = self.controller
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]
        exile_zone = game.get_exile(controller)

        # Step 1: Exile cards until total MV ≥ 4.
        exiled_this_effect: list[Any] = []
        total_mv = 0
        while total_mv < 4:
            cards = library.top(1)
            if not cards:
                break
            card = cards[0]
            library.remove(card)
            exile_zone.add(card)
            exiled_this_effect.append(card)
            cost = getattr(card, "mana_cost", None)
            mv = cost.cmc if cost else 0
            total_mv += mv

        # Step 2: Cast any number of spells from exiled cards for free.
        castable = [
            c for c in exiled_this_effect
            if CardType.INSTANT in getattr(c, "card_types", set())
            or CardType.SORCERY in getattr(c, "card_types", set())
            or CardType.CREATURE in getattr(c, "card_types", set())
            or CardType.ENCHANTMENT in getattr(c, "card_types", set())
            or CardType.ARTIFACT in getattr(c, "card_types", set())
        ]
        for card in castable:
            if not exile_zone.contains(card):
                continue
            try:
                want = controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for free?"
                )
            except Exception:
                want = False
            if not want:
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
                # Resolve immediately.
                if not game.stack.is_empty():
                    stack_obj = game.stack.pop()
                    stack_obj.on_resolve(game)
            except Exception:
                pass  # Skip uncastable cards.

        # Paradigm: register trigger for next main phase if first resolution.
        if not getattr(game, "_paradigm_capstone_active", False):
            game._paradigm_capstone_active = True  # type: ignore[attr-defined]
            self._register_paradigm_trigger(game)

    def _register_paradigm_trigger(self, game: "GameState") -> None:
        """Register a trigger to offer free cast from exile at each main phase."""
        from engine.casting import cast_spell_free
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = self.controller

        def _condition(g: Any, event: Any) -> bool:
            # Fire at beginning of precombat main phase for the controller.
            from engine.types import Phase
            return (
                g.active_player is controller
                and g.phase == Phase.PRECOMBAT_MAIN
            )

        def _effect(g: "GameState") -> None:
            if controller is None:
                return
            exile_zone = g.get_exile(controller)
            copies = [c for c in exile_zone.get_all() if getattr(c, "name", "") == "Improvisation Capstone"]
            if not copies:
                return
            try:
                want = controller.choose_yes_no("Cast Improvisation Capstone from exile?")
            except Exception:
                return
            if want and copies:
                card = copies[0]
                try:
                    cast_spell_free(g, controller, card, Zone.EXILE)
                    if not g.stack.is_empty():
                        stack_obj = g.stack.pop()
                        stack_obj.on_resolve(g)
                except Exception:
                    pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )

