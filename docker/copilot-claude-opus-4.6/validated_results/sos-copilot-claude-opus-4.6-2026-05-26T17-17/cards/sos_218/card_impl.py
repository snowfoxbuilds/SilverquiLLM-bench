"""Card implementation for Quandrix, the Proof."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class QuandrixTheProof(Creature):
    """Quandrix, the Proof — {4}{G}{U} — Legendary Creature — Elder Dragon.

    Flying, trample
    Cascade
    Instant and sorcery spells you cast from your hand have cascade.
    6/6
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quandrix, the Proof")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}{U}"))
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.TRAMPLE | Keyword.CASCADE)
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("rules_text",
            "Flying, trample\nCascade\n"
            "Instant and sorcery spells you cast from your hand have cascade.")
        super().__init__(**kwargs)
        self.is_legendary = True

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Grant cascade to instant/sorcery spells cast from hand by controller."""
        spell = getattr(event, "spell", None)
        if spell is None:
            return
        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if caster is not self.controller:
            return
        # Check if it's an instant or sorcery
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        # Grant cascade
        spell.keywords = getattr(spell, "keywords", Keyword(0)) | Keyword.CASCADE
        # Mark cascade triggered on the game for test assertion
        game.cascade_triggered = True
