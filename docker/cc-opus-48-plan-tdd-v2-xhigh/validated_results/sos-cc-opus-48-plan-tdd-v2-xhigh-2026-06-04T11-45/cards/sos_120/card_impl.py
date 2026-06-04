"""Card implementation for Improvisation Capstone (SOS #120).

ENGINE NOTE: Paradigm is modelled behaviorally — on resolution the spell
exiles itself (gap #4, ``_exile_on_resolve``) and registers an ongoing
trigger that, at the beginning of each of the controller's first main
phases, may cast a free copy of the improvisation effect from exile.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater.  You may cast any number of spells from
    among them without paying their mana costs.
    Paradigm.

    SOS collector number 120.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Lesson"}
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\n"
            "Paradigm",
        )
        super().__init__(**kwargs)

    def _improvise(self, game: "GameState", controller: "Player") -> None:
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total = 0
        while total < 4:
            cards = library.get_all()
            if not cards:
                break
            top = cards[-1]
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top)
            total += getattr(getattr(top, "mana_cost", None), "cmc", 0) or 0

        castable = [
            c for c in exiled if CardType.LAND not in getattr(c, "card_types", set())
        ]
        for card in castable:
            if not controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} without paying its "
                "mana cost?"
            ):
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                pass

    def _register_paradigm(self, game: "GameState", controller: "Player") -> None:
        from engine.triggers import TriggerRegistration

        if getattr(self, "_paradigm_registered", False):
            return
        self._paradigm_registered = True
        source = self

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return (
                getattr(event, "player", None) is ctrl
                and getattr(event, "is_first", False)
            )

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            if not ctrl.choose_yes_no(
                "Paradigm: cast a copy of Improvisation Capstone?"
            ):
                return
            from engine.stack import StackObject

            cp = copy.copy(source)
            cp.owner = source.owner
            cp.controller = ctrl
            game.stack.push(
                StackObject(
                    source=cp,
                    controller=ctrl,
                    on_resolve=lambda g: cp._improvise(g, ctrl),
                )
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return
        self._improvise(game, controller)
        # Paradigm: exile this spell instead of putting it in the graveyard.
        self._exile_on_resolve = True
        self._register_paradigm(game, controller)
