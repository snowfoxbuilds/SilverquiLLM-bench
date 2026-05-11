"""Audited tests for Embercleave (SPG collector number 77)."""
from __future__ import annotations
import pytest
from card_impl import Embercleave
from engine.card import Artifact, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestEmbercleaveBasic:
    def test_is_artifact(self) -> None:
        card = Embercleave()
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        card = Embercleave()
        assert card.name == "Embercleave"

    def test_mana_cost(self) -> None:
        card = Embercleave()
        assert card.mana_cost == ManaCost.parse("{4}{R}{R}")

    def test_is_legendary(self) -> None:
        card = Embercleave()
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_flash(self) -> None:
        card = Embercleave()
        assert Keyword.FLASH & card.keywords

    def test_is_equipment_subtype(self) -> None:
        card = Embercleave()
        assert "Equipment" in card.subtypes


@pytest.mark.ability
class TestEmbercleaveAbilities:
    def test_cost_reduction_with_attackers(self) -> None:
        """Each attacking creature reduces cost by 1."""
        game = create_game()
        p = game.players[0]
        card = Embercleave(owner=p)
        card.controller = p
        attacker = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        attacker.controller = p
        attacker.is_attacking = True
        set_board_state(game, 0, battlefield=[attacker])
        assert card.cost_reduction(game) == 1

    def test_cost_reduction_zero_without_attackers(self) -> None:
        game = create_game()
        p = game.players[0]
        card = Embercleave(owner=p)
        card.controller = p
        assert card.cost_reduction(game) == 0

    def test_on_resolve_attaches_to_creature(self) -> None:
        """Embercleave on_resolve() performs ETB attach (KEY_DECISIONS)."""
        game = create_game()
        p = game.players[0]
        creature = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        creature.controller = p
        card = Embercleave(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[creature, card])
        card.on_resolve(game)
        assert card.attached_to is creature

    def test_has_equip_activated_ability(self) -> None:
        card = Embercleave()
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1
        assert "Equip" in abilities[0].description


@pytest.mark.rules
class TestEmbercleaveEquipEffect:
    def test_equip_grants_double_strike_and_trample(self) -> None:
        """Equipped creature should get keywords in Layer 6."""
        game = create_game()
        p = game.players[0]
        creature = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        creature.controller = p
        card = Embercleave(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[creature, card])
        card.equip(creature, game)
        # Apply continuous effects
        game.effect_manager.apply_all(game)
        assert Keyword.DOUBLE_STRIKE & creature.keywords
        assert Keyword.TRAMPLE & creature.keywords

    def test_equip_grants_plus_one_plus_one(self) -> None:
        """Equipped creature gets +1/+1 via Layer 7c (KEY_DECISIONS)."""
        game = create_game()
        p = game.players[0]
        creature = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        creature.controller = p
        card = Embercleave(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[creature, card])
        card.equip(creature, game)
        game.effect_manager.apply_all(game)
        assert creature.base_power == 3
        assert creature.base_toughness == 3

    def test_cost_reduction_multiple_attackers(self) -> None:
        """Cost reduction scales with number of attacking creatures."""
        game = create_game()
        p = game.players[0]
        card = Embercleave(owner=p)
        card.controller = p
        attackers = []
        for i in range(3):
            a = Creature(name=f"Attacker{i}", owner=p, base_power=1, base_toughness=1)
            a.controller = p
            a.is_attacking = True
            attackers.append(a)
        set_board_state(game, 0, battlefield=attackers)
        assert card.cost_reduction(game) == 3
