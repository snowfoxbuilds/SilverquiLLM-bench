"""Card implementation for Campus Guide."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import (
    ArtifactCreature,
)
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class CampusGuideAbility1:
    text = 'When this creature enters, you may search your library for a basic land card, reveal it, then shuffle and put that card on top.'


# endregion Printed abilities


class CampusGuide(ArtifactCreature):
    """Campus Guide — {2} — 2/1 Golem. ETB: search for basic land on top."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Campus Guide")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Golem"}
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, you may search your library for a basic "
            "land card, reveal it, then shuffle and put that card on top.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that uses the stack."""
        from engine.triggers import register_enters_trigger

        register_enters_trigger(game, self, CampusGuideAbility1, self._enters)

    def _enters(self, game: "GameState", controller: Any) -> None:
        """You may search your library for a basic land card, reveal it, then
        shuffle and put that card on top."""
        from engine.card_queries import choose_object, query_yes_no

        library = controller.zones[Zone.LIBRARY]
        basics = [
            card for card in library.get_all()
            if CardType.LAND in getattr(card, "card_types", set())
            and Supertype.BASIC in getattr(card, "supertypes", set())
        ]
        if not query_yes_no(game, controller, "Search your library for a basic land card?", source_card=self):
            return
        chosen = choose_object(game, controller, basics, "Choose a basic land card", source_card=self, optional=True) if basics else None
        if chosen is not None:
            library.remove(chosen)
        library.shuffle(game)
        if chosen is not None:
            library.add(chosen)
