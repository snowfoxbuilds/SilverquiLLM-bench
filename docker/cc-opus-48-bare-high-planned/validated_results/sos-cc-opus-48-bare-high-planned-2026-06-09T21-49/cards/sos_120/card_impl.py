"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone
from engine.events import BeginningOfPrecombatMainTriggeredEvent

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
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\nParadigm",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Main effect: exile from top until MV >= 4, may cast nonlands for free.
    # ------------------------------------------------------------------

    def _main_effect(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]

        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top = library.top(1)[0]
            mv = 0
            cost = getattr(top, "mana_cost", None)
            if cost is not None:
                mv = cost.cmc
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top)
            total_mv += mv

        for card in exiled:
            # Lands (and other noncastable cards) stay exiled.
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            try:
                if not controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for free?"
                ):
                    continue
            except Exception:
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Resolution + Paradigm setup
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        self._main_effect(game)
        self._setup_paradigm(game)

    def _setup_paradigm(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        controller = self.controller
        if controller is None:
            return
        # "Then exile this spell." — redirect this spell's resolution from
        # graveyard to exile (handled by _resolve_spell's redirect flag).
        self._exile_instead_of_graveyard = True

        # Arm the recurring Paradigm trigger only once per controller.
        if getattr(controller, "_improvisation_paradigm_armed", False):
            return
        controller._improvisation_paradigm_armed = True

        source = self
        marker = type("ImprovisationParadigm", (), {"name": "Improvisation Capstone (Paradigm)"})()

        def _condition(game: Any, event: Any) -> bool:
            # Your first main phase = your precombat main.
            return game.active_player is controller and controller.zones[Zone.EXILE].contains(source)

        def _effect(game: "GameState") -> None:
            try:
                if not controller.choose_yes_no(
                    "Cast a copy of Improvisation Capstone from exile for free?"
                ):
                    return
            except Exception:
                return
            source._cast_paradigm_copy(game, controller)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=marker,
            controller=controller,
        ))

    def _cast_paradigm_copy(self, game: "GameState", controller: Any) -> None:
        """Cast a copy of this spell from exile (the original stays exiled).

        The copy only runs the main effect — it does not re-arm Paradigm.
        """
        from engine.stack import StackObject

        copied = _copy.copy(self)
        copied.controller = controller
        copied.owner = getattr(self, "owner", controller)

        def _resolve(g: "GameState") -> None:
            copied._main_effect(g)

        game.stack.push(StackObject(
            source=copied, controller=controller, on_resolve=_resolve
        ))
