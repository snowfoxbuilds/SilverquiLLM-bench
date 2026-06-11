"""Card implementation for Exhibition Tidecaller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ExhibitionTidecaller(Creature):
    """Exhibition Tidecaller — {U} — Creature — Djinn Wizard — 0/2.

    Opus — Whenever you cast an instant or sorcery spell, target player
    mills three cards. If five or more mana was spent to cast that spell,
    that player mills ten cards instead.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Exhibition Tidecaller")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Djinn", "Wizard"})
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register opus trigger."""
        pass

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Opus: mill target player on instant/sorcery cast."""
        spell = getattr(event, "spell", None) or getattr(event, "card", None)
        if spell is None:
            return

        # Only triggers on instants/sorceries
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return

        # Only triggers on controller's spells
        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if caster is not self.controller:
            return

        # Determine target player from event targets
        targets = getattr(event, "targets", None) or []
        target_player = None
        for t in targets:
            if hasattr(t, "life"):  # It's a player
                target_player = t
                break

        if target_player is None:
            return

        # Determine mana spent
        mana_cost = getattr(spell, "mana_cost", None)
        mana_spent = getattr(event, "mana_spent", 0)
        if mana_spent == 0 and mana_cost is not None:
            mana_spent = mana_cost.cmc

        # Mill amount
        mill_count = 10 if mana_spent >= 5 else 3

        # Mill cards from target player's library
        library = game.get_library(target_player)
        graveyard = game.get_graveyard(target_player)
        lib_cards = library.get_all()
        to_mill = lib_cards[-mill_count:] if len(lib_cards) >= mill_count else lib_cards[:]
        for card in to_mill:
            library.remove(card)
            graveyard.add(card)
