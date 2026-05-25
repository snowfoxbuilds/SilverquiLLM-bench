"""Audited tests for FDN 24 — Squad Rallier."""

from __future__ import annotations

from card_impl import SquadRallier
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSquadRallierBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SquadRallier(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SquadRallier(owner=None)
        assert card.name == "Squad Rallier"

    def test_mana_cost(self) -> None:
        card = SquadRallier(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{W}")

    def test_power_toughness(self) -> None:
        card = SquadRallier(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_subtypes(self) -> None:
        card = SquadRallier(owner=None)
        assert "Human" in card.subtypes
        assert "Scout" in card.subtypes

    def test_has_activated_ability(self) -> None:
        card = SquadRallier(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1


class TestSquadRallierAbility:
    """Activated ability: look at top 4, may take creature with power <= 2."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        rallier = SquadRallier(owner=p1, controller=p1)
        game.get_battlefield(p1).add(rallier)
        return game, p1, rallier

    def test_eligible_creature_goes_to_hand(self) -> None:
        game, p1, rallier = self._setup()
        # Put cards on top of library
        lib = p1.zones[Zone.LIBRARY]
        small = Creature(name="Small", base_power=2, base_toughness=2, owner=p1, controller=p1)
        filler1 = Creature(name="Filler1", base_power=5, base_toughness=5, owner=p1, controller=p1)
        filler2 = Creature(name="Filler2", base_power=5, base_toughness=5, owner=p1, controller=p1)
        filler3 = Creature(name="Filler3", base_power=5, base_toughness=5, owner=p1, controller=p1)
        for c in [small, filler1, filler2, filler3]:
            lib.add(c)
        # Give mana
        p1.mana_pool.add(ManaType.COLORLESS, 3)
        # Script the player to choose the small creature
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(small)
        ability = rallier.get_activated_abilities()[0]
        assert ability.cost(game, rallier)
        ability.effect(game)
        hand_names = [getattr(c, "name", "") for c in p1.zones[Zone.HAND].get_all()]
        assert "Small" in hand_names

    def test_empty_library_does_not_error(self) -> None:
        game, p1, rallier = self._setup()
        p1.mana_pool.add(ManaType.COLORLESS, 3)
        ability = rallier.get_activated_abilities()[0]
        assert ability.cost(game, rallier)
        ability.effect(game)  # Should not raise
