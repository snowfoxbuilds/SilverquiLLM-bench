"""Card implementation for Cephalid Inkmage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.card_queries import query_yes_no
from engine.continuous_effects import (
    DURATION_PERMANENT,
    ContinuousEffect,
    Layer,
)
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class CephalidInkmageAbility1:
    text = 'When this creature enters, surveil 3. (Look at the top three cards of your library, then put any number of them into your graveyard and the rest on top of your library in any order.)'


class CephalidInkmageAbility2:
    text = "Threshold — This creature can't be blocked as long as there are seven or more cards in your graveyard."


# endregion Printed abilities


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class CephalidInkmage(Creature):
    """Cephalid Inkmage — {2}{U} — 2/2 — Octopus Wizard.

    When this creature enters, surveil 3.
    Threshold — This creature can't be blocked as long as there are seven
    or more cards in your graveyard.

    FDN collector number 32.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cephalid Inkmage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Octopus", "Wizard"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, surveil 3.\n"
            "Threshold — This creature can't be blocked as long as there "
            "are seven or more cards in your graveyard.",
        )
        super().__init__(**kwargs)
        self._unblockable_effect_ref: ContinuousEffect | None = None

    def _enters(self, game: "GameState", controller: Any) -> None:
        """ETB: surveil 3."""
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]
        cards = list(library.get_all())
        if not cards:
            return
        # Surveil 3: look at top 3 cards (top is end of list)
        top_cards = cards[-min(3, len(cards)):]
        for card in reversed(top_cards):
            put_in_gy = query_yes_no(
                game, controller,
                f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?",
                source_card=self,
            )
            if put_in_gy:
                library.remove(card)
                controller.zones[Zone.GRAVEYARD].add(card)

    def register_triggers(self, game: "GameState") -> None:
        """Register threshold unblockable continuous effect."""
        from engine.triggers import register_enters_trigger

        register_enters_trigger(game, self, CephalidInkmageAbility1, self._enters)

        source = self

        def _apply_unblockable(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            if not _is_on_battlefield(game, source):
                return
            # Threshold: 7+ cards in graveyard
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            gy_count = len(list(graveyard.get_all()))
            if gy_count >= 7:
                # ENGINE LIMITATION: "can't be blocked" is modeled as a flag
                # on the creature. The engine may not fully support this in
                # combat resolution.
                source.unblockable = True
            else:
                source.unblockable = False

        self._unblockable_effect_ref = game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_unblockable,
            duration=DURATION_PERMANENT,
        ))

    def unregister_triggers(self, game: "GameState") -> None:
        """Clean up unblockable effect when leaving battlefield."""
        if self._unblockable_effect_ref is not None:
            game.effect_manager.remove(self._unblockable_effect_ref)
            self._unblockable_effect_ref = None
        self.unblockable = False
