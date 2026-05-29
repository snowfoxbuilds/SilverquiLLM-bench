"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.casting import cast_spell_copy_free, cast_spell_free
from engine.types import CardType, ManaCost, Phase, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


ORACLE_TEXT = (
    "Exile cards from the top of your library until you exile cards with total "
    "mana value 4 or greater. You may cast any number of spells from among them "
    "without paying their mana costs.\n"
    "Paradigm (Then exile this spell. After you first resolve a spell with this "
    "name, you may cast a copy of it from exile without paying its mana cost at "
    "the beginning of each of your first main phases.)"
)


def _mana_value(card: Any) -> int:
    """Return *card*'s mana value, defaulting to 0 when it has no mana cost."""
    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is None:
        return 0
    return getattr(mana_cost, "cmc", 0)


def _is_nonland_spell(card: Any) -> bool:
    """Return True if *card* is a castable nonland spell."""
    return CardType.LAND not in getattr(card, "card_types", set())


def _resolved_paradigm_names(game: "GameState") -> set[tuple[int, str]]:
    """Return the game-wide set of controller/name pairs that already enabled Paradigm."""
    resolved = getattr(game, "_paradigm_first_resolutions", None)
    if isinstance(resolved, set):
        return resolved
    resolved = set()
    game._paradigm_first_resolutions = resolved  # type: ignore[attr-defined]
    return resolved


def _choose_next_spell_to_cast(
    controller: "Player",
    available_spells: list[Any],
) -> Any | None:
    """Let the controller choose which exiled spell to cast next."""
    if not available_spells:
        return None
    if len(available_spells) == 1:
        return available_spells[0]
    try:
        chosen = controller.choose_card(
            available_spells,
            "Choose an exiled spell to cast next",
        )
    except Exception:
        chosen = available_spells[0]
    if chosen not in available_spells:
        return available_spells[0]
    return chosen


def _schedule_paradigm_offer(
    game: "GameState",
    controller: "Player",
    exiled_card: Sorcery,
    resolved_turn: int,
) -> None:
    """Offer a free spell copy on each later first main phase while the card remains exiled."""
    def _offer(g: "GameState") -> None:
        exile = g.get_exile(controller)
        if not exile.contains(exiled_card):
            return

        if g.phase is not Phase.PRECOMBAT_MAIN or g.turn_number <= resolved_turn:
            g.schedule_beginning_of_next_main_phase(controller, _offer)
            return

        if controller.choose_yes_no(
            f"Cast a copy of {exiled_card.name} from exile without paying its mana cost?"
        ):
            exiled_card._is_paradigm_copy = True  # type: ignore[attr-defined]
            try:
                cast_spell_copy_free(g, controller, exiled_card)
            finally:
                if hasattr(exiled_card, "_is_paradigm_copy"):
                    delattr(exiled_card, "_is_paradigm_copy")

        g.schedule_beginning_of_next_main_phase(controller, _offer)

    game.schedule_beginning_of_next_main_phase(controller, _offer)


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault("rules_text", ORACLE_TEXT)
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Exile cards to a mana-value threshold, offer free casts, then set up Paradigm."""
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        exiled_cards: list[Any] = []
        total_mana_value = 0

        while total_mana_value < 4:
            library_cards = library.get_all()
            if not library_cards:
                break
            top_card = library_cards[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled_cards.append(top_card)
            total_mana_value += _mana_value(top_card)

        if not getattr(self, "_is_paradigm_copy", False):
            resolved_names = _resolved_paradigm_names(game)
            paradigm_key = (id(controller), self.name)
            if paradigm_key not in resolved_names:
                resolved_names.add(paradigm_key)
                _schedule_paradigm_offer(game, controller, self, game.turn_number)

        remaining_spells = [card for card in exiled_cards if _is_nonland_spell(card)]
        while remaining_spells:
            if not controller.choose_yes_no(
                "Cast an exiled spell without paying its mana cost?"
            ):
                break
            next_spell = _choose_next_spell_to_cast(controller, remaining_spells)
            if next_spell is None:
                break
            cast_spell_free(game, controller, next_spell, Zone.EXILE)
            remaining_spells.remove(next_spell)

        self.exile_if_resolved_from_stack = True  # type: ignore[attr-defined]
