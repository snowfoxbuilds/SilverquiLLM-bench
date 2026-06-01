"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, Phase, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    mc = getattr(card, "mana_cost", None)
    if mc is None:
        return 0
    return getattr(mc, "cmc", 0)


def _is_castable(card: Any) -> bool:
    # Lands can't be "cast"; everything else from the exiled pile can.
    return CardType.LAND not in getattr(card, "card_types", set())


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater.  You may cast any number of spells from among them
    without paying their mana costs.

    Paradigm — then exile this spell.  After you first resolve a spell with
    this name, at the beginning of each of your first main phases you may cast
    a copy of it from exile without paying its mana cost.

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
        self._paradigm_registered: bool = False

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        self._do_capstone(game, controller)

        # Paradigm: "Then exile this spell."  The resolution pipeline honours
        # this flag and routes the card to exile instead of the graveyard.
        self._exile_instead_of_graveyard = True

        # "After you first resolve a spell with this name ..." — wire up the
        # recurring main-phase copy trigger exactly once.
        self._register_paradigm(game, controller)

    # ------------------------------------------------------------------
    # Core effect
    # ------------------------------------------------------------------

    def _do_capstone(self, game: "GameState", controller: Any) -> None:
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        library = controller.zones[Zone.LIBRARY]
        exiled: list = []
        total_mv = 0
        while total_mv < 4:
            cards = library.get_all()
            if not cards:
                break
            top = cards[-1]
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top)
            total_mv += _mana_value(top)

        # "You may cast any number of spells from among them ..."
        exile_zone = controller.zones[Zone.EXILE]
        for card in exiled:
            if not _is_castable(card):
                continue
            if not exile_zone.contains(card):
                continue  # already cast / moved
            if controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
            ):
                cast_spell_free(game, controller, card, Zone.EXILE)

    # ------------------------------------------------------------------
    # Paradigm — recurring copy at each of your first main phases
    # ------------------------------------------------------------------

    def _register_paradigm(self, game: "GameState", controller: Any) -> None:
        if self._paradigm_registered:
            return
        self._paradigm_registered = True

        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            if getattr(event, "phase", None) is not Phase.PRECOMBAT_MAIN:
                return False
            ctrl = source.controller
            if ctrl is None:
                return False
            if getattr(event, "player", None) is not ctrl:
                return False
            # The copy is cast "from exile" — only while the spell is there.
            return ctrl.zones[Zone.EXILE].contains(source)

        def _effect(g: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            if ctrl.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile?"
            ):
                source._do_capstone(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
