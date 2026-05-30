"""Card implementation for Improvisation Capstone (Paradigm)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Phase, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _cmc(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return cost.cmc if cost is not None else 0


def _is_castable_spell(card: Any) -> bool:
    """A card is castable as a spell if it isn't a land."""
    return CardType.LAND not in getattr(card, "card_types", set())


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among them
    without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)
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
            "Paradigm",
        )
        super().__init__(**kwargs)
        self.colors: list[str] = ["R"]

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        self._resolve_main_effect(game, controller)

        # Paradigm: "Exile this spell" — redirect this card to exile instead
        # of the graveyard when it leaves the stack.
        self._exile_instead_of_graveyard = True

        # Paradigm: set up the per-precombat-main recast the first time a
        # spell with this name resolves under this controller.
        self._setup_paradigm(game, controller)

    def _resolve_main_effect(self, game: GameState, controller: Player) -> None:
        """Exile from library until total MV >= 4, then optionally free-cast them."""
        exiled = self._exile_until_mv(controller, 4)
        self._offer_free_casts(game, controller, exiled)

    @staticmethod
    def _exile_until_mv(controller: Player, threshold: int) -> list[Any]:
        library = controller.zones[Zone.LIBRARY]
        exile_zone = controller.zones[Zone.EXILE]
        exiled: list[Any] = []
        total = 0
        while total < threshold and len(library) > 0:
            card = library.top(1)[0]
            library.remove(card)
            exile_zone.add(card)
            exiled.append(card)
            total += _cmc(card)
        return exiled

    @staticmethod
    def _offer_free_casts(
        game: GameState, controller: Player, candidates: list[Any]
    ) -> None:
        from engine.casting import cast_spell_free

        for card in candidates:
            if not _is_castable_spell(card):
                continue
            if not controller.zones[Zone.EXILE].contains(card):
                continue
            if controller.choose_yes_no(f"Cast {card.name} without paying its mana cost?"):
                cast_spell_free(game, controller, card, Zone.EXILE)

    # ------------------------------------------------------------------
    # Paradigm — delayed per-main-phase recast
    # ------------------------------------------------------------------

    def _setup_paradigm(self, game: GameState, controller: Player) -> None:
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        active = getattr(controller, "_paradigm_active_names", None)
        if active is None:
            active = set()
            controller._paradigm_active_names = active  # type: ignore[attr-defined]
        if self.name in active:
            return  # Not the first resolution — the delayed trigger already exists.
        active.add(self.name)

        cls = type(self)
        spell_name = self.name
        sentinel = object()  # stable, never-unregistered source for this game

        def _condition(game: GameState, event: Any) -> bool:
            return (
                getattr(event, "player", None) is controller
                and getattr(event, "phase", None) == Phase.PRECOMBAT_MAIN
            )

        def _effect(game: GameState) -> None:
            from engine.casting import cast_spell_free

            copy = cls(owner=controller, controller=controller)
            # A spell copy is not a real card: marking it as a token lets the
            # token state-based action clean it up if it isn't cast (or after
            # it resolves and leaves the stack).
            copy.is_token = True
            controller.zones[Zone.EXILE].add(copy)
            if controller.choose_yes_no(
                f"Cast a copy of {spell_name} without paying its mana cost?"
            ):
                cast_spell_free(game, controller, copy, Zone.EXILE)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=sentinel,
                controller=controller,
            )
        )
