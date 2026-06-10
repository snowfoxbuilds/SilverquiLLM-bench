"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
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
            "spells from among them without paying their mana costs.\nParadigm",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        ctrl = self.controller
        if ctrl is None:
            return

        # Exile from the top of your library until total MV >= 4 (or it runs out).
        library = game.get_library(ctrl)
        exiled_batch: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top = library.top(1)[0]
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled_batch.append(top)
            cost = getattr(top, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        # You may cast any number of (nonland) spells from among them for free.
        for card in exiled_batch:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue  # lands aren't spells — they stay exiled
            if not game.get_exile(ctrl).contains(card):
                continue
            if ctrl.choose_yes_no(f"Cast {card.name} without paying its mana cost?"):
                cast_spell_free(game, ctrl, card, Zone.EXILE)

        # Paradigm — only the original cast (not a paradigm copy) sets this up,
        # and only the first time you resolve a Capstone.
        if getattr(self, "_is_paradigm_copy", False):
            return
        if getattr(ctrl, "_capstone_paradigm_set", False):
            return
        ctrl._capstone_paradigm_set = True
        # "Then exile this spell." — redirect this card to exile as it leaves
        # the stack (read by _resolve_spell), instead of the graveyard.
        self._leaves_stack_to = Zone.EXILE
        self._register_paradigm(game, ctrl)

    def _register_paradigm(self, game: "GameState", ctrl: Any) -> None:
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.stack import StackObject, copy_spell
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            # Each of your first (precombat) main phases.
            return game.active_player is ctrl and game.get_exile(ctrl).contains(
                source
            )

        def _effect(game: "GameState") -> None:
            if not ctrl.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile?"
            ):
                return
            # Cast a copy of it from exile (the original stays exiled for next
            # turn).  The copy re-runs the exile-and-cast effect but does not
            # itself set up Paradigm again.
            orig_so = StackObject(source=source, controller=ctrl, targets=[])
            copy_obj = copy_spell(game, orig_so, ctrl)
            copy_obj.source._is_paradigm_copy = True
            game.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=ctrl,
            )
        )
