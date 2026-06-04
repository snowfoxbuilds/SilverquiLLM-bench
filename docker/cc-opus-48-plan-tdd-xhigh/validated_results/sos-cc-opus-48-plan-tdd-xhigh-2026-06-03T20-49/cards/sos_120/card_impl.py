"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return cost.cmc if cost is not None else 0


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
            "spells from among them without paying their mana costs.\n"
            "Paradigm",
        )
        super().__init__(**kwargs)
        self._is_paradigm_copy: bool = False
        self._paradigm_registered: bool = False

    def on_resolve(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        ctrl = getattr(self, "controller", None)
        if ctrl is None:
            return

        # 1. Exile from the top of the library until total MV >= 4.
        library = ctrl.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total = 0
        while total < 4:
            cards = library.get_all()
            if not cards:
                break
            top = cards[-1]
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top)
            total += _mana_value(top)

        # 2. Optionally cast the exiled nonland cards without paying their cost.
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not ctrl.zones[Zone.EXILE].contains(card):
                continue
            try:
                if ctrl.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying its "
                    "mana cost?"
                ):
                    cast_spell_free(game, ctrl, card, Zone.EXILE)
            except Exception:
                pass

        # 3. Paradigm — only the originally cast spell exiles itself and sets
        #    up the recurring recast; copies just resolve their effect and go
        #    to the graveyard as normal.
        if not self._is_paradigm_copy:
            self._exile_on_resolution = True
            self._register_paradigm(game)

    def _register_paradigm(self, game: "GameState") -> None:
        if self._paradigm_registered:
            return
        self._paradigm_registered = True

        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if getattr(event, "player", None) is not ctrl:
                return False
            if not getattr(event, "is_precombat", False):
                return False
            return ctrl.zones[Zone.EXILE].contains(source)

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            if not ctrl.choose_yes_no(
                "Paradigm — cast a copy of Improvisation Capstone for free?"
            ):
                return
            copy = ImprovisationCapstone(owner=ctrl)
            copy.controller = ctrl
            copy._is_paradigm_copy = True
            ctrl.zones[Zone.EXILE].add(copy)
            try:
                cast_spell_free(game, ctrl, copy, Zone.EXILE)
            except Exception:
                pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
