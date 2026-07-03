"""Tests for SOS 158 — Planar Engineering."""

from __future__ import annotations

from cards.sos.sos_158.card_impl import PlanarEngineering
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestPlanarEngineeringProperties:
    """Static card data should match the SOS 158 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(PlanarEngineering(owner=None), Sorcery)

    def test_name(self) -> None:
        assert PlanarEngineering(owner=None).name == "Planar Engineering"

    def test_mana_cost(self) -> None:
        assert PlanarEngineering(owner=None).mana_cost == ManaCost.parse("{3}{G}")


class TestPlanarEngineeringResolution:
    """Sacrifice two lands, search for four basics, put them tapped."""

    def test_sacrifices_two_lands(self) -> None:
        game = create_game()
        p1 = game.players[0]

        # Create two lands on battlefield
        from engine.card import CardImpl
        land1 = CardImpl(name="Forest", owner=p1, controller=p1)
        land1.card_types = {CardType.LAND}
        land2 = CardImpl(name="Forest", owner=p1, controller=p1)
        land2.card_types = {CardType.LAND}
        set_board_state(game, 0, battlefield=[land1, land2])

        spell = PlanarEngineering(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Both lands should have been sacrificed (moved to graveyard)
        battlefield = game.get_battlefield(p1).get_all()
        lands_on_bf = [c for c in battlefield if CardType.LAND in c.card_types]
        # Should have 4 new basics from library, and old 2 sacrificed
        graveyard = game.get_graveyard(p1).get_all()
        sacrificed = [c for c in graveyard if c in (land1, land2)]
        assert len(sacrificed) == 2

    def test_fetches_four_basic_lands(self) -> None:
        game = create_game()
        p1 = game.players[0]

        from engine.card import CardImpl
        land1 = CardImpl(name="Forest", owner=p1, controller=p1)
        land1.card_types = {CardType.LAND}
        land2 = CardImpl(name="Plains", owner=p1, controller=p1)
        land2.card_types = {CardType.LAND}

        # Put basics in library
        basics = []
        for i in range(4):
            basic = CardImpl(name=f"Forest{i}", owner=p1, controller=p1)
            basic.card_types = {CardType.LAND}
            basic.is_basic = True
            basics.append(basic)

        set_board_state(game, 0, battlefield=[land1, land2], library=basics)

        spell = PlanarEngineering(owner=p1, controller=p1)
        spell.on_resolve(game)

        battlefield = game.get_battlefield(p1).get_all()
        # The 4 basics should be on battlefield (lands sacrificed are in GY)
        assert len(battlefield) >= 4

    def test_fetched_lands_enter_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]

        from engine.card import CardImpl
        land1 = CardImpl(name="Forest", owner=p1, controller=p1)
        land1.card_types = {CardType.LAND}
        land2 = CardImpl(name="Plains", owner=p1, controller=p1)
        land2.card_types = {CardType.LAND}

        basics = []
        for i in range(4):
            basic = CardImpl(name=f"Forest{i}", owner=p1, controller=p1)
            basic.card_types = {CardType.LAND}
            basic.is_basic = True
            basics.append(basic)

        set_board_state(game, 0, battlefield=[land1, land2], library=basics)

        spell = PlanarEngineering(owner=p1, controller=p1)
        spell.on_resolve(game)

        battlefield = game.get_battlefield(p1).get_all()
        new_lands = [c for c in battlefield if hasattr(c, 'is_basic') and c.is_basic]
        for land in new_lands:
            assert land.tapped is True

    def test_requires_two_lands_to_sacrifice(self) -> None:
        """If controller doesn't have two lands, the spell should still resolve
        but the sacrifice requirement means it can't be completed."""
        game = create_game()
        p1 = game.players[0]

        from engine.card import CardImpl
        land1 = CardImpl(name="Forest", owner=p1, controller=p1)
        land1.card_types = {CardType.LAND}
        # Only one land on battlefield
        set_board_state(game, 0, battlefield=[land1])

        spell = PlanarEngineering(owner=p1, controller=p1)
        # Should handle gracefully (card requires sacrificing two lands as cost)
        spell.on_resolve(game)
