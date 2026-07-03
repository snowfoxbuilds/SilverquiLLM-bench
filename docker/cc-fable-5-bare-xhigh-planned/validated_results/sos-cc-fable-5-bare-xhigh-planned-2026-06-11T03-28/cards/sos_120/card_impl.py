"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return cost.cmc if cost is not None else 0


def _register_exile_on_resolution(game: "GameState", spell: Any, controller: Any) -> None:
    """Paradigm's 'Exile this spell': one-shot redirect of the resolving
    spell's stack→graveyard move to exile."""
    from engine.events import MoveToGraveyardReplacementEvent
    from engine.replacement_effects import ReplacementEffect

    sentinel = object()

    def _condition(g: Any, event: Any) -> bool:
        return event.card is spell

    def _replacement(g: Any, event: Any) -> Any:
        event.destination = "exile"
        g.replacement_manager.unregister(sentinel)
        return event

    game.replacement_manager.register(ReplacementEffect(
        event_type=MoveToGraveyardReplacementEvent,
        source=sentinel,
        condition=_condition,
        replacement=_replacement,
        controller=controller,
    ))


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
        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_card = library.top(1)[0]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            total_mv += _mana_value(top_card)

        # 2. May cast any number of them for free (lands are not castable
        #    and stay exiled).
        castable = [
            c for c in exiled
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        for card in castable:
            if controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} without paying its "
                "mana cost?"
            ):
                try:
                    cast_spell_free(game, controller, card, Zone.EXILE)
                except CastingError:
                    pass  # stays exiled

        # 3. Paradigm — "Exile this spell" applies to every resolution
        #    (the original and any copies).
        _register_exile_on_resolution(game, self, controller)

        #    The recurring "cast a copy each of your first main phases"
        #    trigger is set up only the first time a spell with this name
        #    resolves for this player.
        resolved_names = getattr(controller, "_paradigm_resolved_names", None)
        if resolved_names is None:
            resolved_names = set()
            controller._paradigm_resolved_names = resolved_names
        if self.name in resolved_names:
            return
        resolved_names.add(self.name)
        self._register_paradigm_trigger(game, controller)

    def _register_paradigm_trigger(self, game: "GameState", controller: Any) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        original = self

        def _condition(g: Any, event: Any) -> bool:
            return g.active_player is controller

        def _effect(g: "GameState") -> None:
            if not controller.choose_yes_no(
                f"Cast a copy of {original.name} from exile without paying "
                "its mana cost?"
            ):
                return
            cp = _copy.copy(original)
            if hasattr(cp, "chosen_targets"):
                del cp.chosen_targets
            controller.zones[Zone.EXILE].add(cp)
            try:
                cast_spell_free(g, controller, cp, Zone.EXILE)
            except CastingError:
                controller.zones[Zone.EXILE].remove(cp)
                return
            # A spell copy ceases to exist once it leaves the stack; the
            # token state-based action models exactly that.
            cp.is_token = True

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=original,
            controller=controller,
        ))
