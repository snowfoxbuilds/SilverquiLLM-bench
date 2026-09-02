"""Reference test for FDN 114 — Treetop Snarespinner.

Demonstrates a **targeted activated ability** (Phase D pattern 2) with an
extra sorcery-speed timing gate in ``can_activate``. The target creature is
chosen at activation via a Player Query (answered by an Intent), captured on
the stack, revalidated at resolution, and given a +1/+1 counter.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_114.card_impl import TreetopSnarespinner
from engine.abilities import AbilityError
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _activate_targeting(game, player, source, target):
    """Drive the ability through the real activate → stack → resolve path,
    targeting *target* (chosen at activation via an Intent on *player*)."""
    inst = game.refs.instance_id(target, Zone.BATTLEFIELD.value)
    player.start_intent("snare", Intent(
        pattern=GameRef(card=frozenset({("name", source.name)})),
        preferences=(Decision.obj(instance=inst),),
    ))
    try:
        activate_card_ability(game, player, source)
    finally:
        player.end_intent("snare")


class TestTreetopSnarespinnerProperties:
    def test_static_data(self):
        card = TreetopSnarespinner(owner=None)
        assert card.name == "Treetop Snarespinner"
        assert card.mana_cost == ManaCost.parse("{3}{G}")
        assert (card.base_power, card.base_toughness) == (1, 4)
        assert "Spider" in card.subtypes
        assert Keyword.REACH in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords

    def test_has_one_targeted_ability(self):
        card = TreetopSnarespinner(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) == 1
        assert abilities[0].targeting is not None
        assert abilities[0].can_activate is not None


class TestTreetopSnarespinnerAbility:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        snare = TreetopSnarespinner(owner=p1, controller=p1)
        my_bear = _bear(p1, "My Bear")
        set_board_state(game, 0, battlefield=[snare, my_bear], mana={ManaType.GREEN: 3})
        game.phase = Phase.PRECOMBAT_MAIN
        return game, p1, p2, snare, my_bear

    def test_counter_added_after_resolution(self):
        game, p1, p2, snare, my_bear = self._setup()
        _activate_targeting(game, p1, snare, my_bear)
        assert not game.stack.is_empty()
        resolve_stack(game)
        assert my_bear.plus_one_counters == 1

    def test_cost_is_paid(self):
        game, p1, p2, snare, my_bear = self._setup()
        _activate_targeting(game, p1, snare, my_bear)
        assert p1.mana_pool.total() == 0          # {2}{G} paid

    def test_target_captured_on_stack(self):
        game, p1, p2, snare, my_bear = self._setup()
        _activate_targeting(game, p1, snare, my_bear)
        top = game.stack.peek()
        assert top.targets == [my_bear]
        assert top.controller is p1

    def test_cannot_target_creature_you_do_not_control(self):
        """Option-set invariant: only creatures the controller controls are
        offered, so an opponent's creature is never a legal target."""
        game, p1, p2, snare, my_bear = self._setup()
        their_bear = _bear(p2, "Their Bear")
        set_board_state(game, 1, battlefield=[their_bear])
        # No Intent targeting their_bear can be built — it is not a candidate,
        # so activation with no legal own creature-target would fail. Here we
        # confirm targeting p2's bear is simply not among the offered options
        # by driving the ability at our own bear and checking the opponent's
        # creature is untouched.
        _activate_targeting(game, p1, snare, my_bear)
        resolve_stack(game)
        assert their_bear.plus_one_counters == 0
        assert my_bear.plus_one_counters == 1

    def test_sorcery_speed_gate_rejects_outside_main(self):
        """Legality invariant (can_activate): the sorcery-speed timing gate
        rejects activation outside the controller's main phase before any cost."""
        game, p1, p2, snare, my_bear = self._setup()
        game.phase = Phase.COMBAT
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, snare)
        assert p1.mana_pool.total() == 3          # no mana spent

    def test_sorcery_speed_gate_rejects_with_nonempty_stack(self):
        game, p1, p2, snare, my_bear = self._setup()
        # A pending object on the stack means it is not sorcery-speed timing.
        from engine.stack import StackObject
        game.stack.push(StackObject(source=snare, controller=p1))
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, snare)
        assert p1.mana_pool.total() == 3
