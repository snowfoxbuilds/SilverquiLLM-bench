"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _resolve_all(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _activate_mana(game, player, card, index):
    ma = card.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=card, controller=player, cost=ma.cost,
        effect=ma.mana_produced, is_mana_ability=True,
    )
    activate_ability(game, player, inst)


def _activate_five(game, player, card):
    ab = card.get_activated_abilities()[0]
    inst = ActivatedAbilityInstance(
        source=card, controller=player, cost=ab.cost,
        effect=ab.effect, is_mana_ability=False,
    )
    activate_ability(game, player, inst)
    _resolve_all(game)


class TestProperties:
    def test_is_land_no_cost(self):
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types
        assert CardType.CREATURE not in card.card_types
        assert card.can_cast(create_game()) is False

    def test_not_a_creature_before_animation(self):
        card = GreatHallOfTheBiblioplex(owner=None)
        # power/toughness must be absent (raise) so combat/SBAs skip it.
        assert not hasattr(card, "power")
        assert not hasattr(card, "toughness")
        assert not hasattr(card, "base_power")

    def test_two_mana_abilities(self):
        card = GreatHallOfTheBiblioplex(owner=None)
        assert len(card.get_mana_abilities()) == 2


class TestManaAbilities:
    def test_tap_for_colorless(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])
        _activate_mana(game, p1, hall, 0)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped is True

    def test_pay_life_for_restricted_any_color(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], life=20)
        p1._script.append(ManaType.RED)  # choose red
        _activate_mana(game, p1, hall, 1)
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.RED) == 1
        assert p1.mana_pool._restricted[ManaType.RED] == 1
        assert hall.is_tapped is True

    def test_cannot_pay_life_at_zero(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], life=0)
        from engine.abilities import AbilityError

        with pytest.raises(AbilityError):
            p1._script.append(ManaType.RED)
            _activate_mana(game, p1, hall, 1)


class TestRestrictedManaUsage:
    def test_restricted_mana_blocks_creature_allows_instant(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], life=20)
        p1._script.append(ManaType.RED)
        _activate_mana(game, p1, hall, 1)  # 1 restricted red

        # A creature costing {R} cannot be cast with restricted mana.
        creature = Creature(name="RedBear", mana_cost=ManaCost.parse("{R}"),
                            base_power=2, base_toughness=2)
        creature.owner = p1
        creature.controller = p1
        p1.zones[Zone.HAND].add(creature)
        with pytest.raises(Exception):
            cast_spell(game, 0, "RedBear")
        assert p1.mana_pool.get(ManaType.RED) == 1  # still there

        # An instant costing {R} can be cast with the restricted mana.
        inst = Instant(name="RedZap", mana_cost=ManaCost.parse("{R}"))
        inst.owner = p1
        inst.controller = p1
        p1.zones[Zone.HAND].add(inst)
        cast_spell(game, 0, "RedZap")
        assert game.get_graveyard(p1).contains(inst)
        assert p1.mana_pool.get(ManaType.RED) == 0


class TestAnimation:
    def _animated(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        _activate_five(game, p1, hall)
        return game, p1, hall

    def test_becomes_2_4_wizard_still_land(self):
        game, p1, hall = self._animated()
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types  # still a land
        assert "Wizard" in hall.subtypes
        assert hall.power == 2 and hall.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_restricted_mana_cannot_pay_five(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], life=20)
        # 5 restricted mana from another instance-style add
        for _ in range(5):
            p1.mana_pool.add(ManaType.WHITE, 1, restricted=True)
        ab = hall.get_activated_abilities()[0]
        inst = ActivatedAbilityInstance(source=hall, controller=p1, cost=ab.cost,
                                        effect=ab.effect, is_mana_ability=False)
        from engine.abilities import AbilityError

        with pytest.raises(AbilityError):
            activate_ability(game, p1, inst)
        assert CardType.CREATURE not in hall.card_types

    def test_cannot_animate_twice(self):
        game, p1, hall = self._animated()
        # Already a creature; activating again (with mana) must not re-run.
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        _activate_five(game, p1, hall)
        # Mana paid but no change (effect gated on not-already-creature).
        assert hall.base_power == 2 and hall.base_toughness == 4


class TestAnimatedPump:
    def _animated(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        # use a private direct activation path through the engine ability system
        ab = hall.get_activated_abilities()[0]
        inst = ActivatedAbilityInstance(source=hall, controller=p1, cost=ab.cost,
                                        effect=ab.effect, is_mana_ability=False)
        activate_ability(game, p1, inst)
        _resolve_all(game)
        return game, p1, hall

    def test_pump_on_instant_cast_stacks(self):
        game, p1, hall = self._animated()
        assert hall.power == 2
        ping1 = Instant(name="Ping1", mana_cost=ManaCost.parse("{R}"))
        ping2 = Instant(name="Ping2", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, hand=[ping1, ping2], mana={ManaType.RED: 2})
        cast_spell(game, 0, "Ping1")
        assert hall.power == 3  # +1/+0
        cast_spell(game, 0, "Ping2")
        assert hall.power == 4  # stacks

    def test_pump_resets_at_end_of_turn(self):
        game, p1, hall = self._animated()
        ping = Instant(name="Ping", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, hand=[ping], mana={ManaType.RED: 1})
        cast_spell(game, 0, "Ping")
        assert hall.power == 3
        # Cleanup re-applies continuous effects via apply_all → resets P/T.
        game.effect_manager.apply_all(game)
        assert hall.power == 2  # until-end-of-turn pump cleared
        assert CardType.CREATURE in hall.card_types  # still a creature/land

    def test_creature_cast_does_not_pump(self):
        game, p1, hall = self._animated()
        ogre = Creature(name="Ogre", mana_cost=ManaCost.parse("{2}"),
                        base_power=3, base_toughness=3)
        set_board_state(game, 0, hand=[ogre], mana={ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Ogre")
        assert hall.power == 2  # creature spell doesn't pump
