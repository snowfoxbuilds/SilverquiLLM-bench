"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


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
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # 1. Exile from the top of the library until total MV >= 4.
        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_card = library.top(1)[0]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            total_mv += getattr(top_card, "mana_cost", ManaCost()).cmc

        # 2. May cast any number of the exiled spells for free (lands and
        #    other uncastables stay exiled).
        castable = [
            c
            for c in exiled
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        for card in castable:
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying "
                    "its mana cost?"
                ):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                pass

        # 3. Paradigm.
        self._setup_paradigm(game, controller)

    # ------------------------------------------------------------------
    # Paradigm — card-local
    # ------------------------------------------------------------------

    def _setup_paradigm(self, game: "GameState", controller: "Player") -> None:
        from engine.events import (
            BeginningOfPrecombatMainTriggeredEvent,
            SpellToGraveyardReplacementEvent,
        )
        from engine.replacement_effects import ReplacementEffect
        from engine.triggers import TriggerRegistration

        source = self
        is_copy = getattr(self, "_paradigm_copy", False)

        # "Then exile this spell" — redirect this spell's stack→graveyard
        # move.  A resolved copy instead ceases to exist (rule 707.10a).
        def _repl_condition(game: Any, event: Any) -> bool:
            return event.card is source

        def _replacement(game: Any, event: Any) -> Any:
            game.replacement_manager.unregister(source)
            if is_copy:
                stack_zone = controller.zones[Zone.STACK]
                if stack_zone.contains(source):
                    stack_zone.remove(source)
                event.prevented = True
            else:
                event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=SpellToGraveyardReplacementEvent,
                source=source,
                condition=_repl_condition,
                replacement=_replacement,
                controller=controller,
            )
        )

        # Recurring "cast a copy from exile at each of your first main
        # phases" — registered only on the FIRST resolution of a spell
        # with this name for this controller.
        for reg in game.trigger_manager.get_triggers():
            existing = reg.source
            if (
                getattr(existing, "_paradigm_name", None) == self.name
                and getattr(existing, "_paradigm_controller", None)
                is controller
            ):
                return

        original = self
        marker = type(
            "ParadigmMarker",
            (),
            {"_paradigm_name": self.name, "_paradigm_controller": controller},
        )()

        def _condition(game: Any, event: Any) -> bool:
            return game.active_player is controller

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            owner = getattr(original, "owner", controller) or controller
            if not owner.zones[Zone.EXILE].contains(original):
                return  # the exiled card left exile — stop offering casts
            if not controller.choose_yes_no(
                f"Cast a copy of {original.name} from exile without paying "
                "its mana cost?"
            ):
                return
            spell_copy = _copy.copy(original)
            spell_copy._paradigm_copy = True
            spell_copy.owner = controller
            spell_copy.controller = controller
            exile_zone = controller.zones[Zone.EXILE]
            exile_zone.add(spell_copy)
            try:
                cast_spell_free(game, controller, spell_copy, Zone.EXILE)
            except Exception:
                if exile_zone.contains(spell_copy):
                    exile_zone.remove(spell_copy)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=marker,
                controller=controller,
            )
        )
