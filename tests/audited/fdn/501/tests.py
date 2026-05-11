"""Audited tests for Pacifism (FDN collector number 501)."""
from __future__ import annotations
import pytest
from card_impl import Pacifism
from engine.card import Aura, Creature
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestPacifismBasic:
    def test_is_aura(self) -> None:
        card = Pacifism(name="Pacifism", owner=None)
        assert isinstance(card, Aura)
        assert card.is_aura is True
    def test_is_enchantment(self) -> None:
        card = Pacifism(name="Pacifism", owner=None)
        assert CardType.ENCHANTMENT in card.card_types
    def test_mana_cost(self) -> None:
        card = Pacifism(name="Pacifism", owner=None)
        assert card.mana_cost is not None

@pytest.mark.ability
class TestPacifismAbility:
    def test_attach_sets_attached_to(self) -> None:
        game = create_game()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        set_board_state(game, 0, battlefield=[creature])
        pacifism = Pacifism(name="Pacifism", owner=game.players[0])
        pacifism.controller = game.players[0]
        pacifism.chosen_targets = [creature]
        pacifism.on_resolve(game)
        assert pacifism.attached_to is creature
    def test_cant_attack_flag_set(self) -> None:
        game = create_game()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        pacifism = Pacifism(name="Pacifism", owner=game.players[0])
        pacifism.controller = game.players[0]
        set_board_state(game, 0, battlefield=[creature, pacifism])
        pacifism.chosen_targets = [creature]
        pacifism.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert getattr(creature, "_cant_attack", False)
    def test_cant_block_flag_set(self) -> None:
        game = create_game()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        pacifism = Pacifism(name="Pacifism", owner=game.players[0])
        pacifism.controller = game.players[0]
        set_board_state(game, 0, battlefield=[creature, pacifism])
        pacifism.chosen_targets = [creature]
        pacifism.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert getattr(creature, "_cant_block", False)
    def test_get_targets_returns_creatures(self) -> None:
        game = create_game()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        set_board_state(game, 0, battlefield=[creature])
        pacifism = Pacifism(name="Pacifism", owner=game.players[0])
        targets = pacifism.get_targets(game)
        assert len(targets) > 0


@pytest.mark.rules
class TestPacifismSBADetach:
    def test_aura_goes_to_graveyard_when_creature_destroyed(self) -> None:
        """When the enchanted creature leaves the battlefield, the aura should
        be put into its owner's graveyard by state-based actions."""
        from engine.state_based_actions import check_state_based_actions
        from engine.game import destroy
        game = create_game()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        pacifism = Pacifism(name="Pacifism", owner=game.players[0])
        pacifism.controller = game.players[0]
        set_board_state(game, 0, battlefield=[creature, pacifism])
        pacifism.chosen_targets = [creature]
        pacifism.on_resolve(game)
        assert pacifism.attached_to is creature
        # Destroy the creature — aura becomes unattached
        destroy(game, creature)
        # After SBA pass, pacifism should be in graveyard
        check_state_based_actions(game)
        graveyard = game.get_graveyard(game.players[0])
        gy_cards = list(graveyard.get_all())
        aura_in_gy = any(obj is pacifism for obj in gy_cards)
        assert aura_in_gy, "Aura should be in graveyard after attached creature leaves battlefield"

    def test_aura_unattached_none_goes_to_graveyard(self) -> None:
        """An aura with attached_to=None on the battlefield is put into graveyard by SBA."""
        from engine.state_based_actions import check_state_based_actions
        game = create_game()
        pacifism = Pacifism(name="Pacifism", owner=game.players[0])
        pacifism.controller = game.players[0]
        pacifism.attached_to = None
        set_board_state(game, 0, battlefield=[pacifism])
        check_state_based_actions(game)
        graveyard = game.get_graveyard(game.players[0])
        gy_cards = list(graveyard.get_all())
        aura_in_gy = any(obj is pacifism for obj in gy_cards)
        assert aura_in_gy, "Unattached aura should be moved to graveyard by SBA"
