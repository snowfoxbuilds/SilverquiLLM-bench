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
        self._paradigm_registered: bool = False

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
            card = library.top(1)[0]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(card)
            cost = getattr(card, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        # 2. May cast any number of them for free.  Lands are not spells and
        #    stay exiled.
        castable = [
            c for c in exiled
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        while castable:
            choice = controller.choose_card(
                castable,
                "Cast a spell from among the exiled cards without paying "
                "its mana cost (None to stop)",
            )
            if choice is None or choice not in castable:
                break
            castable.remove(choice)
            try:
                cast_spell_free(game, controller, choice, Zone.EXILE)
            except CastingError:
                pass  # not castable right now (e.g. no legal target)

        # 3. Paradigm — exile this spell (a no-op for copies, which are not
        #    in any zone), and after the FIRST resolution register the
        #    recurring first-main-phase trigger.
        owner = self.owner or controller
        if owner.zones[Zone.STACK].contains(self) or controller.zones[Zone.STACK].contains(self):
            move_to_zone(game, self, Zone.STACK, Zone.EXILE)

        if not self._paradigm_registered:
            self._paradigm_registered = True
            self._register_paradigm(game, controller)

    def _register_paradigm(self, game: GameState, controller: Any) -> None:
        """At the beginning of each of your first main phases, you may cast
        a copy of this card from exile without paying its mana cost."""
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.stack import StackObject, copy_spell
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            if game.active_player is not controller:
                return False
            owner = source.owner or controller
            return owner.zones[Zone.EXILE].contains(source)

        def _effect(game: GameState) -> None:
            owner = source.owner or controller
            if not owner.zones[Zone.EXILE].contains(source):
                return
            if not controller.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile without "
                "paying its mana cost?"
            ):
                return
            # The copy is a spell copy: it resolves without ever existing in
            # a zone, so the exiled original stays in exile.
            temp_so = StackObject(source=source, controller=controller, targets=[])
            copy_obj = copy_spell(game, temp_so, controller)
            game.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
