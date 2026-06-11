"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy
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
        # True on the copies the Paradigm trigger casts — copies cease to
        # exist after resolving and never re-register Paradigm.
        self.is_paradigm_copy: bool = False

    def on_resolve(self, game: "GameState") -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # 1. Exile from the top of the library until total mana value >= 4
        #    (or the library runs out).
        library = controller.zones[Zone.LIBRARY]
        exile_zone = controller.zones[Zone.EXILE]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            card = library.top(1)[0]
            library.remove(card)
            exile_zone.add(card)
            exiled.append(card)
            total_mv += getattr(card, "mana_cost", ManaCost()).cmc

        # 2. You may cast any number of them for free (lands are not
        #    castable and stay exiled).
        while True:
            candidates = [
                c
                for c in exiled
                if exile_zone.contains(c)
                and CardType.LAND not in getattr(c, "card_types", set())
            ]
            if not candidates:
                break
            try:
                chosen = controller.choose_card(
                    candidates, "cast an exiled card without paying its cost (None to stop)"
                )
            except Exception:
                chosen = None
            if chosen is None or chosen not in candidates:
                break
            try:
                cast_spell_free(game, controller, chosen, Zone.EXILE)
            except CastingError:
                exiled.remove(chosen)  # not castable right now — skip it

        # 3. Paradigm.
        if self.is_paradigm_copy:
            # A resolved copy ceases to exist — drop it from the stack zone
            # so the casting pipeline's stack→graveyard move finds nothing.
            stack_zone = controller.zones[Zone.STACK]
            if stack_zone.contains(self):
                stack_zone.remove(self)
            return

        # Then exile this spell (pre-empts the pipeline's graveyard move).
        move_to_zone(game, self, Zone.STACK, Zone.EXILE)

        # After you FIRST resolve a spell with this name, set up the
        # recurring cast — once per player, keyed by card name.
        registered = getattr(controller, "_paradigm_registered_names", None)
        if registered is None:
            registered = set()
            controller._paradigm_registered_names = registered
        if self.name in registered:
            return
        registered.add(self.name)
        self._register_paradigm_trigger(game, controller)

    def _register_paradigm_trigger(self, game: "GameState", controller: Any) -> None:
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return game.active_player is controller

        def _effect(game: "GameState") -> None:
            exile_zone = controller.zones[Zone.EXILE]
            if not exile_zone.contains(source):
                return
            try:
                wants = controller.choose_yes_no(
                    "cast a copy of Improvisation Capstone from exile for free?"
                )
            except Exception:
                wants = False
            if not wants:
                return
            from engine.casting import CastingError, cast_spell_free

            spell_copy = copy.copy(source)
            spell_copy.is_paradigm_copy = True
            exile_zone.add(spell_copy)
            try:
                cast_spell_free(game, controller, spell_copy, Zone.EXILE)
            except CastingError:
                exile_zone.remove(spell_copy)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
