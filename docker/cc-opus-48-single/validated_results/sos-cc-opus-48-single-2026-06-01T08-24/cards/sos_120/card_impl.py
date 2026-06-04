"""Card implementation for Improvisation Capstone (SOS 120)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_castable_spell(card: Any) -> bool:
    """Return ``True`` if *card* can be cast as a spell (instant or sorcery).

    Lands are never spells, and permanents like creatures/enchantments would
    require timing/legality the free-cast among-exiled clause does not model
    here, so we restrict the free-cast to instants and sorceries.
    """
    types = getattr(card, "card_types", set()) or set()
    return CardType.INSTANT in types or CardType.SORCERY in types


def _mana_value(card: Any) -> int:
    """Return the mana value (cmc) of *card*, defaulting to 0."""
    cost = getattr(card, "mana_cost", None)
    if cost is None:
        return 0
    return getattr(cost, "cmc", 0)


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among them
    without paying their mana costs.

    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)

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
            "paying its mana cost at the beginning of each of your first main "
            "phases.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Exile from the top of the library to total MV >= 4, then free-cast.

        The Paradigm "exile this spell / recurring copy-cast from exile" clause
        is NOT implemented here — see the UNVERIFIED marker below.
        """
        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if controller is None:
            return

        exiled = self._exile_until_total_four(game, controller)
        self._free_cast_among(game, controller, exiled)

        # UNVERIFIED: Paradigm (exile this spell; after first resolving a spell
        # with this name, cast a copy of it from exile without paying its mana
        # cost at the beginning of each of your first main phases) — requires
        # copy-from-exile engine support (same gap marked UNVERIFIED for sos_13)
        # plus a recurring name-keyed delayed trigger. No engine surface exists
        # to model this without a large, fragile feature, so it is omitted.

    # ------------------------------------------------------------------
    # Exile-until-total-MV-4
    # ------------------------------------------------------------------

    def _exile_until_total_four(
        self, game: "GameState", controller: Any
    ) -> list[Any]:
        """Exile cards from the top of *controller*'s library until the running
        total mana value reaches 4 or greater. Returns the exiled cards."""
        from engine.game import exile as _exile

        library = game.get_library(controller)
        exiled: list[Any] = []
        total = 0
        # Top of library is the last element of the internal list.
        while total < 4 and len(library) > 0:
            top_cards = library.top(1)
            if not top_cards:
                break
            card = top_cards[-1]
            total += _mana_value(card)
            _exile(game, card)
            exiled.append(card)
        return exiled

    # ------------------------------------------------------------------
    # Free-cast among the exiled cards
    # ------------------------------------------------------------------

    def _free_cast_among(
        self, game: "GameState", controller: Any, exiled: list[Any]
    ) -> None:
        """Offer the controller to free-cast any number of the exiled spells.

        The "may cast any number" is modeled as a loop: each iteration asks the
        controller whether to cast another spell and, if so, which one. The loop
        ends when the controller declines or no castable spells remain.
        """
        from engine.casting import cast_spell_free

        while True:
            exile_zone = game.get_exile(controller)
            candidates = [
                c
                for c in exiled
                if _is_castable_spell(c) and exile_zone.contains(c)
            ]
            if not candidates:
                return

            if not self._wants_to_cast(controller):
                return

            choice = self._choose_spell(controller, candidates)
            if choice is None or not exile_zone.contains(choice):
                return

            try:
                cast_spell_free(game, controller, choice, Zone.EXILE)
            except Exception:
                # If a particular spell cannot be cast, stop rather than raise.
                return

    def _wants_to_cast(self, controller: Any) -> bool:
        """Ask the controller whether to free-cast another spell.

        Defaults to ``False`` (decline) when the player has no decision method,
        so resolution never blocks or raises in headless contexts.
        """
        choose_yes_no = getattr(controller, "choose_yes_no", None)
        if choose_yes_no is None:
            return False
        try:
            return bool(choose_yes_no("Cast a spell from among the exiled cards?"))
        except Exception:
            return False

    def _choose_spell(self, controller: Any, candidates: list[Any]) -> Any:
        """Ask the controller which exiled spell to free-cast."""
        choose_card = getattr(controller, "choose_card", None)
        if choose_card is None:
            return None
        try:
            selection = choose_card(candidates, "Choose a spell to cast for free")
        except Exception:
            return None
        if selection in candidates:
            return selection
        return None
