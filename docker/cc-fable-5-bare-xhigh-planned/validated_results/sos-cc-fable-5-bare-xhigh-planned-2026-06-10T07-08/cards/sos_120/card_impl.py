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
    this name, you may cast a copy of it from exile without paying its mana
    cost at the beginning of each of your first main phases.)

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

        # 1. Exile from the top of the library until total mana value >= 4
        #    (or the library runs out).
        library = game.get_library(controller)
        batch: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            card = library.top(1)[0]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            batch.append(card)
            cost = getattr(card, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        # 2. May cast any number of spells from among them, free.
        castable = [
            c
            for c in batch
            if CardType.LAND not in getattr(c, "card_types", set())
            and c.can_cast(game)
        ]
        while castable:
            chosen = controller.choose_card(
                castable,
                "Cast a spell exiled with Improvisation Capstone without "
                "paying its mana cost? (None to stop)",
            )
            if chosen is None or chosen not in castable:
                break
            castable.remove(chosen)
            try:
                cast_spell_free(game, controller, chosen, Zone.EXILE)
            except CastingError:
                pass  # not castable after all — it simply stays exiled

        # 3. Paradigm.
        self._paradigm_exile_instead(game, controller)
        self._paradigm_register_recurring_copy(game, controller)

    # ------------------------------------------------------------------
    # Paradigm helpers
    # ------------------------------------------------------------------

    def _paradigm_exile_instead(self, game: GameState, controller: Any) -> None:
        """"Then exile this spell" — redirect this card's stack→graveyard
        move to exile (one-shot).  Spell *copies* are never in a stack zone
        and never move zones, so they skip this."""
        from engine.events import MoveToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        if not controller.zones[Zone.STACK].contains(self):
            return

        source = self
        marker = object()

        def _condition(g: Any, event: Any) -> bool:
            return getattr(event, "card", None) is source

        def _replacement(g: Any, event: Any) -> Any:
            event.destination = "exile"
            g.replacement_manager.unregister(marker)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=marker,
                condition=_condition,
                replacement=_replacement,
                controller=controller,
            )
        )

    def _paradigm_register_recurring_copy(
        self, game: GameState, controller: Any
    ) -> None:
        """After you first resolve a spell with this name: at the beginning
        of each of your first main phases, you may cast a copy from exile."""
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.stack import StackObject, copy_spell
        from engine.triggers import TriggerRegistration

        # Once per player ("after you FIRST resolve a spell with this name").
        if getattr(controller, "_capstone_paradigm_registered", False):
            return
        controller._capstone_paradigm_registered = True

        source = self
        marker = object()

        def _condition(g: Any, event: Any) -> bool:
            return g.active_player is controller

        def _effect(g: GameState) -> None:
            if not controller.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile without "
                "paying its mana cost?"
            ):
                return
            # The copy resolves on its own and never changes zones; the
            # exiled original stays in exile.
            original = StackObject(source=source, controller=controller)
            copy_obj = copy_spell(g, original, controller)
            g.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=marker,
                controller=controller,
            )
        )
