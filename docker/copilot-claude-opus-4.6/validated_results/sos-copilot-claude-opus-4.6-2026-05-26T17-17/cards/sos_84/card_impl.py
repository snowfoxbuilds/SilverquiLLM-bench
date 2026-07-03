"""Card implementation for Forum Necroscribe."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ForumNecroscribe(Creature):
    """Forum Necroscribe — {5}{B} — Creature — Troll Warlock.

    5/4. Ward—Discard a card.
    Repartee — Whenever you cast an instant or sorcery spell that targets a
    creature, return target creature card from your graveyard to the battlefield.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Forum Necroscribe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{B}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("subtypes", {"Troll", "Warlock"})
        kwargs.setdefault("keywords", Keyword.WARD)
        super().__init__(**kwargs)

    def on_repartee_trigger(self, game: "GameState", targeting_creature: Any = None) -> None:
        """Repartee trigger: return a creature card from graveyard to battlefield."""
        owner = self.controller or self.owner
        gy = game.get_graveyard(owner)

        # Find a creature card in graveyard
        creature_card = None
        for card in gy.get_all():
            types = getattr(card, "card_types", set())
            if CardType.CREATURE in types:
                creature_card = card
                break

        if creature_card is None:
            return

        # Move from graveyard to battlefield
        gy.remove(creature_card)
        bf = game.get_battlefield(owner)
        creature_card.controller = owner
        bf.add(creature_card)
