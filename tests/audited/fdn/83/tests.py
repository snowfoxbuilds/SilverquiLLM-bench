"""Audited tests for Fiend Artisan (SPG collector number 83)."""
from __future__ import annotations
import pytest
from card_impl import FiendArtisan
from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestFiendArtisanBasic:
    def test_is_creature(self) -> None:
        card = FiendArtisan()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = FiendArtisan()
        assert card.name == "Fiend Artisan"

    def test_mana_cost_hybrid(self) -> None:
        """Fiend Artisan costs {B/G}{B/G} — hybrid mana."""
        card = FiendArtisan()
        assert card.mana_cost is not None
        assert len(card.mana_cost.hybrid) == 2

    def test_hybrid_symbols_are_bg(self) -> None:
        """Each hybrid symbol should allow B or G payment (KEY_DECISIONS: hybrid mana ordering)."""
        from engine.types import HybridManaSymbol, ManaType
        card = FiendArtisan()
        for h in card.mana_cost.hybrid:
            assert {h.option_a, h.option_b} == {ManaType.BLACK, ManaType.GREEN}

    def test_base_power_toughness_zero(self) -> None:
        card = FiendArtisan()
        assert card.base_power == 0
        assert card.base_toughness == 0

    def test_subtypes(self) -> None:
        card = FiendArtisan()
        assert "Nightmare" in card.subtypes


@pytest.mark.ability
class TestFiendArtisanCDA:
    def test_power_equals_graveyard_creatures(self) -> None:
        """P/T = number of creature cards in graveyard (CDA)."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        p = game.players[0]
        card = FiendArtisan(owner=p)
        card.controller = p
        # Put two creatures in graveyard
        c1 = Creature(name="Dead1", owner=p, base_power=1, base_toughness=1)
        c2 = Creature(name="Dead2", owner=p, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card], graveyard=[c1, c2])
        assert card.power == 2
        assert card.toughness == 2

    def test_power_zero_with_empty_graveyard(self) -> None:
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        p = game.players[0]
        card = FiendArtisan(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[card])
        assert card.power == 0
        assert card.toughness == 0


@pytest.mark.ability
class TestFiendArtisanActivated:
    def test_has_activated_ability(self) -> None:
        card = FiendArtisan()
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_ability_description(self) -> None:
        card = FiendArtisan()
        abilities = card.get_activated_abilities()
        assert "Sacrifice" in abilities[0].description

    def test_activated_ability_puts_creature_on_battlefield(self) -> None:
        """Full activation: pay hybrid, tap, sacrifice creature, tutor creature onto bf."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import ManaType, Zone, Phase
        game = create_game()
        p = game.players[0]
        # Set up sorcery speed conditions
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN

        card = FiendArtisan(owner=p)
        card.controller = p
        sac_target = Creature(name="Fodder", owner=p, base_power=1, base_toughness=1)
        sac_target.controller = p
        # Library creature to find (MV=1)
        from engine.card import CardImpl
        lib_creature = Creature(name="Found", owner=p, base_power=3, base_toughness=3)
        lib_creature.mana_cost = ManaCost.parse("{G}")  # MV=1
        lib_creature.controller = p

        set_board_state(game, 0, battlefield=[card, sac_target],
                        mana={ManaType.BLACK: 2, ManaType.GREEN: 2})
        p.zones[Zone.LIBRARY].add(lib_creature)

        card._x_value = 1
        card._sacrifice_target = sac_target
        abilities = card.get_activated_abilities()
        cost_ok = abilities[0].cost(game, card)
        assert cost_ok is True
        assert card.is_tapped is True
        abilities[0].effect(game)
        bf_names = [c.name for c in game.get_battlefield(p).get_all()]
        assert "Found" in bf_names

    def test_activated_ability_fails_without_sacrifice_target(self) -> None:
        """Cannot activate when no other creature is on the battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import ManaType, Phase
        game = create_game()
        p = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN

        card = FiendArtisan(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.BLACK: 5, ManaType.GREEN: 5})
        card._x_value = 0
        abilities = card.get_activated_abilities()
        cost_ok = abilities[0].cost(game, card)
        assert cost_ok is False
