"""Tests for SOS 145 — Emeritus of Abundance // Regrowth.

Front face: Emeritus of Abundance — {2}{G} Creature — Elf Druid 3/4
  Vigilance
  This creature enters prepared.
  Whenever this creature attacks, if you control eight or more lands,
  this creature becomes prepared.

Back face: Regrowth — {1}{G} Sorcery (adventure/prepared side TBD)
"""

from __future__ import annotations

from cards.sos.sos_145.card_impl import EmeritusOfAbundanceRegrowth
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestEmeritusOfAbundanceProperties:
    """Static card data for the front face."""

    def test_is_creature(self) -> None:
        card = EmeritusOfAbundanceRegrowth(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfAbundanceRegrowth(owner=None)
        assert card.name == "Emeritus of Abundance"

    def test_mana_cost(self) -> None:
        card = EmeritusOfAbundanceRegrowth(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{G}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfAbundanceRegrowth(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_has_vigilance(self) -> None:
        card = EmeritusOfAbundanceRegrowth(owner=None)
        assert Keyword.VIGILANCE in card.keywords


class TestEmeritusEntersPrepared:
    """This creature enters the battlefield prepared."""

    def test_enters_prepared(self) -> None:
        """When ETB, creature should be in prepared state."""
        game = create_game()
        p1 = game.players[0]

        card = EmeritusOfAbundanceRegrowth(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        # After entering, should be prepared
        assert card.is_prepared is True

    def test_has_prepared_keyword(self) -> None:
        """Card should have the PREPARED keyword."""
        card = EmeritusOfAbundanceRegrowth(owner=None)
        assert Keyword.PREPARED in card.keywords


class TestEmeritusAttackTrigger:
    """Whenever this creature attacks, if 8+ lands, becomes prepared."""

    def _make_lands(self, owner, count):
        """Create dummy land permanents."""
        from engine.card import CardImpl
        lands = []
        for i in range(count):
            land = CardImpl(name=f"Forest_{i}", owner=owner, controller=owner)
            land.card_types = {CardType.LAND}
            lands.append(land)
        return lands

    def test_attack_with_eight_lands_becomes_prepared(self) -> None:
        """Attacking with 8+ lands makes creature prepared again."""
        game = create_game()
        p1 = game.players[0]

        card = EmeritusOfAbundanceRegrowth(owner=p1, controller=p1)
        # Simulate creature not being prepared (used its prepared ability)
        card.is_prepared = False

        lands = self._make_lands(p1, 8)
        set_board_state(game, 0, battlefield=[card] + lands)

        # Simulate attack trigger
        card.on_attack(game)

        assert card.is_prepared is True

    def test_attack_with_fewer_than_eight_lands_stays_unprepared(self) -> None:
        """Attacking with fewer than 8 lands does not re-prepare."""
        game = create_game()
        p1 = game.players[0]

        card = EmeritusOfAbundanceRegrowth(owner=p1, controller=p1)
        card.is_prepared = False

        lands = self._make_lands(p1, 7)
        set_board_state(game, 0, battlefield=[card] + lands)

        card.on_attack(game)

        assert card.is_prepared is False

    def test_attack_already_prepared_stays_prepared(self) -> None:
        """If already prepared, attacking with 8+ lands keeps it prepared."""
        game = create_game()
        p1 = game.players[0]

        card = EmeritusOfAbundanceRegrowth(owner=p1, controller=p1)
        card.is_prepared = True

        lands = self._make_lands(p1, 8)
        set_board_state(game, 0, battlefield=[card] + lands)

        card.on_attack(game)

        assert card.is_prepared is True
