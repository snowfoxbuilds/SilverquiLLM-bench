"""Tests for Great Hall of the Biblioplex (sos_257)."""

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


def _activate_mana(game, land, index):
    ability = land.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=land, controller=land.controller,
        cost=ability.cost, effect=ability.mana_produced, is_mana_ability=True,
    )
    activate_ability(game, land.controller, inst)


def _activate(game, land, index):
    ability = land.get_activated_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=land, controller=land.controller,
        cost=ability.cost, effect=ability.effect, is_mana_ability=False,
    )
    activate_ability(game, land.controller, inst)


class TestGreatHallOfTheBiblioplex:
    def test_tap_for_colorless(self):
        game = create_game()
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall])
        _activate_mana(game, hall, 0)
        p0 = game.players[0]
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped

    def test_restricted_mana_pays_for_instant_only(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        spell = Instant(name="Trick", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[hall], hand=[spell])
        p0._script.append(ManaType.BLUE)  # color choice
        _activate_mana(game, hall, 1)
        assert p0.life == 19  # paid 1 life
        assert p0.mana_pool.get_restricted(ManaType.BLUE) == 1
        cast_spell(game, 0, "Trick")  # restricted mana legally pays
        assert p0.mana_pool.total() == 0

    def test_restricted_mana_cannot_pay_creature(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[hall], hand=[bear])
        p0._script.append(ManaType.BLUE)
        _activate_mana(game, hall, 1)
        try:
            cast_spell(game, 0, "Bear")
            assert False, "restricted mana must not pay for a creature"
        except Exception:
            pass

    def test_animation_makes_2_4_wizard_still_land(self):
        game = create_game(scripts=(["pass"] * 6, ["pass"] * 6))
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 5})
        _activate(game, hall, 0)
        priority_loop(game)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2 and hall.toughness == 4
        assert game.players[0].mana_pool.total() == 0

    def test_animated_pump_on_instant_cast(self):
        game = create_game(scripts=(["pass"] * 6, ["pass"] * 6))
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        spell = Instant(name="Trick", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, battlefield=[hall], hand=[spell],
                        mana={ManaType.COLORLESS: 6})
        _activate(game, hall, 0)
        priority_loop(game)
        assert hall.power == 2
        cast_spell(game, 0, "Trick")
        # The pump trigger was pushed and resolved by cast_spell's loop.
        assert hall.power == 3
        # End-of-turn: the effect cycle resets it to base 2/4.
        game.effect_manager.apply_all(game)
        assert hall.power == 2

    def test_not_animated_if_already_creature(self):
        game = create_game(scripts=(["pass"] * 12, ["pass"] * 12))
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 10})
        _activate(game, hall, 0)
        priority_loop(game)
        hall.modified_power = 5  # marker to detect re-application
        _activate(game, hall, 0)
        priority_loop(game)
        assert hall.modified_power == 5  # unchanged — already a creature
