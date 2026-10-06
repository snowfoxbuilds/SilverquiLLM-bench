"""Reference test for FDN 31 — Bigfin Bouncer.

Its enters ability is a triggered ability (rule 603.3d): the creature spell
has no targets; once it resolves and the Bouncer enters, the trigger goes on
the stack choosing its target — a creature an opponent controls — and checks
it again as it resolves (rule 608.2b). Targeting is driven the intent-style
way through ``cast_spell(targets=...)`` — never a test-only resolve backdoor.
"""

from __future__ import annotations

from cards.fdn.fdn_31.card_impl import BigfinBouncer
from engine.card import Creature, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from test_utils import Intent
from engine.stack import resolve_top_of_stack
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _cast_and_place_trigger(game, player_index, card, targets):
    """Cast *card* and resolve the creature spell, so its enters trigger goes
    on the stack choosing *targets* via an Intent — and stop there, so a test
    can change the board before the trigger resolves."""
    from engine.state_based_actions import resolve_state_based_actions

    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    prefs = tuple(
        Decision.obj(instance=game.refs.instance_id(t, Zone.BATTLEFIELD.value))
        for t in targets
    )
    player.start_intent("cast", Intent(pattern=GameRef(), preferences=prefs))
    try:
        engine_cast_spell(game, player, card)
        resolve_top_of_stack(game)
        resolve_state_based_actions(game)
    finally:
        player.end_intent("cast")


class TestBigfinBouncerProperties:
    def test_static_data(self):
        c = BigfinBouncer(owner=None)
        assert printed_class(c) is BigfinBouncer
        assert c.mana_cost == ManaCost.parse("{3}{U}")
        assert (c.base_power, c.base_toughness) == (3, 2)
        assert {"Shark", "Pirate"} <= c.subtypes

    def test_the_spell_has_no_targets_its_enters_trigger_has_one(self):
        game = create_game()
        c = BigfinBouncer(owner=game.players[0], controller=game.players[0])
        assert c.get_targets(game) == []
        specs = c._enters_targets(game, game.players[0])
        assert len(specs) == 1
        assert isinstance(specs[0], TargetRequirement)
        assert specs[0].zone == Zone.BATTLEFIELD
        assert specs[0].optional is False


class TestBigfinBouncerBounce:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        bigfin = BigfinBouncer(owner=p1, controller=p1)
        their_bear = _bear(p2, "Their Bear")
        set_board_state(game, 0, hand=[bigfin], mana={ManaType.BLUE: 4})
        set_board_state(game, 1, battlefield=[their_bear])
        return game, p1, p2, bigfin, their_bear

    def test_bounces_target_to_owner_hand(self):
        game, p1, p2, bigfin, their_bear = self._setup()
        cast_spell(game, 0, BigfinBouncer, targets=[their_bear])
        # Target left the battlefield and returned to its owner's hand.
        assert not game.get_battlefield(p2).contains(their_bear)
        assert game.get_hand(p2).contains(their_bear)
        # Bigfin itself entered the caster's battlefield afterward.
        assert game.get_battlefield(p1).contains(bigfin)

    def test_cost_is_paid(self):
        game, p1, p2, bigfin, their_bear = self._setup()
        cast_spell(game, 0, BigfinBouncer, targets=[their_bear])
        assert p1.mana_pool.total() == 0

    def test_filter_targets_only_opponent_creatures(self):
        """Legality invariant: the trigger's requirement accepts an opponent's
        creature and rejects one its controller controls."""
        game, p1, p2, bigfin, their_bear = self._setup()
        my_bear = _bear(p1, "My Bear")
        spec = bigfin._enters_targets(game, p1)[0]
        assert spec.filter_fn(their_bear) is True
        assert spec.filter_fn(my_bear) is False

    def test_no_legal_target_removes_the_trigger(self):
        """Required target with no opponent creature: the Bouncer still
        enters, and its trigger is removed from the stack (rule 603.3c)."""
        game = create_game()
        p1, p2 = game.players
        bigfin = BigfinBouncer(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[bigfin], mana={ManaType.BLUE: 4})
        cast_spell(game, 0, BigfinBouncer)
        assert game.get_battlefield(p1).contains(bigfin)
        assert game.stack.is_empty()

    def test_target_control_change_before_resolution_no_bounce(self):
        """Negative revalidation: after the trigger chose it, the target comes
        under the trigger's controller → no longer 'a creature an opponent
        controls', so it is not bounced."""
        game, p1, p2, bigfin, their_bear = self._setup()
        _cast_and_place_trigger(game, 0, bigfin, [their_bear])
        (trigger,) = game.stack.objects()
        assert trigger.targets == [their_bear]
        their_bear.controller = p1  # the trigger's controller now controls it
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(their_bear)  # not bounced
        assert not game.get_hand(p2).contains(their_bear)
