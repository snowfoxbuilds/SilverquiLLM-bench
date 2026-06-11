"""Card implementation for Inkling Mascot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class InklingMascot(Creature):
    """Inkling Mascot — {W}{B} — 2/2 — Creature — Inkling Cat.

    Repartee — Whenever you cast an instant or sorcery spell that targets a
    creature, this creature gains flying until end of turn. Surveil 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inkling Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{B}"))
        kwargs.setdefault("subtypes", {"Inkling", "Cat"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self.keywords_granted: set = set()

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Repartee: gain flying + surveil 1 when controller casts instant/sorcery targeting a creature."""
        spell = getattr(event, "spell", None) or getattr(event, "card", None)
        if spell is None:
            return

        # Only triggers on controller's spells
        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if caster is not self.controller:
            return

        # Only instant or sorcery
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return

        # Must target a creature
        targets = getattr(event, "targets", None) or []
        targets_creature = False
        for t in targets:
            t_types = getattr(t, "card_types", set())
            if CardType.CREATURE in t_types:
                targets_creature = True
                break

        if not targets_creature:
            return

        # Gain flying until end of turn
        self.keywords_granted.add(Keyword.FLYING)

        # Surveil 1 - look at top card, put into graveyard (default behavior)
        controller = self.controller
        library = game.get_library(controller)
        lib_cards = library.get_all()
        if lib_cards:
            top_card = lib_cards[-1]
            library.remove(top_card)
            game.get_graveyard(controller).add(top_card)
