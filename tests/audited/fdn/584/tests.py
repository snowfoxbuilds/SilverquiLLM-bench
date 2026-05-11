"""Audited tests for Zetalpa, Primal Dawn (FDN collector number 584) — flying + double strike + vigilance + trample + indestructible."""

from __future__ import annotations

import pytest

from card_impl import ZetalpaPrimalDawn

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestZetalpaPrimalDawnProperties:
    def test_is_creature(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        assert card.power == 4

    def test_toughness(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        assert card.toughness == 8

    def test_has_elder_subtype(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        assert "Elder" in card.subtypes

    def test_has_dinosaur_subtype(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        assert "Dinosaur" in card.subtypes


@pytest.mark.ability
class TestZetalpaPrimalDawnKeywords:
    def test_has_flying(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_double_strike(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        assert Keyword.DOUBLE_STRIKE in card.keywords

    def test_has_vigilance(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_has_trample(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_has_indestructible(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        assert Keyword.INDESTRUCTIBLE in card.keywords

    def test_exact_keywords(self) -> None:
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        expected = (Keyword.FLYING | Keyword.DOUBLE_STRIKE | Keyword.VIGILANCE
                    | Keyword.TRAMPLE | Keyword.INDESTRUCTIBLE)
        assert card.keywords == expected


@pytest.mark.behavior
class TestZetalpaPrimalDawnBehavior:
    """Flying + double strike + vigilance + trample + indestructible behavior tests."""

    def test_flying_cannot_be_blocked_by_ground(self) -> None:
        """Ground creature cannot block Zetalpa."""
        from engine.combat import _can_block
        from engine.card import Creature

        zetalpa = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=None)
        ground = Creature(name="Ground", owner=None)
        assert not _can_block(ground, zetalpa)

    def test_vigilance_does_not_tap_on_attack(self) -> None:
        """Zetalpa does not tap when declared as attacker."""
        from tests.test_utils import create_game, set_board_state, declare_attackers

        game = create_game()
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Zetalpa, Primal Dawn"])
        assert not card.is_tapped

    def test_double_strike_deals_damage_twice(self) -> None:
        """Zetalpa (4 power, double strike) deals 8 total damage unblocked."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Zetalpa, Primal Dawn"])
        combat_damage_step(game)
        assert game.players[1].life == 20 - 8

    def test_indestructible_survives_destroy(self) -> None:
        """Zetalpa with indestructible is not destroyed by destroy()."""
        from tests.test_utils import create_game, set_board_state
        from engine.game import destroy
        from engine.types import Zone

        game = create_game()
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=game.players[0])
        set_board_state(game, 0, battlefield=[card])

        destroy(game, card)

        bf = game.get_battlefield(game.players[0])
        assert bf.contains(card)

    def test_indestructible_survives_lethal_damage(self) -> None:
        """Zetalpa with indestructible survives lethal damage after SBAs."""
        from tests.test_utils import create_game, set_board_state
        from engine.game import deal_damage
        from engine.state_based_actions import resolve_state_based_actions
        from engine.types import Zone

        game = create_game()
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=game.players[0])
        set_board_state(game, 0, battlefield=[card])

        # Deal damage >= toughness (8)
        deal_damage(game, source=None, target=card, amount=10)
        resolve_state_based_actions(game)

        bf = game.get_battlefield(game.players[0])
        assert bf.contains(card)

    def test_trample_excess_damage_goes_to_defending_player(self) -> None:
        """Zetalpa (4/8, trample, double strike) blocked by 1/1 tramples excess to defending player."""
        from tests.test_utils import create_game, set_board_state, declare_attackers, declare_blockers
        from engine.card import Creature as BaseCreature
        from engine.combat import combat_damage_step
        from engine.types import Keyword as Kw

        game = create_game()
        card = ZetalpaPrimalDawn(name="Zetalpa, Primal Dawn", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])

        # Give the blocker flying so it can legally block Zetalpa
        blocker = BaseCreature(name="Flying Blocker", owner=game.players[1], base_power=1, base_toughness=1)
        blocker.keywords = Kw.FLYING
        set_board_state(game, 1, battlefield=[blocker])

        game.active_player_index = 0
        declare_attackers(game, ["Zetalpa, Primal Dawn"])
        declare_blockers(game, {"Zetalpa, Primal Dawn": ["Flying Blocker"]})
        combat_damage_step(game)

        # Double strike: first strike step assigns 1 lethal to blocker, 3 tramples through.
        # Normal step: blocker still in blocker list (dead), 1 assigned lethal, 3 tramples.
        # Total trample damage to player = 3 + 3 = 6
        assert game.players[1].life == 20 - 6
