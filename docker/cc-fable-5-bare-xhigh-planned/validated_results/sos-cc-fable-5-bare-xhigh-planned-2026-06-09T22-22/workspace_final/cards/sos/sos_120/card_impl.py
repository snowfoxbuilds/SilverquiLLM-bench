"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfPrecombatMainTriggeredEvent
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

        self._improvise(game, ctrl)

        # Copies created by Paradigm only run the improvisation effect — they
        # do not re-exile the original or re-register the recurring trigger.
        if getattr(self, "_is_paradigm_copy", False):
            return

        # Paradigm: exile this spell (instead of going to the graveyard) and
        # set up the recurring "cast a copy from exile" trigger.
        from engine.game import exile

        exile(game, self)  # moves self from the stack zone to exile
        self._register_paradigm(game, ctrl)

    # ------------------------------------------------------------------

    def _improvise(self, game: "GameState", ctrl: Any) -> None:
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        library = game.get_library(ctrl)
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_card = library.get_all()[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            cost = getattr(top_card, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        # You may cast any number of the exiled SPELLS (nonland cards) for free.
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue  # lands aren't spells — they stay exiled
            if not game.get_exile(ctrl).contains(card):
                continue
            if ctrl.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} for free?"
            ):
                try:
                    cast_spell_free(game, ctrl, card, Zone.EXILE)
                except Exception:
                    pass

    def _register_paradigm(self, game: "GameState", ctrl: Any) -> None:
        from engine.stack import StackObject
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            # Each of YOUR first (precombat) main phases, while still in exile.
            return (
                game.active_player is source.controller
                and game.get_exile(source.controller).contains(source)
            )

        def _effect(game: "GameState") -> None:
            ctrl2 = source.controller
            if ctrl2 is None:
                return
            if not ctrl2.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile for free?"
            ):
                return
            # Cast a copy: a duplicate stack object that resolves the
            # improvisation effect. The original stays in exile.
            dup = _copy.copy(source)
            dup._is_paradigm_copy = True
            dup.controller = ctrl2
            so = StackObject(source=dup, controller=ctrl2, targets=[])

            def _res(g: "GameState") -> None:
                dup.chosen_targets = []
                dup.on_resolve(g)

            so.on_resolve = _res
            game.stack.push(so)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=ctrl,
            )
        )
