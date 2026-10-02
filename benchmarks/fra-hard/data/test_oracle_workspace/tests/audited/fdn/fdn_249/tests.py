"""Reference test for FDN 249 — Adventuring Gear.

No static buff; a landfall trigger gives the equipped creature +2/+2 until end
of turn. See fdn_129/tests.py for the canonical Equipment test shape.
"""

from __future__ import annotations

from cards.fdn.fdn_249.card_impl import AdventuringGear
from engine.card import Creature, Equipment, Land
from engine.types import ManaCost
from test_utils import scenario_game as create_game
from test_utils import set_board_state


def _bear(p):
    return Creature(name="Bear", base_power=2, base_toughness=2, owner=p, controller=p)


class TestAdventuringGearProperties:
    def test_static_data(self):
        gear = AdventuringGear(owner=None)
        assert gear.name == "Adventuring Gear"
        assert gear.mana_cost == ManaCost.parse("{1}")
        assert gear.equip_cost == ManaCost.parse("{1}")
        assert isinstance(gear, Equipment) and gear.is_equipment is True


class TestAdventuringGearBehaviour:
    def test_no_static_buff(self):
        from engine.types import ManaType, Phase
        from test_utils import (
            activate_card_ability,
            enter_permanent,
            object_preference,
            prefer,
            resolve_stack,
        )

        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        set_board_state(game, 0, battlefield=[bear], mana={ManaType.COLORLESS: 1})
        gear = enter_permanent(game, p1, AdventuringGear())
        game.phase, game.step = Phase.PRECOMBAT_MAIN, None
        prefer(p1, object_preference(game, bear))
        activate_card_ability(game, p1, gear)
        resolve_stack(game)
        assert (bear.power, bear.toughness) == (2, 2)

    def test_landfall_pumps_until_end_of_turn(self):
        from engine.casting import play_land
        from engine.types import ManaType, Phase, Step
        from test_utils import (
            activate_card_ability,
            advance_game_to_phase,
            enter_permanent,
            object_preference,
            prefer,
            resolve_stack,
        )

        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        set_board_state(game, 0, battlefield=[bear], mana={ManaType.COLORLESS: 1})
        gear = enter_permanent(game, p1, AdventuringGear())
        game.phase, game.step = Phase.PRECOMBAT_MAIN, None
        prefer(p1, object_preference(game, bear))
        activate_card_ability(game, p1, gear)
        resolve_stack(game)
        assert (bear.power, bear.toughness) == (2, 2)

        land = Land(name="Forest", owner=p1)
        game.get_hand(p1).add(land)
        play_land(game, p1, land)
        resolve_stack(game)
        assert (bear.power, bear.toughness) == (4, 4)
        advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
        assert (bear.power, bear.toughness) == (2, 2)
