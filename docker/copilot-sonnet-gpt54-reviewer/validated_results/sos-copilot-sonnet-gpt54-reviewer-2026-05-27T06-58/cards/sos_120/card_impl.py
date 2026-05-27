"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Sorcery
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
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards with total mana value 4 or greater. "
            "You may cast any number of spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell with this name, you may cast a copy "
            "of it from exile without paying its mana cost at the beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)
        self.exiled_castable_pool: list[CardImpl] = []
        self.paradigm_first_resolved: bool = False

    def _is_on_stack(self, game: GameState) -> bool:
        """Return True if this card is currently in any player's STACK zone."""
        for player in game.players:
            if player.zones[Zone.STACK].contains(self):
                return True
        return False

    def on_resolve(self, game: GameState) -> None:
        """Exile cards from top of library until total MV >= 4; then exile self (Paradigm)."""
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        exile = game.get_exile(controller)

        # --- Step 1: Exile cards until cumulative MV >= 4 ---
        total_mv = 0
        exiled_cards: list[CardImpl] = []

        while total_mv < 4:
            all_cards = library.get_all()
            if not all_cards:
                break
            top_card = all_cards[-1]  # top of library
            library.remove(top_card)
            exile.add(top_card)
            exiled_cards.append(top_card)
            mv = top_card.mana_cost.cmc if top_card.mana_cost is not None else 0
            total_mv += mv

        # Only non-land cards can be cast; filter lands out of the castable pool.
        self.exiled_castable_pool = [
            c for c in exiled_cards
            if CardType.LAND not in getattr(c, "card_types", set())
        ]

        # --- Step 2: Offer free casts during resolution ---
        # Give the controller the opportunity to cast any number of spells from
        # the exiled pool for free RIGHT NOW (during resolution).
        castable = list(self.exiled_castable_pool)
        while castable:
            try:
                chosen = controller.choose(
                    castable,
                    "Cast a spell for free from the exiled pool? (choose None to stop)",
                )
            except Exception:
                break
            if chosen is None or chosen not in castable:
                break
            self.cast_exiled_card(game, controller, chosen)
            # Refresh from the pool (cast_exiled_card removes the chosen card)
            castable = list(self.exiled_castable_pool)

        # --- Step 3: Paradigm — exile this spell instead of going to graveyard ---
        # If this card is on the stack (real casting pipeline), proactively move
        # it from the STACK zone to EXILE before _resolve_spell can move it to
        # GRAVEYARD.  The pipeline's zone move will then be a no-op (card not
        # found in STACK).
        # If called directly (unit tests), just add to exile directly.
        if self._is_on_stack(game):
            from engine.zones import move_zone as _move_zone
            stack_zone = controller.zones[Zone.STACK]
            exile_zone = controller.zones[Zone.EXILE]
            _move_zone(self, stack_zone, exile_zone)
        else:
            exile.add(self)

        # --- Step 4: Mark as first-resolved and register trigger ---
        if not self.paradigm_first_resolved:
            self.paradigm_first_resolved = True
            self._register_paradigm_trigger(game)

    def _register_paradigm_trigger(self, game: GameState) -> None:
        """Register a persistent trigger for the Paradigm mechanic."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.stack import StackObject
        from engine.triggers import TriggerRegistration

        source = self
        controller = self.controller

        def _condition(g: GameState, event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return (
                event.player is controller
                and getattr(event, "is_precombat", True)
            )

        def _effect(g: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            try:
                wants_cast = (
                    ctrl.choose_yes_no("Cast a copy of Improvisation Capstone for free?")
                    if hasattr(ctrl, "choose_yes_no")
                    else False
                )
            except Exception:
                wants_cast = False

            if wants_cast:
                copied = _copy.copy(source)
                copied.controller = ctrl
                copied.owner = getattr(source, "owner", ctrl)

                def _resolve_copy(inner_game: GameState) -> None:
                    copied.on_resolve(inner_game)

                stack_obj = StackObject(
                    source=copied,
                    controller=ctrl,
                    on_resolve=_resolve_copy,
                )
                g.stack.push(stack_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def cast_exiled_card(self, game: GameState, player: Player, card: CardImpl) -> None:
        """Cast *card* from the exiled castable pool for free.

        Validates that *card* is in ``exiled_castable_pool`` before casting.
        Only removes *card* from the pool after a successful free cast.
        """
        from engine.casting import cast_spell_free

        # Validate membership BEFORE any state mutation.
        if card not in self.exiled_castable_pool:
            return

        # Cast for free from exile (may raise CastingError on failure).
        cast_spell_free(game, player, card, Zone.EXILE)

        # Only remove from pool after a successful cast.
        self.exiled_castable_pool = [c for c in self.exiled_castable_pool if c is not card]
