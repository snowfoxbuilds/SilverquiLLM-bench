"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_MANA_COST = ManaCost(generic=5, pips={ManaType.RED: 2})


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
        kwargs.setdefault("mana_cost", _MANA_COST)
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\nParadigm "
            "(Then exile this spell. After you first resolve a spell with this "
            "name, you may cast a copy of it from exile without paying its mana "
            "cost at the beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)
        # Mutable list shared by shallow copies (copy.copy) so copies skip Paradigm.
        self._paradigm_registered = [False]

    def on_resolve(self, game: "GameState") -> None:
        """Exile from library until MV>=4, cast any for free, then Paradigm."""
        controller = self.controller
        if controller is None:
            return

        # 1. Peel top of library until cumulative mana value >= 4.
        library = game.get_library(controller)
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4:
            cards = library.get_all()
            if not cards:
                break
            top_card = cards[-1]
            from engine.zones import move_to_zone
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            mc = getattr(top_card, "mana_cost", None)
            total_mv += mc.cmc if mc else 0

        # 2. Player may cast any number of non-land exiled cards for free.
        from engine.casting import cast_spell_free
        castable = [
            c for c in exiled
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        for card in castable:
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for free?"
                ):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                pass

        # 3. Paradigm — only the first (real) resolution; copies share
        #    _paradigm_registered via shallow copy so they skip this step.
        if not self._paradigm_registered[0]:
            self._paradigm_registered[0] = True
            _do_paradigm(game, self, controller)


def _do_paradigm(
    game: "GameState", card: ImprovisationCapstone, controller: Any
) -> None:
    """Exile self after resolve and register a recurring copy trigger."""
    # Register replacement: spell goes to exile instead of graveyard.
    from engine.events import SpellMovesToGraveyardReplacementEvent
    from engine.replacement_effects import ReplacementEffect

    active = [True]

    def _condition(g: Any, event: Any) -> bool:
        return active[0] and event.spell is card

    def _replacement(g: Any, event: Any) -> Any:
        active[0] = False
        event.destination = "exile"
        return event

    game.replacement_manager.register(
        ReplacementEffect(
            event_type=SpellMovesToGraveyardReplacementEvent,
            source=card,
            condition=_condition,
            replacement=_replacement,
            controller=controller,
        )
    )

    # Register recurring trigger at beginning of each of controller's main phases.
    _register_paradigm_trigger(game, card, controller)


def _register_paradigm_trigger(
    game: "GameState", exiled_card: ImprovisationCapstone, controller: Any
) -> None:
    """At beginning of each of controller's precombat main phases, may cast a copy."""
    from engine.events import BeginningOfPrecombatMainTriggeredEvent
    from engine.stack import StackObject
    from engine.triggers import TriggerRegistration

    sentinel = object()

    def _condition(g: Any, event: Any) -> bool:
        return g.active_player is controller

    def _effect(g: "GameState") -> None:
        try:
            if not controller.choose_yes_no(
                f"Cast a copy of {exiled_card.name} for free?"
            ):
                return
        except Exception:
            return

        # Shallow copy shares _paradigm_registered (already True) → skips Paradigm.
        copy_card = _copy.copy(exiled_card)
        copy_card.controller = controller
        copy_card.owner = getattr(exiled_card, "owner", controller)

        copy_so = StackObject(
            source=copy_card,
            controller=controller,
            targets=[],
        )

        def _resolve_copy(g2: "GameState") -> None:
            copy_card.chosen_targets = copy_so.targets
            copy_card.on_resolve(g2)

        copy_so.on_resolve = _resolve_copy
        g.stack.push(copy_so)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=sentinel,
            controller=controller,
        )
    )
