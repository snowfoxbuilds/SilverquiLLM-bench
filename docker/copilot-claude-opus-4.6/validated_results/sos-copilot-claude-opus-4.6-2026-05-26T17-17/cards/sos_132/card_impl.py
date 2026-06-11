"""Card implementation for Tablet of Discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Artifact, ManaAbility
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TabletOfDiscovery(Artifact):
    """Tablet of Discovery — {2}{R} — Artifact.

    When this artifact enters, mill a card. You may play that card this turn.
    {T}: Add {R}.
    {T}: Add {R}{R}. Spend this mana only to cast instant and sorcery spells.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tablet of Discovery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault(
            "rules_text",
            "When this artifact enters, mill a card. You may play that card this turn.\n"
            "{T}: Add {R}.\n"
            "{T}: Add {R}{R}. Spend this mana only to cast instant and sorcery spells.",
        )
        super().__init__(**kwargs)
        self.playable_this_turn: list[Any] = []

    def on_enter_battlefield(self, game: "GameState") -> None:
        """ETB: Mill a card. You may play that card this turn."""
        controller = self.controller
        if controller is None:
            return
        if not controller.library:
            return
        # Mill: move top card of library to graveyard
        milled_card = controller.library.pop()
        graveyard = game.get_graveyard(controller)
        graveyard.add(milled_card)
        # Mark as playable this turn
        self.playable_this_turn.append(milled_card)
        milled_card.playable_this_turn = True

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return the two mana abilities."""
        source = self

        def _tap_cost(game: Any, src: Any = None) -> bool:
            if getattr(source, "is_tapped", False):
                return False
            source.is_tapped = True
            return True

        def _add_one_red(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 1)

        def _tap_cost2(game: Any, src: Any = None) -> bool:
            if getattr(source, "is_tapped", False):
                return False
            source.is_tapped = True
            return True

        def _add_two_red_restricted(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 2)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_one_red,
                description="{T}: Add {R}.",
            ),
            ManaAbility(
                cost=_tap_cost2,
                mana_produced=_add_two_red_restricted,
                description="{T}: Add {R}{R}. Spend this mana only to cast instant and sorcery spells.",
            ),
        ]

