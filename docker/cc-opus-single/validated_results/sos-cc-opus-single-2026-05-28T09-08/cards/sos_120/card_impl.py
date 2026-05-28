"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Creature, Instant, Land, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone -- {5}{R}{R} -- Sorcery -- Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells
    from among them without paying their mana costs.

    Paradigm (Then exile this spell. After you first resolve a spell
    with this name, you may cast a copy of it from exile without paying
    its mana cost at the beginning of each of your first main phases.)

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
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first "
            "main phases.)",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """Resolve Improvisation Capstone:

        1. Exile cards from the top of library until total MV >= 4.
        2. Cast any number of non-land spells from among them for free.
        3. Paradigm: exile self, register delayed trigger for recurrence.
        """
        controller = self.controller if self.controller is not None else self.owner
        if controller is None:
            # Still need to handle paradigm self-exile even with no controller
            return

        # --- Step 1: Exile from library until total MV >= 4 ---
        exiled_cards = self._exile_from_library(game, controller)

        # --- Step 2: Free-cast spells from among exiled cards ---
        self._free_cast_exiled(game, controller, exiled_cards)

        # --- Step 3: Paradigm -- self-exile ---
        self._paradigm_self_exile(game, controller)

        # --- Step 4: Paradigm -- register delayed trigger for recurrence ---
        self._paradigm_register_recurrence(game, controller)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _exile_from_library(
        self, game: "GameState", controller: Any
    ) -> list[Any]:
        """Exile cards from top of library until total MV >= 4.

        Returns the list of cards exiled from the library.
        """
        library = controller.zones[Zone.LIBRARY]
        exile = game.get_exile(controller)
        exiled: list[Any] = []
        total_mv = 0

        while len(library) > 0 and total_mv < 4:
            # Top of library is the last element
            top_cards = library.top(1)
            if not top_cards:
                break
            card = top_cards[0]
            library.remove(card)
            exile.add(card)
            exiled.append(card)

            card_cost = getattr(card, "mana_cost", None)
            if card_cost is not None:
                total_mv += card_cost.cmc
            # Cards with no mana_cost contribute 0

        return exiled

    def _free_cast_exiled(
        self, game: "GameState", controller: Any, exiled_cards: list[Any]
    ) -> None:
        """Cast any number of spells from among the exiled cards for free.

        Lands are not spells and cannot be cast this way.  Cards remain in
        exile until their StackObject resolves -- this matches the MTG rule
        that a spell moves from its zone to the stack when cast and then to
        its destination on resolution.
        """
        exile = game.get_exile(controller)

        for card in exiled_cards:
            # Lands cannot be cast as spells
            if isinstance(card, Land):
                continue
            card_types = getattr(card, "card_types", set())
            if CardType.LAND in card_types:
                continue

            # Set up ownership/control for the free cast
            card.controller = controller
            if card.owner is None:
                card.owner = controller

            # For creatures, push a StackObject that resolves to battlefield
            if CardType.CREATURE in card_types:
                def _make_creature_resolve(c: Any) -> Any:
                    def _resolve(g: "GameState") -> None:
                        # Remove from exile when the spell resolves
                        ex = g.get_exile(controller)
                        if ex.contains(c):
                            ex.remove(c)
                        c.on_resolve(g)
                        bf = g.get_battlefield(controller)
                        bf.add(c)
                        c.summoning_sick = True
                        if hasattr(c, "register_triggers"):
                            c.register_triggers(g)
                        if hasattr(c, "register_replacement_effects"):
                            c.register_replacement_effects(g)
                    return _resolve

                stack_obj = StackObject(
                    source=card,
                    controller=controller,
                    targets=[],
                    on_resolve=_make_creature_resolve(card),
                )
                game.stack.push(stack_obj)
            elif CardType.INSTANT in card_types or CardType.SORCERY in card_types or isinstance(card, (Instant, Sorcery)):
                # For instants/sorceries, push to stack; on resolve go to graveyard
                def _make_spell_resolve(c: Any) -> Any:
                    def _resolve(g: "GameState") -> None:
                        # Remove from exile when the spell resolves
                        ex = g.get_exile(controller)
                        if ex.contains(c):
                            ex.remove(c)
                        c.on_resolve(g)
                        gy = g.get_graveyard(controller)
                        gy.add(c)
                    return _resolve

                stack_obj = StackObject(
                    source=card,
                    controller=controller,
                    targets=[],
                    on_resolve=_make_spell_resolve(card),
                )
                game.stack.push(stack_obj)
            else:
                # For other permanents (enchantments, artifacts, planeswalkers),
                # push to stack; on resolve go to battlefield like creatures
                def _make_permanent_resolve(c: Any) -> Any:
                    def _resolve(g: "GameState") -> None:
                        # Remove from exile when the spell resolves
                        ex = g.get_exile(controller)
                        if ex.contains(c):
                            ex.remove(c)
                        c.on_resolve(g)
                        bf = g.get_battlefield(controller)
                        bf.add(c)
                        if hasattr(c, "register_triggers"):
                            c.register_triggers(g)
                        if hasattr(c, "register_replacement_effects"):
                            c.register_replacement_effects(g)
                    return _resolve

                stack_obj = StackObject(
                    source=card,
                    controller=controller,
                    targets=[],
                    on_resolve=_make_permanent_resolve(card),
                )
                game.stack.push(stack_obj)

    def _paradigm_self_exile(self, game: "GameState", controller: Any) -> None:
        """Paradigm: exile this spell after resolution (instead of graveyard).

        Looks for self on the stack zone and moves to exile.
        """
        exile = game.get_exile(controller)

        # Try to find and remove self from the stack zone
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(self):
            stack_zone.remove(self)

        # Add to exile if not already there
        if not exile.contains(self):
            exile.add(self)

    def _paradigm_register_recurrence(
        self, game: "GameState", controller: Any
    ) -> None:
        """Paradigm: register a delayed trigger that fires at the beginning
        of each of the controller's first main phases, creating a copy of
        this spell that can be cast for free.
        """
        source = self
        capstone_controller = controller

        def _condition(game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            """Only fire for the controller's main phase."""
            return getattr(event, "player", None) is capstone_controller

        def _effect(game: "GameState") -> None:
            """Create a copy of Improvisation Capstone and put it on the stack
            (or in exile for casting). The copy has the same on_resolve logic."""
            # Create a copy of the capstone
            capstone_copy = ImprovisationCapstone(
                owner=capstone_controller,
                controller=capstone_controller,
            )

            # Put the copy on the stack as a free-cast spell.
            # IMPORTANT: Only run the exile-from-library and free-cast steps,
            # NOT the paradigm self-exile and trigger registration.  Otherwise
            # each copy would register another trigger, causing exponential growth.
            def _copy_resolve(g: "GameState") -> None:
                exiled = capstone_copy._exile_from_library(g, capstone_controller)
                capstone_copy._free_cast_exiled(g, capstone_controller, exiled)

            stack_obj = StackObject(
                source=capstone_copy,
                controller=capstone_controller,
                targets=[],
                on_resolve=_copy_resolve,
            )
            game.stack.push(stack_obj)

        trigger = TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=source,
            controller=capstone_controller,
        )
        game.trigger_manager.register(trigger)
