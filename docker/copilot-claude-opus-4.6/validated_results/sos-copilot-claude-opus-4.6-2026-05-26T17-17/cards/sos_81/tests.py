"""Tests for SOS 81 — End of the Hunt."""

from __future__ import annotations

from cards.sos.sos_81.card_impl import EndOfTheHunt
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestEndOfTheHuntProperties:
    """Static card data should match the SOS 81 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(EndOfTheHunt(owner=None), Sorcery)

    def test_name(self) -> None:
        assert EndOfTheHunt(owner=None).name == "End of the Hunt"

    def test_mana_cost(self) -> None:
        assert EndOfTheHunt(owner=None).mana_cost == ManaCost.parse("{1}{B}")


class TestEndOfTheHuntTargeting:
    """Targets an opponent."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        reqs = EndOfTheHunt(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1


class TestEndOfTheHuntResolution:
    """Opponent exiles creature/planeswalker with greatest mana value."""

    def test_exiles_highest_mana_value_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Opponent has two creatures with different mana values
        small = Creature(name="Small Bear", owner=p2, controller=p2,
                         base_power=1, base_toughness=1)
        small.card_types = {CardType.CREATURE}
        small.mana_cost = ManaCost.parse("{1}{G}")  # mv 2

        big = Creature(name="Big Dragon", owner=p2, controller=p2,
                       base_power=5, base_toughness=5)
        big.card_types = {CardType.CREATURE}
        big.mana_cost = ManaCost.parse("{4}{R}{R}")  # mv 6

        set_board_state(game, 1, battlefield=[small, big])

        spell = EndOfTheHunt(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        # Big Dragon should be exiled (highest mana value)
        bf = game.get_battlefield(p2)
        bf_names = [c.name for c in bf.cards] if hasattr(bf, 'cards') else [c.name for c in bf]
        assert "Big Dragon" not in bf_names
        assert "Small Bear" in bf_names

    def test_opponent_chooses_among_tied_mana_values(self) -> None:
        """When tied, the opponent chooses which to exile."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        bear1 = Creature(name="Bear A", owner=p2, controller=p2,
                         base_power=2, base_toughness=2)
        bear1.card_types = {CardType.CREATURE}
        bear1.mana_cost = ManaCost.parse("{1}{G}")

        bear2 = Creature(name="Bear B", owner=p2, controller=p2,
                         base_power=2, base_toughness=2)
        bear2.card_types = {CardType.CREATURE}
        bear2.mana_cost = ManaCost.parse("{1}{G}")

        set_board_state(game, 1, battlefield=[bear1, bear2])

        spell = EndOfTheHunt(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        # One of the two bears should be exiled
        bf = game.get_battlefield(p2)
        bf_names = [c.name for c in bf.cards] if hasattr(bf, 'cards') else [c.name for c in bf]
        assert len(bf_names) == 1

    def test_no_creatures_is_noop(self) -> None:
        """If opponent has no creatures/planeswalkers, nothing happens."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        set_board_state(game, 1, battlefield=[])

        spell = EndOfTheHunt(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        # Should not raise
        spell.on_resolve(game)
