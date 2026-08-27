"""Engine tests for the shared activation-context helpers.

These exercise the *single* centralized mechanism every targeted activated,
loyalty, and triggered ability uses (``engine.stack``): capturing the
activation-time controller and source/target stints, and revalidating captured
targets at resolution. The Required-tests §3 scenarios — target leaves and
returns, source changes controller, target changes controller, two activations
coexist — are asserted directly against the helpers here (the Equipment path in
test_phase_c_primitives asserts the same invariants end-to-end).
"""

from __future__ import annotations

from engine.card import Creature
from engine.stack import (
    ActivationContext,
    battlefield_stint_id,
    capture_activation_context,
    object_stint_id,
    same_stint,
    surviving_targets,
)
from engine.types import Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


def _creature(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _controls(controller):
    return lambda t: getattr(t, "controller", None) is controller


class TestStintCapture:
    def test_battlefield_target_captured_and_matches(self):
        game = create_game()
        p1 = game.players[0]
        bear = _creature(p1)
        set_board_state(game, 0, battlefield=[bear])
        ctx = capture_activation_context(game, bear, p1, [bear])
        assert ctx.target_instance_ids[0] is not None
        assert same_stint(game, bear, ctx.target_instance_ids[0])

    def test_graveyard_target_captured_zone_generically(self):
        """A target in a graveyard is captured by its graveyard stint (not
        battlefield-only), so Scavenging-Ooze-style graveyard targeting works."""
        game = create_game()
        p1 = game.players[0]
        card = _creature(p1, "Dead Bear")
        set_board_state(game, 0, graveyard=[card])
        ctx = capture_activation_context(game, card, p1, [card])
        assert ctx.target_instance_ids[0] is not None
        assert same_stint(game, card, ctx.target_instance_ids[0])
        # It is NOT on the battlefield, so a battlefield-only capture would miss.
        assert battlefield_stint_id(game, card) is None

    def test_object_in_no_zone_has_no_stint(self):
        game = create_game()
        p1 = game.players[0]
        loose = _creature(p1, "Loose")  # never placed into a zone
        assert object_stint_id(game, loose) is None
        assert not same_stint(game, loose, 12345)


class TestLeaveAndReturn:
    def test_leave_and_return_rejected(self):
        game = create_game()
        p1 = game.players[0]
        bear = _creature(p1)
        set_board_state(game, 0, battlefield=[bear])
        ctx = capture_activation_context(game, bear, p1, [bear])
        move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.EXILE)
        move_to_zone(game, bear, Zone.EXILE, Zone.BATTLEFIELD)  # new stint
        assert not same_stint(game, bear, ctx.target_instance_ids[0])
        assert surviving_targets(game, ctx, [bear]) == []

    def test_departed_target_rejected(self):
        game = create_game()
        p1 = game.players[0]
        bear = _creature(p1)
        set_board_state(game, 0, battlefield=[bear])
        ctx = capture_activation_context(game, bear, p1, [bear])
        move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.GRAVEYARD)  # left, stays gone
        assert not same_stint(game, bear, ctx.target_instance_ids[0])


class TestControllerSemantics:
    def test_context_controller_fixed_when_source_controller_changes(self):
        """The captured controller is the activation-time controller; mutating
        the source's current controller afterward does not change it."""
        game = create_game()
        p1, p2 = game.players
        source = _creature(p1, "Source")
        bear = _creature(p1, "Bear")
        set_board_state(game, 0, battlefield=[source, bear])
        ctx = capture_activation_context(game, source, p1, [bear])
        source.controller = p2  # source changes controller after activation
        # "you control" is still evaluated relative to p1 (context.controller).
        assert ctx.controller is p1
        assert surviving_targets(game, ctx, [bear], is_legal=_controls(ctx.controller)) == [bear]

    def test_target_control_change_makes_it_illegal(self):
        game = create_game()
        p1, p2 = game.players
        bear = _creature(p1, "Bear")
        set_board_state(game, 0, battlefield=[bear])
        ctx = capture_activation_context(game, bear, p1, [bear])
        bear.controller = p2  # target changes controller (stint-preserving)
        # Still the same stint, but no longer "a creature you (p1) control".
        assert same_stint(game, bear, ctx.target_instance_ids[0])
        assert surviving_targets(game, ctx, [bear], is_legal=_controls(p1)) == []

    def test_player_target_always_present(self):
        game = create_game()
        p1, p2 = game.players
        ctx = capture_activation_context(game, _creature(p1), p1, [p2])
        # Players are not zone residents; they always survive stint validation.
        assert same_stint(game, p2, None)
        assert surviving_targets(game, ctx, [p2]) == [p2]


class TestContextCoexistence:
    def test_two_activations_independent_contexts(self):
        """Two activations from the same source capture independent contexts —
        neither clobbers the other (contexts live on the stack objects)."""
        game = create_game()
        p1, p2 = game.players
        source = _creature(p1, "Source")
        bear_a = _creature(p1, "A")
        bear_b = _creature(p2, "B")
        set_board_state(game, 0, battlefield=[source, bear_a])
        set_board_state(game, 1, battlefield=[bear_b])
        ctx_a = capture_activation_context(game, source, p1, [bear_a])
        ctx_b = capture_activation_context(game, source, p1, [bear_b])
        assert ctx_a is not ctx_b
        assert ctx_a.target_instance_ids != ctx_b.target_instance_ids
        assert surviving_targets(game, ctx_a, [bear_a]) == [bear_a]
        assert surviving_targets(game, ctx_b, [bear_b]) == [bear_b]

    def test_positional_alignment(self):
        """Two targets: each is revalidated against its own captured stint."""
        game = create_game()
        p1 = game.players[0]
        a = _creature(p1, "A")
        b = _creature(p1, "B")
        set_board_state(game, 0, battlefield=[a, b])
        ctx = capture_activation_context(game, a, p1, [a, b])
        move_to_zone(game, a, Zone.BATTLEFIELD, Zone.GRAVEYARD)  # only a leaves
        assert surviving_targets(game, ctx, [a, b]) == [b]
