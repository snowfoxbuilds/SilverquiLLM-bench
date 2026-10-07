"""Known-Best control-changing effects (layer 2): a control effect applies
after one it depends on and otherwise in timestamp order (rule 613.8), and a
permanent that comes under a new controller — and only then — is summoning
sick for them (rule 302.6).

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``.
"""

from __future__ import annotations

from engine.card import Aura, Creature
from engine.continuous_effects import DURATION_PERMANENT, ContinuousEffect, Layer, set_controller
from engine.turn import untap_step
from test_utils import behavioral_game


def _game():
    game = behavioral_game()
    return game, *game.players


def _put(game, obj, player):
    obj.owner = obj.controller = player
    game.get_battlefield(player).add(obj)
    return obj


def _steal(game, obj, player):
    """A plain effect: ``player`` controls ``obj``."""
    effect = ContinuousEffect(
        source=None,
        layer=Layer.CONTROL,
        apply=lambda g: set_controller(obj, player),
        duration=DURATION_PERMANENT,
        controls=lambda: obj,
    )
    game.effect_manager.add(effect)
    return effect


def _aura_control(game, aura, enchanted):
    """An Aura's "you control enchanted permanent"."""
    aura.attached_to = enchanted

    def apply(g):
        set_controller(aura.attached_to, aura.controller)

    effect = ContinuousEffect(
        source=aura,
        layer=Layer.CONTROL,
        apply=apply,
        duration=DURATION_PERMANENT,
        controls=lambda: aura.attached_to,
        reads_controller_of=aura,
    )
    game.effect_manager.add(effect)
    return effect


def test_independent_control_effects_apply_in_timestamp_order():
    game, p0, p1 = _game()
    bear = _put(game, Creature(name="Bear"), p0)
    _steal(game, bear, p1)
    _steal(game, bear, p0)
    game.effect_manager.apply_all(game)
    assert bear.controller is p0


def test_an_aura_taken_over_takes_what_it_enchants_whatever_the_timestamps():
    game, p0, p1 = _game()
    bear = _put(game, Creature(name="Bear"), p1)
    first = _put(game, Aura(name="First"), p0)
    second = _put(game, Aura(name="Second"), p1)
    _aura_control(game, first, bear)
    _aura_control(game, second, first)
    game.effect_manager.apply_all(game)
    assert (first.controller, bear.controller) == (p1, p1)
    game.effect_manager.apply_all(game)
    assert (first.controller, bear.controller) == (p1, p1)


def test_auras_taking_each_other_over_apply_in_timestamp_order():
    game, p0, p1 = _game()
    first = _put(game, Aura(name="First"), p0)
    second = _put(game, Aura(name="Second"), p1)
    _aura_control(game, first, second)
    _aura_control(game, second, first)
    game.effect_manager.apply_all(game)
    # A dependency loop: the earlier effect first, so p0 takes the Second,
    # whose controller then takes the First (rule 613.8b).
    assert (second.controller, first.controller) == (p0, p0)


def test_a_dependency_loop_applies_before_a_later_effect_its_member_depends_on():
    game, p0, p1 = _game()
    first = _put(game, Aura(name="First"), p0)
    second = _put(game, Aura(name="Second"), p1)
    third = _put(game, Aura(name="Third"), p1)
    _aura_control(game, first, second)
    _aura_control(game, second, first)
    competing = _aura_control(game, third, second)
    # The First and Second form a loop; ignoring its inner dependencies leaves
    # the First ready at once, while the Second still waits for the Third,
    # which takes the Second for p1 before the Second takes the First (rule
    # 613.8b–c): First → Third → Second.
    game.effect_manager.apply_all(game)
    assert (first.controller, second.controller) == (p1, p1)
    game.effect_manager.apply_all(game)
    assert (first.controller, second.controller) == (p1, p1)
    game.effect_manager.remove(competing)
    game.effect_manager.apply_all(game)
    assert (first.controller, second.controller) == (p0, p0)


def test_a_control_change_makes_the_permanent_summoning_sick_once():
    game, p0, p1 = _game()
    bear = _put(game, Creature(name="Bear"), p1)
    bear.summoning_sick = False
    effect = _steal(game, bear, p0)
    game.effect_manager.apply_all(game)
    assert bear.controller is p0 and bear.summoning_sick
    bear.summoning_sick = False
    game.effect_manager.apply_all(game)
    assert not bear.summoning_sick
    game.effect_manager.remove(effect)
    game.effect_manager.apply_all(game)
    assert bear.controller is p1 and bear.summoning_sick


def test_the_untap_step_untaps_and_readies_what_the_active_player_controls():
    game, p0, p1 = _game()
    bear = _put(game, Creature(name="Bear"), p1)
    theirs = _put(game, Creature(name="Theirs"), p1)
    _steal(game, bear, p0)
    game.effect_manager.apply_all(game)
    for obj in (bear, theirs):
        obj.is_tapped = True
    game.active_player_index = 0
    untap_step(game)
    assert (bear.is_tapped, bear.summoning_sick) == (False, False)
    assert theirs.is_tapped
