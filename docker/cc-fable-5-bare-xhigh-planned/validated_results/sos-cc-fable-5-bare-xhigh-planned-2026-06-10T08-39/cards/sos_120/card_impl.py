"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
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
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # 1. Exile from the top of the library until total MV >= 4 (or the
        #    library runs out).
        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_card = library.top(1)[0]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            cost = getattr(top_card, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        # 2. May cast any number of them for free (lands can't be cast and
        #    stay exiled).
        castable = [
            c for c in exiled
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        for c in castable:
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(c, 'name', 'card')} without paying its mana cost?"
                ):
                    cast_spell_free(game, controller, c, Zone.EXILE)
            except CastingError:
                continue  # not castable right now — stays exiled
            except Exception:
                continue  # no scripted answer — treat as declined

        # 3. Paradigm.
        if getattr(self, "_is_paradigm_copy", False):
            # A resolved copy ceases to exist — leave the stack zone and
            # land nowhere.
            stack_zone = controller.zones[Zone.STACK]
            if stack_zone.contains(self):
                stack_zone.remove(self)
            return

        # Original: exile this spell (so _resolve_spell's graveyard move
        # finds nothing to do), then set up the recurring first-main-phase
        # copy cast.
        move_to_zone(game, self, Zone.STACK, Zone.EXILE)
        self._register_paradigm_trigger(game, controller)

    def _register_paradigm_trigger(self, game: GameState, controller: Any) -> None:
        """At the beginning of each of your first main phases, you may cast
        a copy of this card from exile for free (recurring)."""
        from engine.casting import CastingError, cast_spell_free
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: GameState, event: Any) -> bool:
            # Your first main phase, and the card is still in exile.
            return (
                g.active_player is controller
                and controller.zones[Zone.EXILE].contains(source)
            )

        def _effect(g: GameState) -> None:
            try:
                wants = controller.choose_yes_no(
                    "Cast a copy of Improvisation Capstone from exile "
                    "without paying its mana cost?"
                )
            except Exception:
                return
            if not wants:
                return
            cp = _copy.copy(source)
            cp._is_paradigm_copy = True
            cp.controller = controller
            cp.owner = getattr(source, "owner", controller)
            controller.zones[Zone.EXILE].add(cp)
            try:
                cast_spell_free(g, controller, cp, Zone.EXILE)
            except CastingError:
                controller.zones[Zone.EXILE].remove(cp)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
