"""Card implementation for Page, Loose Leaf."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PageLooseLeaf(ArtifactCreature):
    """Page, Loose Leaf — {2} — 0/2 Legendary Artifact Creature — Construct.

    {T}: Add {C}.
    Grandeur — Discard another card named Page, Loose Leaf: Reveal cards from
    the top of your library until you reveal an instant or sorcery card. Put
    that card into your hand and the rest on the bottom of your library in a
    random order.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Page, Loose Leaf")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", {"Construct"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self.legendary = True

    def tap_for_mana(self, game: "GameState") -> None:
        """Tap to add {C}."""
        self.tapped = True
        controller = self.controller or self.owner
        controller.mana_pool.add(ManaType.COLORLESS, 1)

    def activate_grandeur(self, game: "GameState", discard: Any = None) -> None:
        """Grandeur ability: discard another Page, reveal until instant/sorcery found."""
        controller = self.controller or self.owner

        # Discard the Page as cost
        if discard is not None:
            hand = game.get_zone(controller, Zone.HAND)
            hand.remove(discard)
            graveyard = game.get_zone(controller, Zone.GRAVEYARD)
            graveyard.add(discard)

        # Reveal from top of library until instant or sorcery found
        library = game.get_zone(controller, Zone.LIBRARY)
        revealed_non_hits: list[Any] = []

        while len(library) > 0:
            top_cards = library.top(1)
            if not top_cards:
                break
            card = top_cards[0]
            library.remove(card)
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                # Put into hand
                hand = game.get_zone(controller, Zone.HAND)
                hand.add(card)
                break
            else:
                revealed_non_hits.append(card)

        # Put non-hits on bottom of library in random order
        import random
        random.shuffle(revealed_non_hits)
        for card in revealed_non_hits:
            library.add_to_bottom(card) if hasattr(library, "add_to_bottom") else library.add(card)
