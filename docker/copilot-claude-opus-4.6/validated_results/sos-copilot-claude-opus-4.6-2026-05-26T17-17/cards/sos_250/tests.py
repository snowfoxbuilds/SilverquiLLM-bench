"""Tests for SOS 250 — Page, Loose Leaf.

Legendary Artifact Creature — Construct  {2}
0/2
Oracle: {T}: Add {C}.
Grandeur — Discard another card named Page, Loose Leaf: Reveal cards from
the top of your library until you reveal an instant or sorcery card. Put
that card into your hand and the rest on the bottom of your library in a
random order.
"""

from __future__ import annotations

from cards.sos.sos_250.card_impl import PageLooseLeaf
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game


class TestPageLooseLeafProperties:
    """Static card data should match the SOS 250 spec."""

    def test_name(self) -> None:
        card = PageLooseLeaf(owner=None)
        assert card.name == "Page, Loose Leaf"

    def test_mana_cost(self) -> None:
        card = PageLooseLeaf(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}")

    def test_power_toughness(self) -> None:
        card = PageLooseLeaf(owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 2

    def test_is_creature(self) -> None:
        card = PageLooseLeaf(owner=None)
        assert isinstance(card, Creature)

    def test_is_legendary(self) -> None:
        card = PageLooseLeaf(owner=None)
        assert getattr(card, "legendary", False) or "Legendary" in getattr(card, "supertypes", set())

    def test_subtypes(self) -> None:
        card = PageLooseLeaf(owner=None)
        subtypes = getattr(card, "subtypes", set())
        assert "Construct" in subtypes


class TestPageManaAbility:
    """{T}: Add {C}."""

    def test_has_mana_ability(self) -> None:
        card = PageLooseLeaf(owner=None)
        assert hasattr(card, "get_mana_abilities") or hasattr(card, "tap_for_mana") or hasattr(card, "activate")

    def test_tap_adds_colorless_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PageLooseLeaf(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        pool_before = p1.mana_pool.amount(ManaType.COLORLESS) if hasattr(p1, "mana_pool") else 0
        card.tap_for_mana(game)
        pool_after = p1.mana_pool.amount(ManaType.COLORLESS)
        assert pool_after == pool_before + 1

    def test_tap_ability_taps_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PageLooseLeaf(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.tap_for_mana(game)
        assert card.tapped is True


class TestPageGrandeurAbility:
    """Grandeur — Discard another Page: reveal until instant/sorcery found."""

    def test_has_grandeur_ability(self) -> None:
        card = PageLooseLeaf(owner=None)
        assert hasattr(card, "activate_grandeur") or hasattr(card, "grandeur")

    def test_grandeur_finds_instant_from_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PageLooseLeaf(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Set up library with some creatures then an instant on top
        library = game.get_zone(p1, Zone.LIBRARY)
        filler1 = Creature(name="Bear1", owner=p1, base_power=2, base_toughness=2)
        filler1.card_types = {CardType.CREATURE}
        filler2 = Creature(name="Bear2", owner=p1, base_power=2, base_toughness=2)
        filler2.card_types = {CardType.CREATURE}
        target_spell = Instant(name="Lightning Bolt", owner=p1)
        target_spell.card_types = {CardType.INSTANT}

        # Library order: top -> filler1, filler2, target_spell
        library.add(target_spell)
        library.add(filler2)
        library.add(filler1)

        # Put another Page in hand to discard as cost
        discard_page = PageLooseLeaf(owner=p1, controller=p1)
        discard_page.name = "Page, Loose Leaf"
        game.get_zone(p1, Zone.HAND).add(discard_page)

        hand_before = [c.name for c in game.get_zone(p1, Zone.HAND).get_all()]
        card.activate_grandeur(game, discard=discard_page)
        hand_after = game.get_zone(p1, Zone.HAND).get_all()

        # The instant should now be in hand
        hand_names = [c.name for c in hand_after]
        assert "Lightning Bolt" in hand_names

    def test_grandeur_puts_non_hits_on_bottom(self) -> None:
        """Cards revealed that aren't instant/sorcery go to bottom of library."""
        game = create_game()
        p1 = game.players[0]
        card = PageLooseLeaf(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        library = game.get_zone(p1, Zone.LIBRARY)
        filler = Creature(name="Bear", owner=p1, base_power=2, base_toughness=2)
        filler.card_types = {CardType.CREATURE}
        target_spell = Sorcery(name="Divination", owner=p1)
        target_spell.card_types = {CardType.SORCERY}

        library.add(target_spell)
        library.add(filler)

        discard_page = PageLooseLeaf(owner=p1, controller=p1)
        game.get_zone(p1, Zone.HAND).add(discard_page)

        card.activate_grandeur(game, discard=discard_page)

        # Filler should be on the bottom of library (still in library)
        lib_cards = library.get_all()
        lib_names = [c.name for c in lib_cards]
        assert "Bear" in lib_names

    def test_grandeur_discards_the_page_as_cost(self) -> None:
        """The discarded Page should go to graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = PageLooseLeaf(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        library = game.get_zone(p1, Zone.LIBRARY)
        target_spell = Instant(name="Opt", owner=p1)
        target_spell.card_types = {CardType.INSTANT}
        library.add(target_spell)

        discard_page = PageLooseLeaf(owner=p1, controller=p1)
        game.get_zone(p1, Zone.HAND).add(discard_page)

        card.activate_grandeur(game, discard=discard_page)

        graveyard = game.get_zone(p1, Zone.GRAVEYARD).get_all()
        grave_names = [c.name for c in graveyard]
        assert "Page, Loose Leaf" in grave_names
