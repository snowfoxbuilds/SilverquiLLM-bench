"""Card implementation for Soaring Stoneglider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.game import exile
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


class SoaringStoneglider(Creature):
    """Soaring Stoneglider."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Soaring Stoneglider")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Elephant", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "As an additional cost to cast this spell, exile two cards from your graveyard or pay {1}{W}.\n"
            "Flying, vigilance",
        )
        super().__init__(**kwargs)
        self._graveyard_cards_to_exile_on_cast: list[CardImpl] = []
        self._use_graveyard_exile_payment = False

    def _can_prompt_for_choice(self, player: Player) -> bool:
        remaining_choices = getattr(player, "remaining_choices", None)
        return remaining_choices is None or remaining_choices > 0

    def _choose_graveyard_cards_to_exile(
        self,
        game: GameState,
        player: Player,
    ) -> list[CardImpl]:
        graveyard_cards = list(game.get_graveyard(player).get_all())
        if len(graveyard_cards) < 2:
            return []
        if len(graveyard_cards) == 2:
            return graveyard_cards

        chosen: list[CardImpl] = []
        remaining = list(graveyard_cards)
        for index in range(2):
            selection: CardImpl | None = None
            if self._can_prompt_for_choice(player):
                try:
                    candidate = player.choose_card(
                        remaining,
                        f"Choose card to exile for Soaring Stoneglider ({index + 1}/2)",
                    )
                except Exception:
                    candidate = None
                if candidate in remaining:
                    selection = candidate
            if selection is None:
                selection = remaining[0]
            chosen.append(selection)
            remaining.remove(selection)
        return chosen

    def get_additional_cast_cost(
        self,
        game: GameState,
        player: Player,
        from_zone: Zone,  # noqa: ARG002
    ) -> ManaCost:
        self._graveyard_cards_to_exile_on_cast = []
        self._use_graveyard_exile_payment = False

        graveyard = game.get_graveyard(player).get_all()
        if len(graveyard) >= 2:
            pay_with_mana = False
            if self._can_prompt_for_choice(player):
                try:
                    choice = player.choose(
                        ["exile", "pay"],
                        "Choose Soaring Stoneglider additional cost",
                    )
                except Exception:
                    choice = "exile"
                pay_with_mana = choice == "pay"
            if pay_with_mana:
                return ManaCost.parse("{1}")

            chosen_cards = self._choose_graveyard_cards_to_exile(game, player)
            if len(chosen_cards) == 2:
                self._graveyard_cards_to_exile_on_cast = chosen_cards
                self._use_graveyard_exile_payment = True
                return ManaCost()

        self._graveyard_cards_to_exile_on_cast = []
        self._use_graveyard_exile_payment = False
        return ManaCost.parse("{1}")

    def pay_additional_cast_costs(
        self,
        game: GameState,
        player: Player,  # noqa: ARG002
        from_zone: Zone,  # noqa: ARG002
    ) -> None:
        if not self._use_graveyard_exile_payment:
            self._graveyard_cards_to_exile_on_cast = []
            return
        for card in list(self._graveyard_cards_to_exile_on_cast):
            if game.get_graveyard(player).contains(card):
                exile(game, card)
        self._graveyard_cards_to_exile_on_cast = []
        self._use_graveyard_exile_payment = False
