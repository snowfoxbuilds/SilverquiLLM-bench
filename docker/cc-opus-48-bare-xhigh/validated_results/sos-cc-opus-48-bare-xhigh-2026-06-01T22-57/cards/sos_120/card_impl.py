"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    mc = getattr(card, "mana_cost", None)
    return mc.cmc if mc is not None else 0


def _is_castable_spell(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return bool(types) and CardType.LAND not in types


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
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Lesson"}
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
        self._paradigm_registered: bool = False
        self._is_paradigm_copy: bool = False

    def on_resolve(self, game: "GameState") -> None:
        self._do_capstone(game)
        # Copies cast from exile by Paradigm do not re-exile themselves nor
        # re-register the recurring trigger.
        if self._is_paradigm_copy:
            return
        if not self._paradigm_registered:
            self._register_paradigm(game)
        # Paradigm: exile this spell instead of putting it into the graveyard.
        self._replace_graveyard_with_exile = True

    # ------------------------------------------------------------------
    # Core effect
    # ------------------------------------------------------------------
    def _do_capstone(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free

        controller = self.controller
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]
        exile = controller.zones[Zone.EXILE]

        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4:
            lib_cards = list(library.get_all())
            if not lib_cards:
                break
            top = lib_cards[-1]
            library.remove(top)
            exile.add(top)
            exiled.append(top)
            total_mv += _mana_value(top)

        castable = [c for c in exiled if _is_castable_spell(c)]
        while castable:
            if not controller.choose_yes_no(
                "Cast a spell from the exiled cards for free?"
            ):
                break
            chosen = controller.choose_card(
                castable, "Choose a spell to cast for free"
            )
            if chosen is None or chosen not in castable:
                break
            castable.remove(chosen)
            try:
                cast_spell_free(game, controller, chosen, Zone.EXILE)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Paradigm
    # ------------------------------------------------------------------
    def _register_paradigm(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        self._paradigm_registered = True
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            if not getattr(event, "precombat", False):
                return False
            ctrl = source.controller
            if ctrl is None or getattr(event, "player", None) is not ctrl:
                return False
            return source in ctrl.zones[Zone.EXILE].get_all()

        def _effect(game: "GameState") -> None:
            from engine.stack import StackObject

            ctrl = source.controller
            if ctrl is None:
                return
            if not ctrl.choose_yes_no(
                "Paradigm: cast a copy of Improvisation Capstone for free?"
            ):
                return
            spell_copy = _copy.copy(source)
            spell_copy.controller = ctrl
            spell_copy.owner = getattr(source, "owner", ctrl)
            spell_copy._is_paradigm_copy = True
            spell_copy.chosen_targets = []

            stack_obj = StackObject(
                source=spell_copy,
                controller=ctrl,
                on_resolve=lambda g: spell_copy.on_resolve(g),
            )
            game.stack.push(stack_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
