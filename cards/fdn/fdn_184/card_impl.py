"""Card implementation for Rune-Scarred Demon."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RuneScarredDemon(Creature):
    """Rune-Scarred Demon — {5}{B}{B} — 6/6 — Demon — Flying.

    When this creature enters, search your library for a card, put it
    into your hand, then shuffle.

    FDN collector number 184.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rune-Scarred Demon")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{B}{B}"))
        kwargs.setdefault("subtypes", {"Demon"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, search your library for a "
            "card, put it into your hand, then shuffle.",
        )
        super().__init__(**kwargs)

    def _tutor(self, game: "GameState") -> None:
        """Search library for any card, put into hand, shuffle."""
        controller = self.controller
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]
        candidates = library.get_all()
        if not candidates:
            return
        try:
            chosen = controller.choose_card(
                candidates,
                "Choose a card to put into your hand",
            )
        except Exception:
            chosen = candidates[0] if candidates else None
        if chosen is None:
            return
        library.remove(chosen)
        controller.zones[Zone.HAND].add(chosen)
        library.shuffle()

    def on_resolve(self, game: "GameState") -> None:
        """Tutor on resolve (for direct invocation / test compatibility)."""
        self._tutor(game)

    def register_triggers(self, game: "GameState") -> None:
        """ETB: search library for any card, put into hand, shuffle."""
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, data: dict) -> bool:
            return data.get("permanent") is source

        def _effect(game: "GameState") -> None:
            source._tutor(game)

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
