"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfPrecombatMainTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return getattr(cost, "cmc", 0) if cost is not None else 0


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
    # Main effect (shared by the original resolution and each Paradigm copy)
    # ------------------------------------------------------------------

    def _main_effect(self, game: "GameState", controller: Any) -> None:
        from engine.casting import cast_spell_free

        library = controller.zones[Zone.LIBRARY]
        exile = controller.zones[Zone.EXILE]
        exiled: list[Any] = []
        total_mv = 0
        # Exile from the top until total mana value is 4 or greater (or the
        # library runs out).
        while total_mv < 4 and len(library) > 0:
            top = library.top(1)[0]
            library.remove(top)
            exile.add(top)
            exiled.append(top)
            total_mv += _mana_value(top)

        # You may cast any number of them for free.  Lands aren't spells and
        # stay exiled.
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not exile.contains(card):
                continue  # already cast / left exile
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} from exile without "
                    "paying its mana cost?"
                ):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Resolution + Paradigm
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return
        self._main_effect(game, controller)
        # Paradigm: "Then exile this spell." — redirect this sorcery's
        # stack→graveyard move to exile (see engine.casting._resolve_spell).
        self._exile_on_resolve = True
        self._setup_paradigm(game, controller)

    def _setup_paradigm(self, game: "GameState", controller: Any) -> None:
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            # "the beginning of each of your first main phases" — E2 fires at
            # precombat (first) main; gate to the controller's turns.  Recurring.
            return getattr(g, "active_player", None) is controller

        def _effect(g: "GameState") -> None:
            # Only while this spell is still in exile.
            if not controller.zones[Zone.EXILE].contains(source):
                return
            try:
                cast_copy = controller.choose_yes_no(
                    "Cast a copy of Improvisation Capstone from exile without "
                    "paying its mana cost?"
                )
            except Exception:
                cast_copy = False
            if not cast_copy:
                return
            # Cast a copy: push a stack object that runs the main effect (the
            # copy is not the printed spell, so it does not re-set up Paradigm).
            copy_obj = StackObject(
                source=source,
                controller=controller,
                on_resolve=lambda gg: source._main_effect(gg, controller),
            )
            g.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
