"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Phase, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return getattr(cost, "cmc", 0) if cost is not None else 0


def _is_castable_spell(card: Any) -> bool:
    """A card you can cast as a spell — anything that isn't a land."""
    types = getattr(card, "card_types", set())
    return bool(types) and CardType.LAND not in types


def exile_until_mana_value(game: "GameState", controller: Any, threshold: int) -> list:
    """Exile cards from the top of *controller*'s library until the total mana
    value of the exiled cards is *threshold* or greater.  Returns the exiled
    cards (in the order exiled)."""
    library = controller.zones[Zone.LIBRARY]
    exile = controller.zones[Zone.EXILE]
    exiled: list = []
    total = 0
    while total < threshold:
        cards = library.get_all()
        if not cards:
            break
        top = cards[-1]
        library.remove(top)
        exile.add(top)
        exiled.append(top)
        total += _mana_value(top)
    return exiled


def cast_free_from_exile(game: "GameState", controller: Any, cards: list) -> None:
    """Let *controller* cast any number of the given exiled *cards* without
    paying their mana costs."""
    from engine.casting import cast_spell_free

    exile = controller.zones[Zone.EXILE]
    for card in list(cards):
        if not _is_castable_spell(card) or not exile.contains(card):
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
            # Casting failed (e.g. no legal target) — leave it in exile.
            continue


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
        # Set on copies cast by Paradigm so they don't re-arm the mechanic.
        self.is_paradigm_copy: bool = False

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        exiled = exile_until_mana_value(game, controller, 4)
        cast_free_from_exile(game, controller, exiled)

        # Paradigm: only the original (not a Paradigm copy) arms the mechanic.
        if not self.is_paradigm_copy:
            self.replace_graveyard_with_exile = True
            self._register_paradigm(game)

    def _register_paradigm(self, game: "GameState") -> None:
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = source.controller

        def _condition(game: Any, event: Any) -> bool:
            if getattr(event, "player", None) is not source.controller:
                return False
            return getattr(event, "phase", None) == Phase.PRECOMBAT_MAIN

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            # The original must still be in exile to copy it.
            if not ctrl.zones[Zone.EXILE].contains(source):
                return
            try:
                if not ctrl.choose_yes_no(
                    "Paradigm: cast a copy of Improvisation Capstone for free?"
                ):
                    return
            except Exception:
                return
            copy = ImprovisationCapstone(owner=ctrl, controller=ctrl)
            copy.is_paradigm_copy = True
            ctrl.zones[Zone.EXILE].add(copy)
            from engine.casting import cast_spell_free

            try:
                cast_spell_free(game, ctrl, copy, Zone.EXILE)
            except Exception:
                if ctrl.zones[Zone.EXILE].contains(copy):
                    ctrl.zones[Zone.EXILE].remove(copy)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
