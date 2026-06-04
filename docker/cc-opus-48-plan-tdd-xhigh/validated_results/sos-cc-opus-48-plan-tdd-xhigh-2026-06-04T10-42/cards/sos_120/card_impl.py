"""Card implementation for Improvisation Capstone (SOS #120)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Phase, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return cost.cmc if cost is not None else 0


def _is_land(card: Any) -> bool:
    return CardType.LAND in getattr(card, "card_types", set())


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
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first main "
            "phases.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        ctrl = self.controller
        if ctrl is None:
            return
        self._exile_and_cast(game, ctrl)
        self._setup_paradigm(game, ctrl)
        # Paradigm: "Then exile this spell" — redirect this spell's
        # stack→graveyard move to exile instead.
        self._register_self_exile(game)

    # ------------------------------------------------------------------
    # Impulse: exile from the top until total MV >= 4, then may free-cast.
    # ------------------------------------------------------------------
    def _exile_and_cast(self, game: "GameState", ctrl: Any) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.game import exile

        library = ctrl.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total = 0
        while total < 4:
            top = library.top(1)
            if not top:
                break
            card = top[0]
            exile(game, card)
            exiled.append(card)
            total += _mana_value(card)

        for card in exiled:
            if _is_land(card):
                continue
            if not ctrl.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} without paying its cost?"
            ):
                continue
            try:
                cast_spell_free(game, ctrl, card, Zone.EXILE)
            except CastingError:
                continue

    # ------------------------------------------------------------------
    # Paradigm recurrence — registered once per controller, persists for the
    # rest of the game on its own emblem-like source object.
    # ------------------------------------------------------------------
    def _setup_paradigm(self, game: "GameState", ctrl: Any) -> None:
        if getattr(ctrl, "_improvisation_paradigm_active", False):
            return
        ctrl._improvisation_paradigm_active = True

        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = type("ParadigmEmblem", (), {"name": "Improvisation Capstone Paradigm"})()
        ctrl._improvisation_paradigm_source = source

        def _condition(game: Any, event: Any) -> bool:
            return (
                getattr(event, "player", None) is ctrl
                and getattr(event, "phase", None) is Phase.PRECOMBAT_MAIN
            )

        def _effect(game: Any) -> None:
            from engine.casting import CastingError, cast_spell_free

            if not ctrl.choose_yes_no(
                "Paradigm: cast a copy of Improvisation Capstone for free?"
            ):
                return
            copy = ImprovisationCapstone(owner=ctrl, controller=ctrl)
            ctrl.zones[Zone.EXILE].add(copy)
            try:
                cast_spell_free(game, ctrl, copy, Zone.EXILE)
            except CastingError:
                if ctrl.zones[Zone.EXILE].contains(copy):
                    ctrl.zones[Zone.EXILE].remove(copy)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=ctrl,
            )
        )

    def _register_self_exile(self, game: "GameState") -> None:
        from engine.events import SpellResolvesToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        card = self

        def _condition(game: Any, event: Any) -> bool:
            return getattr(event, "spell", None) is card

        def _replace(game: Any, event: Any) -> Any:
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=SpellResolvesToGraveyardReplacementEvent,
                source=card,
                condition=_condition,
                replacement=_replace,
                controller=getattr(card, "controller", None),
            )
        )
