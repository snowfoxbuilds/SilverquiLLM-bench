import pytest
from engine.card import Creature, Instant
from engine.decisions import Decision
from engine.game import exile
from engine.types import ManaCost, ManaType, Zone
from engine.zones import move_to_zone
from test_utils import (
    behavioral_game,
    cast_vanilla_spell,
    enter_permanent,
    prefer,
    put_on_battlefield,
    resolve_stack,
)


def bear(game, player, name="Bear", power=2):
    return put_on_battlefield(game, player, Creature(name=name, base_power=power, base_toughness=4))


def fund(player, **amounts):
    for name, amount in amounts.items():
        player.mana_pool.add(ManaType[name], amount)


from card_impl import GollumRiddleMaster


def arrange(parity="even"):
    game = behavioral_game()
    p = game.players[0]
    prefer(p, Decision.mode(parity))
    card = enter_permanent(game, p, GollumRiddleMaster())
    resolve_stack(game)
    return game, p, card


@pytest.mark.parametrize(
    "parity,value,expected",
    [("even", 0, True), ("even", 2, True), ("even", 3, False), ("odd", 0, False), ("odd", 3, True)],
)
def test_parity_filters_opponent_spells(parity, value, expected):
    game, p, _card = arrange(parity)
    prefer(p, Decision.mode("drain"))
    cast_vanilla_spell(game, 1, value)
    resolve_stack(game)
    assert game.players[1].life == (18 if expected else 20)
    assert p.life == (22 if expected else 20)


def test_own_spell_does_not_trigger():
    game, p, _card = arrange()
    prefer(p, Decision.mode("drain"))
    cast_vanilla_spell(game, 0, 2)
    resolve_stack(game)
    assert p.life == game.players[1].life == 20


def test_each_mode_is_available_once_per_permanent():
    game, p, card = arrange()
    for mode in ["counter", "drain", "draw", "drain"]:
        prefer(p, Decision.mode(mode))
        cast_vanilla_spell(game, 1, 2)
        resolve_stack(game)
    assert card.power == 4 and card.toughness == 2
    assert p.life == 22 and game.players[1].life == 18
    assert len(game.get_hand(p).get_all()) == 1


def test_pending_triggers_cannot_choose_same_mode():
    game, p, card = arrange()
    prefer(p, Decision.mode("counter"))
    cast_vanilla_spell(game, 1, 2)
    cast_vanilla_spell(game, 1, 2)
    resolve_stack(game)
    assert card.power == 4
    assert p.life == 22


def test_reentry_resets_parity_and_mode_choices():
    game, p, card = arrange()
    prefer(p, Decision.mode("drain"))
    cast_vanilla_spell(game, 1, 2)
    resolve_stack(game)
    exile(game, card)
    prefer(p, Decision.mode("odd"))
    move_to_zone(game, card, Zone.EXILE, Zone.BATTLEFIELD)
    prefer(p, Decision.mode("drain"))
    cast_vanilla_spell(game, 1, 3)
    resolve_stack(game)
    assert p.life == 24 and game.players[1].life == 16


def test_draw_trigger_survives_source_leaving():
    game, p, card = arrange()
    prefer(p, Decision.mode("draw"))
    cast_vanilla_spell(game, 1, 2)
    exile(game, card)
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 1


@pytest.mark.parametrize("value,life", [(0, 22), (1, 20), (2, 22), (3, 20)])
def test_x_in_a_spell_mana_value_uses_the_declared_value(value, life):
    from engine.casting import cast_spell as cast

    game, p, _card = arrange("even")
    opponent = game.players[1]
    prefer(p, Decision.mode("drain"))
    prefer(opponent, Decision.number(value))
    spell = Instant(name="X spell", mana_cost=ManaCost.parse("{X}"), owner=opponent)
    game.get_hand(opponent).add(spell)
    fund(opponent, COLORLESS=3)
    cast(game, opponent, spell)
    resolve_stack(game)
    assert p.life == life
    assert opponent.mana_pool.total() == 3 - value


def test_blink_does_not_keep_old_counters():
    game, p, card = arrange()
    prefer(p, Decision.mode("counter"))
    cast_vanilla_spell(game, 1, 2)
    resolve_stack(game)
    assert card.power == 4
    exile(game, card)
    prefer(p, Decision.mode("even"))
    move_to_zone(game, card, Zone.EXILE, Zone.BATTLEFIELD)
    prefer(p, Decision.mode("counter"))
    cast_vanilla_spell(game, 1, 2)
    resolve_stack(game)
    assert (card.power, card.toughness) == (4, 2)


class TurnIntoArtifact(Instant):
    def __init__(self, target, **kwargs):
        super().__init__(name="Turn into artifact", mana_cost=ManaCost(), **kwargs)
        self.target = target

    def on_resolve(self, game):
        from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer
        from engine.types import CardType

        def apply(state):
            self.target.card_types = {CardType.ARTIFACT}

        game.effect_manager.add(
            ContinuousEffect(self, Layer.TYPE, apply=apply, duration=DURATION_END_OF_TURN)
        )


def test_counter_mode_still_applies_while_gollum_is_not_a_creature():
    # Rule 608.2k still affects the named object after its characteristics change.
    from engine.types import Phase, Step
    from test_utils import advance_game_to_phase, cast_card

    game, p, card = arrange()
    prefer(p, Decision.mode("counter"))
    cast_vanilla_spell(game, 1, 2)
    cast_card(game, p, TurnIntoArtifact(card, owner=p))
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    resolve_stack(game)
    assert (card.power, card.toughness) == (4, 2)
