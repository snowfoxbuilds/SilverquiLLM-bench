"""Card implementation for Improvisation Capstone.

Paradigm simplification: "cast a copy of it from exile" is implemented by
shallow-copying this card, placing the copy in the exile zone, and free-casting
it from there. The original spell stays in exile (it is never moved), so the
recurring effect can fire every first main phase. Copies are flagged so they
re-run the exile-and-cast effect but do not arm a second Paradigm trigger.
"""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_PARADIGM_THRESHOLD = 4


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.
    Paradigm.

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
            "Paradigm.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return
        # Paradigm: this spell is exiled instead of going to the graveyard.
        self._exile_on_resolve = True
        self._improvise(game, controller)
        if not getattr(self, "_is_paradigm_copy", False):
            self._arm_paradigm(game, controller)

    def _improvise(self, game: "GameState", controller: Any) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total = 0
        while total < _PARADIGM_THRESHOLD and len(library) > 0:
            card = library.top(1)[0]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(card)
            cost = getattr(card, "mana_cost", None)
            total += cost.cmc if cost is not None else 0

        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not controller.zones[Zone.EXILE].contains(card):
                continue
            prompt = f"Cast {getattr(card, 'name', 'spell')} without paying its mana cost?"
            if not controller.choose_yes_no(prompt):
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                pass

    def _arm_paradigm(self, game: "GameState", controller: Any) -> None:
        if getattr(self, "_paradigm_armed", False):
            return
        self._paradigm_armed = True

        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _paradigm(g: "GameState") -> None:
            ctrl = controller
            if not ctrl.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile?"
            ):
                return
            copy_card = _copy.copy(source)
            copy_card.controller = ctrl
            copy_card.owner = getattr(source, "owner", ctrl)
            copy_card._is_paradigm_copy = True
            copy_card._paradigm_armed = True
            ctrl.zones[Zone.EXILE].add(copy_card)
            from engine.casting import CastingError, cast_spell_free

            try:
                cast_spell_free(g, ctrl, copy_card, Zone.EXILE)
            except CastingError:
                if ctrl.zones[Zone.EXILE].contains(copy_card):
                    ctrl.zones[Zone.EXILE].remove(copy_card)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=lambda g, e: e.player is controller
                and getattr(e, "is_first_main", False),
                effect=_paradigm,
                source=self,
                controller=controller,
            )
        )
