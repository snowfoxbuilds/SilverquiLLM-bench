"""Tests for Great Hall of the Biblioplex (sos_257)."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _activate_mana(game, player, land, index):
    ma = land.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=land, controller=player, cost=ma.cost,
        effect=ma.mana_produced, is_mana_ability=True,
    )
    activate_ability(game, player, inst)


def _activate_five(game, player, land):
    aa = land.get_activated_abilities()[0]
    inst = ActivatedAbilityInstance(
        source=land, controller=player, cost=aa.cost,
        effect=aa.effect, is_mana_ability=False,
    )
    activate_ability(game, player, inst)
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


class TestProperties:
    def test_is_land_not_creature_initially(self):
        c = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in c.card_types
        assert CardType.CREATURE not in c.card_types
        # Not seen as a creature with P/T before animation.
        assert not hasattr(c, "toughness")
        assert not hasattr(c, "base_power")


class TestManaAbilities:
    def test_tap_add_colorless(self):
        game = create_game()
        land = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[land])
        p0 = game.players[0]
        _activate_mana(game, p0, land, 0)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped is True

    def test_pay_life_add_any_restricted(self):
        game = create_game(scripts=([ManaType.BLUE], []))
        land = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[land], life=20)
        p0 = game.players[0]
        _activate_mana(game, p0, land, 1)
        assert p0.mana_pool.get(ManaType.BLUE) == 1
        assert p0.life == 19
        assert land.is_tapped is True

    def test_restricted_mana_casts_instant_not_creature(self):
        game = create_game(scripts=([ManaType.BLUE], []))
        land = GreatHallOfTheBiblioplex(owner=None)
        creature = Creature(name="Ogre", mana_cost=ManaCost.parse("{1}"),
                            base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[land],
                        hand=[creature])
        p0 = game.players[0]
        _activate_mana(game, p0, land, 1)  # 1 restricted blue
        # Creature cannot be cast with restricted mana.
        with pytest.raises(Exception):
            cast_spell(game, 0, "Ogre")
        # Instant can.
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[bolt])
        cast_spell(game, 0, "Bolt")
        assert game.get_graveyard(p0).contains(bolt)

    def test_only_one_mana_ability_per_tap(self):
        game = create_game()
        land = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[land])
        p0 = game.players[0]
        _activate_mana(game, p0, land, 0)
        # Second tap-based ability fails (already tapped).
        with pytest.raises(Exception):
            _activate_mana(game, p0, land, 1)


class TestAnimation:
    def test_five_animates_to_2_4_wizard_land(self):
        game = create_game()
        land = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})
        p0 = game.players[0]
        _activate_five(game, p0, land)
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types  # still a land
        assert "Wizard" in land.subtypes
        assert land.power == 2 and land.toughness == 4
        assert p0.mana_pool.total() == 0  # spent {5}

    def test_animation_only_if_not_already_creature(self):
        game = create_game()
        land = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 10})
        p0 = game.players[0]
        _activate_five(game, p0, land)
        # Manually pump, then re-animate: should not reset P/T to 2/4.
        land.modified_power += 1  # simulate prior pump
        _activate_five(game, p0, land)  # pays {5} again but no-ops
        assert land.power == 3  # unchanged by the second (no-op) animation

    def test_restricted_mana_cannot_pay_five_ability(self):
        game = create_game(scripts=([ManaType.RED, ManaType.RED, ManaType.RED,
                                     ManaType.RED, ManaType.RED], []))
        land = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[land], life=20)
        p0 = game.players[0]
        # produce 5 restricted red via 5 separate activations is impossible
        # (one tap). Instead set restricted mana directly to isolate the rule.
        for _ in range(5):
            p0.mana_pool.add(ManaType.RED, 1, instant_sorcery_only=True)
        with pytest.raises(Exception):
            _activate_five(game, p0, land)
        assert CardType.CREATURE not in land.card_types


class TestPump:
    def test_pump_on_cast_and_reset(self):
        game = create_game()
        land = GreatHallOfTheBiblioplex(owner=None)
        i1 = Instant(name="A", mana_cost=ManaCost.parse("{0}"))
        i2 = Instant(name="B", mana_cost=ManaCost.parse("{0}"))
        set_board_state(game, 0, battlefield=[land], hand=[i1, i2],
                        mana={ManaType.COLORLESS: 5})
        p0 = game.players[0]
        _activate_five(game, p0, land)
        assert land.power == 2
        cast_spell(game, 0, "A")
        assert land.power == 3
        cast_spell(game, 0, "B")
        assert land.power == 4
        # Until-end-of-turn reset via the engine's continuous-effect reset.
        game.effect_manager.apply_all(game)
        assert land.power == 2

    def test_no_pump_before_animation(self):
        game = create_game()
        land = GreatHallOfTheBiblioplex(owner=None)
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{0}"))
        set_board_state(game, 0, battlefield=[land], hand=[bolt])
        # No pump trigger registered yet; casting must not error.
        cast_spell(game, 0, "Bolt")
        assert not hasattr(land, "base_power")
