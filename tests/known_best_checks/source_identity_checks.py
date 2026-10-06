"""A triggered ability's "other" and "another" exclude its source as it was
when the ability triggered: the same card in the same battlefield stint. A
source that has left the battlefield and returned since is a new object
(rule 400.7), so it counts as another object to an occurrence from before,
while an occurrence of the returned card still excludes it. And a chosen mode
whose target cannot be chosen is rejected rather than replaced by another
mode (rule 700.2a, ADR-017).

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_12.card_impl import FelidarSavior
from cards.fdn.fdn_15.card_impl import HareApparent
from cards.fdn.fdn_122.card_impl import (
    KykarZephyrAwakener,
    KykarZephyrAwakenerAbility2,
    KykarZephyrAwakenerAbility3,
    KykarZephyrAwakenerAbility4,
)
from cards.fdn.fdn_218.card_impl import DwynensElite
from engine.card import Creature, Instant
from engine.decisions import Decision, GameRef, InvalidPlayerChoiceError, PostconditionError
from engine.events import SpellCastTriggeredEvent
from engine.protection import ProtectionAbility
from engine.stack import resolve_top_of_stack
from engine.types import Color, Zone
from engine.zones import move_to_zone
from test_utils import Intent, branch, create_game, set_board_state


def _table(**zones):
    game = create_game()
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    set_board_state(game, 0, **zones)
    return game


def _enter(game, card, from_zone=Zone.HAND):
    move_to_zone(game, card, from_zone, Zone.BATTLEFIELD)


def _leave_and_return(game, card):
    move_to_zone(game, card, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, card, Zone.EXILE, Zone.BATTLEFIELD)


def _settle(game):
    game.trigger_manager.put_pending_on_stack(game)


def _resolve_all(game):
    while not game.stack.is_empty():
        resolve_top_of_stack(game)


def _tokens(game, subtype):
    return [
        o for o in game.get_battlefield(game.players[0]).get_all()
        if o.is_token and subtype in getattr(o, "subtypes", set())
    ]


# ---- Hare Apparent: "other creatures you control named Hare Apparent" --------


def test_a_lone_hare_makes_no_rabbit():
    hare = HareApparent()
    game = _table(hand=[hare])
    _enter(game, hare)
    _settle(game)
    _resolve_all(game)
    assert _tokens(game, "Rabbit") == []


def test_a_hare_entering_beside_another_makes_one_rabbit():
    hare, other = HareApparent(), HareApparent()
    game = _table(hand=[hare], battlefield=[other])
    _enter(game, hare)
    _settle(game)
    _resolve_all(game)
    assert len(_tokens(game, "Rabbit")) == 1


def test_a_hare_that_returned_before_its_first_trigger_was_placed_counts_for_it():
    hare = HareApparent()
    game = _table(hand=[hare])
    _enter(game, hare)
    _leave_and_return(game, hare)
    _settle(game)
    assert len(game.stack.objects()) == 2
    _resolve_all(game)
    # The first occurrence counts the returned Hare; the second excludes it.
    assert len(_tokens(game, "Rabbit")) == 1


def test_a_hare_that_returned_after_its_first_trigger_was_placed_counts_for_it():
    hare = HareApparent()
    game = _table(hand=[hare])
    _enter(game, hare)
    _settle(game)
    _leave_and_return(game, hare)
    _settle(game)
    resolve_top_of_stack(game)  # the returned Hare's own occurrence
    assert _tokens(game, "Rabbit") == []
    resolve_top_of_stack(game)  # the first occurrence
    assert len(_tokens(game, "Rabbit")) == 1


# ---- Dwynen's Elite: "if you control another Elf" ----------------------------


def _elf():
    return Creature(name="Elf", subtypes={"Elf"}, base_power=1, base_toughness=1)


def test_the_elite_with_another_elf_makes_a_warrior():
    elite, elf = DwynensElite(), _elf()
    game = _table(hand=[elite], battlefield=[elf])
    _enter(game, elite)
    _settle(game)
    _resolve_all(game)
    assert len(_tokens(game, "Warrior")) == 1


def test_the_elite_makes_nothing_when_its_last_other_elf_has_left():
    elite, elf = DwynensElite(), _elf()
    game = _table(hand=[elite], battlefield=[elf])
    _enter(game, elite)
    _settle(game)
    move_to_zone(game, elf, Zone.BATTLEFIELD, Zone.GRAVEYARD)
    _resolve_all(game)
    assert _tokens(game, "Warrior") == []


@pytest.mark.parametrize("placed_first", [False, True], ids=["before placement", "after placement"])
def test_an_elite_that_returned_alone_is_another_elf_to_its_first_trigger(placed_first):
    elite, elf = DwynensElite(), _elf()
    game = _table(hand=[elite], battlefield=[elf])
    _enter(game, elite)
    if placed_first:
        _settle(game)
    move_to_zone(game, elite, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, elf, Zone.BATTLEFIELD, Zone.GRAVEYARD)
    _enter(game, elite, Zone.EXILE)  # alone: its own entry does not trigger
    _settle(game)
    assert len(game.stack.objects()) == 1
    _resolve_all(game)
    assert len(_tokens(game, "Warrior")) == 1


# ---- Felidar Savior: "up to two other target creatures you control" ----------


def _savior_ref(game, savior):
    return Decision.obj(instance=game.refs.instance_id(savior, Zone.BATTLEFIELD.value))


def test_a_lone_savior_cannot_target_itself():
    savior = FelidarSavior()
    game = _table(hand=[savior])
    _enter(game, savior)
    game.players[0].set_baseline(Intent(pattern=GameRef(), preferences=(_savior_ref(game, savior),)))
    _settle(game)
    _resolve_all(game)
    assert savior.counters.get("+1/+1", 0) == 0


def test_a_savior_that_returned_before_placement_is_another_creature_to_its_first_trigger():
    savior = FelidarSavior()
    game = _table(hand=[savior])
    _enter(game, savior)
    _leave_and_return(game, savior)
    game.players[0].set_baseline(Intent(pattern=GameRef(), preferences=(_savior_ref(game, savior),)))
    _settle(game)
    targeted = [o.targets for o in game.stack.objects()]
    # Only the first occurrence may target the returned Savior.
    assert sorted(targeted, key=len) == [[], [savior]]
    _resolve_all(game)
    assert savior.counters.get("+1/+1", 0) == 1


# ---- Kykar: a chosen flicker mode with no legal target is rejected -----------

FLICKER = Decision.mode(printed=KykarZephyrAwakenerAbility3)
TOKEN = Decision.mode(printed=KykarZephyrAwakenerAbility4)


def _kykar(*, protected: bool):
    """Player 0's Kykar and one other creature it controls; the other has
    protection from white when *protected*, so Kykar cannot target it."""
    kykar = KykarZephyrAwakener()
    other = Creature(name="Bear", base_power=2, base_toughness=2)
    if protected:
        other.protections = [ProtectionAbility(quality=Color.WHITE)]
    game = _table(battlefield=[kykar, other])
    kykar.register_triggers(game)
    return game, kykar, other


def _cast_noncreature_spell(game, *branches):
    p0 = game.players[0]
    p0.set_baseline(Intent(pattern=GameRef(), branches=tuple(branches)))
    game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(spell=Instant(name="Spell"), player=p0))
    _settle(game)


def _other_ref(game, other):
    return Decision.obj(instance=game.refs.instance_id(other, Zone.BATTLEFIELD.value))


def test_a_flicker_mode_with_no_legal_target_is_rejected():
    game, _, other = _kykar(protected=True)
    # Its only branch is rejected, so the script runs out.
    with pytest.raises(PostconditionError) as failed:
        _cast_noncreature_spell(game, branch(FLICKER))
    assert isinstance(failed.value.__cause__, InvalidPlayerChoiceError)
    assert _tokens(game, "Spirit") == []
    assert game.get_battlefield(game.players[0]).contains(other)


def test_a_rejected_flicker_mode_is_asked_again_and_token_chosen():
    game, _, other = _kykar(protected=True)
    _cast_noncreature_spell(game, branch(FLICKER), branch(TOKEN))
    (obj,) = game.stack.objects()
    assert obj.printed is KykarZephyrAwakenerAbility2
    assert not game.trigger_manager.has_pending()
    _resolve_all(game)
    assert len(_tokens(game, "Spirit")) == 1 and len(game.created_tokens) == 1
    assert game.get_battlefield(game.players[0]).contains(other)


def test_a_legal_flicker_exiles_its_target_and_makes_no_token():
    game, _, other = _kykar(protected=False)
    _cast_noncreature_spell(game, branch(FLICKER, _other_ref(game, other)))
    _resolve_all(game)
    assert game.players[0].zones[Zone.EXILE].contains(other)
    assert _tokens(game, "Spirit") == []


def test_a_chosen_token_mode_makes_a_token_with_a_legal_flicker_target_present():
    game, _, other = _kykar(protected=False)
    _cast_noncreature_spell(game, branch(TOKEN))
    _resolve_all(game)
    assert len(_tokens(game, "Spirit")) == 1
    assert game.get_battlefield(game.players[0]).contains(other)


def test_a_flicker_whose_target_became_illegal_does_nothing():
    game, _, other = _kykar(protected=False)
    _cast_noncreature_spell(game, branch(FLICKER, _other_ref(game, other)))
    other.protections = [ProtectionAbility(quality=Color.WHITE)]
    _resolve_all(game)
    assert game.get_battlefield(game.players[0]).contains(other)
    assert _tokens(game, "Spirit") == []
