"""Tests for SOS 107 — Archaic's Agony.

Archaic's Agony is a sorcery with Converge that deals X damage to a target
creature (X = number of colors of mana spent), then exiles cards from the
top of the caster's library equal to the excess damage dealt. Those exiled
cards may be played until end of the caster's next turn.
"""

from __future__ import annotations

from cards.sos.sos_107.card_impl import ArchaicsAgony
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game


class TestArchaicsAgonyProperties:
    """Static card data should match the SOS 107 spec."""

    def test_is_sorcery(self) -> None:
        card = ArchaicsAgony(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = ArchaicsAgony(owner=None)
        assert card.name == "Archaic's Agony"

    def test_mana_cost(self) -> None:
        card = ArchaicsAgony(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{R}")

    def test_has_sorcery_type(self) -> None:
        card = ArchaicsAgony(owner=None)
        assert CardType.SORCERY in card.card_types


class TestArchaicsAgonyConvergeDamage:
    """Converge: damage equals number of colors of mana spent."""

    def test_one_color_deals_one_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", base_power=2, base_toughness=4, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 1
        card.targets = [target]
        card.on_resolve(game)

        assert target.damage_marked == 1

    def test_three_colors_deals_three_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", base_power=2, base_toughness=4, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 3
        card.targets = [target]
        card.on_resolve(game)

        assert target.damage_marked == 3

    def test_five_colors_deals_five_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", base_power=2, base_toughness=6, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 5
        card.targets = [target]
        card.on_resolve(game)

        assert target.damage_marked == 5

    def test_zero_colors_deals_zero_damage(self) -> None:
        """If somehow zero colors spent (all colorless), no damage dealt."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 0
        card.targets = [target]
        card.on_resolve(game)

        assert target.damage_marked == 0


class TestArchaicsAgonyExcessDamageExile:
    """Excess damage exiles cards from the top of the caster's library."""

    def test_excess_damage_exiles_correct_count(self) -> None:
        """3 damage to a 1-toughness creature => 2 excess => exile 2 cards."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Mite", base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)

        # Put cards in p1's library to exile
        lib_cards = []
        for i in range(5):
            c = Creature(name=f"LibCard{i}", base_power=1, base_toughness=1, owner=p1)
            lib_cards.append(c)
        for c in lib_cards:
            game.get_library(p1).add(c)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 3  # 3 damage, 1 toughness => 2 excess
        card.targets = [target]
        card.on_resolve(game)

        exile_zone = game.get_exile(p1)
        assert len(exile_zone.get_all()) == 2

    def test_no_excess_means_no_exile(self) -> None:
        """Damage exactly equal to toughness => 0 excess => no exile."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", base_power=2, base_toughness=3, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)

        # Put cards in p1's library
        for i in range(5):
            c = Creature(name=f"LibCard{i}", base_power=1, base_toughness=1, owner=p1)
            game.get_library(p1).add(c)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 3  # 3 damage to 3-toughness creature => 0 excess
        card.targets = [target]
        card.on_resolve(game)

        exile_zone = game.get_exile(p1)
        assert len(exile_zone.get_all()) == 0

    def test_damage_less_than_toughness_no_exile(self) -> None:
        """Damage less than toughness => no lethal => no excess => no exile."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", base_power=2, base_toughness=5, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)

        for i in range(5):
            c = Creature(name=f"LibCard{i}", base_power=1, base_toughness=1, owner=p1)
            game.get_library(p1).add(c)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 2  # 2 damage to 5-toughness creature
        card.targets = [target]
        card.on_resolve(game)

        exile_zone = game.get_exile(p1)
        assert len(exile_zone.get_all()) == 0

    def test_excess_limited_by_library_size(self) -> None:
        """If library has fewer cards than excess, exile only what's there."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Mite", base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)

        # Only 1 card in library but 4 excess
        c = Creature(name="OnlyCard", base_power=1, base_toughness=1, owner=p1)
        game.get_library(p1).add(c)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 5  # 5 damage to 1-toughness => 4 excess, but only 1 card
        card.targets = [target]
        card.on_resolve(game)

        exile_zone = game.get_exile(p1)
        assert len(exile_zone.get_all()) == 1

    def test_five_colors_to_one_toughness_exiles_four(self) -> None:
        """5 damage to 1-toughness creature => 4 excess => exile 4."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Mite", base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)

        for i in range(10):
            c = Creature(name=f"LibCard{i}", base_power=1, base_toughness=1, owner=p1)
            game.get_library(p1).add(c)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 5
        card.targets = [target]
        card.on_resolve(game)

        exile_zone = game.get_exile(p1)
        assert len(exile_zone.get_all()) == 4

    def test_prior_damage_counts_for_excess(self) -> None:
        """If creature already has damage marked, excess accounts for it.
        
        Excess damage = damage dealt - remaining toughness.
        Remaining toughness = toughness - existing damage.
        So a 3-toughness creature with 1 damage already marked needs only
        2 more damage to die; dealing 3 gives 1 excess.
        """
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", base_power=2, base_toughness=3, owner=p2, controller=p2)
        target.damage_marked = 1  # Already has 1 damage
        game.get_battlefield(p2).add(target)

        for i in range(5):
            c = Creature(name=f"LibCard{i}", base_power=1, base_toughness=1, owner=p1)
            game.get_library(p1).add(c)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 3  # 3 damage; remaining toughness = 3-1=2; excess = 3-2=1
        card.targets = [target]
        card.on_resolve(game)

        exile_zone = game.get_exile(p1)
        assert len(exile_zone.get_all()) == 1


class TestArchaicsAgonyExiledCardsPlayable:
    """Exiled cards should be marked as playable until end of next turn."""

    def test_exiled_cards_have_playable_marker(self) -> None:
        """Cards exiled by Archaic's Agony should be marked as playable."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Mite", base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)

        lib_card = Creature(name="ExiledCard", base_power=2, base_toughness=2, owner=p1)
        game.get_library(p1).add(lib_card)

        card = ArchaicsAgony(owner=p1, controller=p1)
        card.colors_spent = 2  # 2 damage to 1-toughness => 1 excess => exile 1
        card.targets = [target]
        card.on_resolve(game)

        exile_zone = game.get_exile(p1)
        exiled = exile_zone.get_all()
        assert len(exiled) == 1
        # The exiled card should have some marker indicating it's playable
        exiled_card = exiled[0]
        assert getattr(exiled_card, "playable_by", None) == p1 or \
               getattr(exiled_card, "may_be_played_by", None) == p1 or \
               getattr(exiled_card, "impulse_draw", False) is True
