"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its
    mana cost at the beginning of each of your first main phases.)

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
            "Paradigm (Then exile this spell. After you first resolve a "
            "spell with this name, you may cast a copy of it from exile "
            "without paying its mana cost at the beginning of each of your "
            "first main phases.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.game import exile
        from engine.zones import move_to_zone

        ctrl = self.controller
        if ctrl is None:
            return

        # 1. Exile from the top of the library until total MV >= 4.
        library = ctrl.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_card = library.top(1)[0]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            cost = getattr(top_card, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        # 2. May cast any number of the exiled spells for free (lands are
        #    not spells — they stay exiled).
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if ctrl.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
            ):
                try:
                    cast_spell_free(game, ctrl, card, Zone.EXILE)
                except CastingError:
                    pass  # not castable (e.g. no legal targets) — stays exiled

        # 3. Paradigm — exile this spell (the engine's stack→graveyard move
        #    then finds nothing to move, which is the correct no-op for a
        #    resolved copy too, since a copy exists in no zone).
        exile(game, self)
        _arm_paradigm(game, ctrl, self)


def _arm_paradigm(game: GameState, ctrl: Any, capstone: ImprovisationCapstone) -> None:
    """After you first resolve a spell with this name, register the
    recurring first-main-phase copy trigger (once per player per name)."""
    from engine.events import BeginningOfPrecombatMainTriggeredEvent
    from engine.stack import StackObject, copy_spell
    from engine.triggers import TriggerRegistration

    armed: set[str] = getattr(ctrl, "_paradigm_armed", set())
    if capstone.name in armed:
        return
    armed.add(capstone.name)
    ctrl._paradigm_armed = armed

    def _condition(game: Any, event: Any) -> bool:
        if game.active_player is not ctrl:
            return False
        # Only while the exiled Capstone is still in exile.
        return ctrl.zones[Zone.EXILE].contains(capstone)

    def _effect(game: GameState) -> None:
        if not ctrl.choose_yes_no(
            f"Cast a copy of {capstone.name} from exile without paying its mana cost?"
        ):
            return
        # A copy of the exiled card is put on the stack and resolves; the
        # original stays in exile for future turns.
        original_so = StackObject(source=capstone, controller=ctrl, targets=[])
        copy_obj = copy_spell(game, original_so, ctrl)
        game.stack.push(copy_obj)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=capstone,
            controller=ctrl,
        )
    )
