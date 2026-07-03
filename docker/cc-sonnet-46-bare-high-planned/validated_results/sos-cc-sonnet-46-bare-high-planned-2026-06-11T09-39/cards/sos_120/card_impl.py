"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among them
    without paying their mana costs.

    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)

    SOS collector number 120.
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
        self._is_paradigm_copy: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Main effect + Paradigm setup on first resolution."""
        from engine.casting import cast_spell_free, CastingError
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # -- Exile from library until total CMC >= 4 --
        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_cmc = 0
        while total_cmc < 4 and len(library) > 0:
            top = library.top(1)[0]
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top)
            cost = getattr(top, "mana_cost", None)
            total_cmc += cost.cmc if cost is not None else 0

        # -- Offer free cast for each non-land exiled card --
        castable = [
            c for c in exiled
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        for card in castable:
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')!r} without paying its mana cost?"
                ):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except (CastingError, Exception):
                pass

        # -- Paradigm: first resolution only (not for Paradigm copies) --
        if self._is_paradigm_copy:
            return

        paradigm_done: set[str] = getattr(game, "_paradigm_done", set())
        if self.name in paradigm_done:
            return

        paradigm_done.add(self.name)
        setattr(game, "_paradigm_done", paradigm_done)

        # Register exile-instead replacement so _resolve_spell sends self to exile.
        _register_paradigm_exile(game, self, controller)
        # Register recurring precombat-main trigger for copies.
        _register_paradigm_trigger(game, self, controller)


def _register_paradigm_exile(
    game: "GameState", card: Any, controller: Any
) -> None:
    """Register a one-shot replacement: send *card* to exile instead of graveyard."""

    def _condition(game: Any, event: Any) -> bool:
        return getattr(event, "_source_card", None) is card

    def _replacement(game: Any, event: Any) -> Any:
        event.destination = "exile"
        game.replacement_manager.unregister(card)
        return event

    game.replacement_manager.register(
        ReplacementEffect(
            event_type=MoveToGraveyardReplacementEvent,
            source=card,
            condition=_condition,
            replacement=_replacement,
            controller=controller,
        )
    )


def _register_paradigm_trigger(
    game: "GameState", original: Any, controller: Any
) -> None:
    """Register a recurring trigger: at each of your precombat main phases,
    optionally cast a copy of the Capstone from exile for free.
    """
    from engine.events import BeginningOfPrecombatMainTriggeredEvent
    from engine.triggers import TriggerRegistration

    source = original  # keep reference to trigger source for unregister

    def _condition(game: Any, event: Any) -> bool:
        return game.active_player is controller

    def _effect(game: Any) -> None:
        from engine.casting import cast_spell_free, CastingError

        try:
            if not controller.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile without paying its mana cost?"
            ):
                return
        except Exception:
            return

        # Create a copy of the original card to cast from exile.
        cap_copy = _copy.copy(original)
        cap_copy._is_paradigm_copy = True
        cap_copy.controller = controller
        cap_copy.owner = controller

        # Put the copy in the exile zone so cast_spell_free can find it.
        exile_zone = controller.zones[Zone.EXILE]
        exile_zone.add(cap_copy)

        try:
            cast_spell_free(game, controller, cap_copy, Zone.EXILE)
        except (CastingError, Exception):
            # Roll back: remove copy from exile if casting failed.
            if exile_zone.contains(cap_copy):
                exile_zone.remove(cap_copy)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=source,
            controller=controller,
        )
    )
