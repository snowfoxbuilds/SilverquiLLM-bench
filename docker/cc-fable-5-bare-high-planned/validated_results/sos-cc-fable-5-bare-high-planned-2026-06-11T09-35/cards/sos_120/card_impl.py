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

    def on_resolve(self, game: "GameState") -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # 1. Exile from the top of the library until total MV >= 4.
        library = game.get_library(controller)
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            card = library.top(1)[0]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(card)
            cost = getattr(card, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        # 2. May cast any number of those spells for free.
        exile_zone = game.get_exile(controller)
        while True:
            candidates = [
                c for c in exiled
                if exile_zone.contains(c)
                and CardType.LAND not in getattr(c, "card_types", set())
                and c.can_cast(game)
            ]
            if not candidates:
                break
            chosen = controller.choose_card(
                candidates,
                "Cast a spell exiled with Improvisation Capstone for free? "
                "(None to stop)",
            )
            if chosen is None or chosen not in candidates:
                break
            try:
                cast_spell_free(game, controller, chosen, Zone.EXILE)
            except CastingError:
                break

        # 3. Paradigm — "Then exile this spell" applies to every resolution
        #    of a Paradigm card; the recurring copy-cast only after you
        #    FIRST resolve a spell with this name.
        self._register_exile_replacement(game, controller)
        paradigm_names = getattr(controller, "_paradigm_names", None)
        if paradigm_names is None:
            paradigm_names = set()
            controller._paradigm_names = paradigm_names
        if self.name in paradigm_names:
            return
        paradigm_names.add(self.name)
        self._register_paradigm(game, controller)

    def _register_exile_replacement(self, game: "GameState", controller: Any) -> None:
        """Redirect this card's post-resolution graveyard move to exile."""
        from engine.events import MoveToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        if getattr(self, "_exile_repl_registered", False):
            return
        self._exile_repl_registered = True
        source = self

        def _repl_condition(game: Any, event: Any) -> bool:
            return event.card is source

        def _replacement(game: Any, event: Any) -> Any:
            event.destination = "exile"
            return event

        game.replacement_manager.register(ReplacementEffect(
            event_type=MoveToGraveyardReplacementEvent,
            source=source,
            condition=_repl_condition,
            replacement=_replacement,
            controller=controller,
        ))

    def _register_paradigm(self, game: "GameState", controller: Any) -> None:
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.stack import StackObject, copy_spell
        from engine.triggers import TriggerRegistration

        source = self

        # Recurring: at the beginning of each of your first main phases,
        # you may cast a copy of it from exile for free.
        def _condition(game: Any, event: Any) -> bool:
            return game.active_player is controller

        def _effect(game: "GameState") -> None:
            if not game.get_exile(controller).contains(source):
                return  # card left exile — paradigm goes dormant
            if not controller.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile for free?"
            ):
                return
            # Copy the spell onto the stack; the physical card stays in
            # exile (copies never change zones).
            template = StackObject(source=source, controller=controller)
            game.stack.push(copy_spell(game, template, controller))

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=source,
            controller=controller,
        ))
