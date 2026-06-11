"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _mana_instance(game, land, index):
    ability = land.get_mana_abilities()[index]
    return ActivatedAbilityInstance(
        source=land,
        controller=land.controller,
        cost=ability.cost,
        effect=ability.mana_produced,
        is_mana_ability=True,
        description=ability.description,
    )


def _animate_instance(land):
    ability = land.get_activated_abilities()[0]
    return ActivatedAbilityInstance(
        source=land,
        controller=land.controller,
        cost=ability.cost,
        effect=ability.effect,
        description=ability.description,
    )


def _animate(game, player_index, land):
    """Activate the {5} ability through the real ability pipeline."""
    player = game.players[player_index]
    activate_ability(game, player, _animate_instance(land))
    # Both players pass so the ability resolves off the stack.
    game.players[0]._script.appendleft("pass")
    game.players[1]._script.appendleft("pass")
    priority_loop(game)


class TestProperties:
    def test_static_data(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types
        assert CardType.CREATURE not in card.card_types
        assert len(card.get_mana_abilities()) == 2


class TestManaAbilities:
    def test_tap_for_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])

        activate_ability(game, p1, _mana_instance(game, land, 0))
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped

    def test_restricted_mana_casts_instant_only(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        trick = Instant(name="Trick", mana_cost=ManaCost.parse("{U}"))
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{U}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[land], hand=[trick, bear], life=20)

        activate_ability(game, p1, _mana_instance(game, land, 1))
        assert p1.life == 19                              # paid 1 life
        assert land.is_tapped
        assert p1.mana_pool.get_restricted(ManaType.BLUE) == 1
        assert p1.mana_pool.get(ManaType.BLUE) == 0       # not normal mana

        # The restricted mana cannot pay for a creature spell...
        try:
            cast_spell(game, 0, "Bear")
            raise AssertionError("restricted mana paid for a creature")
        except Exception as exc:
            assert "insufficient mana" in str(exc)

        # ...but it can pay for an instant.
        cast_spell(game, 0, "Trick")
        assert game.get_graveyard(p1).contains(trick)
        assert p1.mana_pool.total() == 0

    def test_cannot_pay_life_at_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land], life=0)
        ability = land.get_mana_abilities()[1]
        assert ability.cost(game, land) is False
        assert not land.is_tapped


class TestAnimation:
    def test_becomes_2_4_wizard_still_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})

        _animate(game, 0, land)

        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types          # still a land
        assert "Wizard" in land.subtypes
        assert land.power == 2 and land.toughness == 4
        assert p1.mana_pool.total() == 0                 # paid {5}

    def test_pump_on_instant_and_reset_at_cleanup(self) -> None:
        game = create_game(scripts=([[]], []))
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        tricks = [Instant(name=f"T{i}", mana_cost=ManaCost.parse("{U}"))
                  for i in range(2)]
        set_board_state(game, 0, battlefield=[land], hand=list(tricks),
                        mana={ManaType.COLORLESS: 5, ManaType.BLUE: 2})
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        filler.owner = filler.controller = p1
        p1.zones[Zone.LIBRARY].add(filler)

        _animate(game, 0, land)
        cast_spell(game, 0, "T0")
        assert land.power == 3                            # +1/+0
        cast_spell(game, 0, "T1")
        assert land.power == 4                            # stacks per spell

        # Run out the rest of the turn — cleanup clears the pump.
        from engine.turn import run_turn
        run_turn(game)
        assert land.power == 2
        assert land.toughness == 4

    def test_already_creature_no_double_animation(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 10})

        _animate(game, 0, land)
        land.modified_power = 5                           # marker
        _animate(game, 0, land)                           # gated: no reset
        assert land.modified_power == 5

    def test_opponent_spell_does_not_pump(self) -> None:
        game = create_game()
        p1, p2 = game.players
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})
        _animate(game, 0, land)

        opp_trick = Instant(name="Opp Trick", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 1, hand=[opp_trick], mana={ManaType.BLUE: 1})
        cast_spell(game, 1, "Opp Trick")
        assert land.power == 2
