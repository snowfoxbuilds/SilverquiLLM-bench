"""Reference test for FDN 144 — Mischievous Pup.

Pattern 1 — optional ("up to one") targeted enters trigger on a creature. The
Pup enters, then its enters ability goes on the stack choosing "up to one other
target permanent you control" through a real Player Query (rule 603.3d), and
returns it to its owner's hand as it resolves, checking the target again
(rule 608.2b). Because the target is optional, the trigger goes on the stack
with zero targets (no legal choice, or a decline). No dead test backdoors —
targeting flows through real engine channels.
"""

from __future__ import annotations

from cards.fdn.fdn_144.card_impl import MischievousPup
from engine.card import Creature, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from test_utils import Intent
from engine.stack import resolve_top_of_stack
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2)


def _cast_and_place_trigger(game, player_index, card, targets):
    """Cast *card* and resolve the creature spell; as the game settles, its
    enters trigger goes on the stack choosing *targets* (rule 603.3d) — and
    stop there, so a test can change a target before the trigger resolves."""
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
    finally:
        player.end_intent("cast")
    (trigger,) = game.stack.objects()
    assert not trigger.is_spell
    assert trigger.targets == list(targets)


class TestMischievousPupProperties:
    def test_static_data(self):
        pup = MischievousPup(owner=None)
        assert printed_class(pup) is MischievousPup
        assert pup.mana_cost == ManaCost.parse("{2}{W}")
        assert (pup.base_power, pup.base_toughness) == (3, 1)
        assert "Dog" in pup.subtypes
        assert Keyword.FLASH in pup.keywords


class TestMischievousPupETB:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        pup = MischievousPup(owner=p1, controller=p1)
        bear = _bear()
        set_board_state(game, 0, hand=[pup], battlefield=[bear], mana={ManaType.WHITE: 3})
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        return game, p1, p2, pup, bear

    def test_bounces_chosen_permanent(self):
        game, p1, p2, pup, bear = self._setup()
        cast_spell(game, 0, MischievousPup, targets=[bear])
        assert game.get_hand(p1).contains(bear)          # returned to owner's hand
        assert not game.get_battlefield(p1).contains(bear)
        assert game.get_battlefield(p1).contains(pup)     # the Pup itself entered

    def test_castable_with_no_legal_target(self):
        """'Up to one' → castable when the controller has no other permanent."""
        game = create_game()
        p1, p2 = game.players
        pup = MischievousPup(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[pup], mana={ManaType.WHITE: 3})
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        cast_spell(game, 0, MischievousPup)  # no target offered, no query
        assert game.get_battlefield(p1).contains(pup)

    def test_optional_target_can_be_declined(self):
        """A legal target exists but the controller declines — nothing bounced."""
        game, p1, p2, pup, bear = self._setup()
        # An intent that matches the Pup's target query but expresses no
        # preference: a min==0 (optional) query is declined rather than filled.
        p1.start_intent("decline", Intent(
            pattern=GameRef(card=frozenset({("printed", MischievousPup)})),
            preferences=(),
        ))
        cast_spell(game, 0, MischievousPup)
        p1.end_intent("decline")
        assert game.get_battlefield(p1).contains(bear)   # not bounced
        assert game.get_battlefield(p1).contains(pup)

    def test_unchanged_target_is_bounced_when_the_trigger_resolves(self):
        """Control for the revalidation test below: with its target unchanged,
        the waiting enters trigger returns it to its owner's hand."""
        game, p1, p2, pup, bear = self._setup()
        _cast_and_place_trigger(game, 0, pup, [bear])
        assert game.get_battlefield(p1).contains(bear)   # still waiting
        resolve_top_of_stack(game)
        assert game.get_hand(p1).contains(bear)
        assert game.stack.is_empty()

    def test_target_control_change_before_resolution_no_bounce(self):
        """Negative revalidation: the trigger's target leaves its controller's
        control before the trigger resolves → no longer 'a permanent you
        control', so it is not bounced."""
        game, p1, p2, pup, bear = self._setup()
        _cast_and_place_trigger(game, 0, pup, [bear])
        bear.controller = p2  # no longer controlled by the trigger's controller
        resolve_top_of_stack(game)
        assert game.stack.is_empty()
        assert game.get_battlefield(p1).contains(bear)   # not bounced
        assert not game.get_hand(p1).contains(bear)
