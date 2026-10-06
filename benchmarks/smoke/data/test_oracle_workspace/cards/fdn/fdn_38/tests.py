"""Reference test for FDN 38 — Faebloom Trick.

The spell itself has no targets: it creates two Faerie tokens, and its "when
you do, tap target creature an opponent controls" is a reflexive triggered
ability (rule 603.12) that triggers as the spell resolves and, like any other
triggered ability, goes on the stack when the game next settles, choosing its
target then (rule 603.3b, 603.3d). With no opponent creature the reflexive
trigger is removed and the tokens still appear. Targeting is intent-style via
``cast_spell(targets=...)``.
"""

from __future__ import annotations

from cards.fdn.fdn_38.card_impl import FaebloomTrick
from engine.card import Creature, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from test_utils import Intent
from engine.protection import get_colors
from engine.stack import resolve_top_of_stack
from engine.types import (
    CardType,
    Color,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Zone,
)
from test_utils import cast_spell, create_game, set_board_state


def _resolve_spell_only(game, player_index, card, targets):
    """Cast *card* and resolve the spell; as the game settles afterwards, its
    reflexive trigger goes on the stack choosing *targets* — and stop there,
    so a test can change the board before the trigger resolves."""
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


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _faeries(game, player):
    bf = game.get_battlefield(player)
    return [o for o in bf.get_all() if getattr(o, "name", None) == "Faerie"]


class TestFaebloomTrickProperties:
    def test_static_data(self):
        c = FaebloomTrick(owner=None)
        assert printed_class(c) is FaebloomTrick
        assert c.mana_cost == ManaCost.parse("{2}{U}")
        assert CardType.INSTANT in c.card_types

    def test_the_spell_targets_nothing(self):
        game = create_game()
        c = FaebloomTrick(owner=game.players[0], controller=game.players[0])
        assert c.get_targets(game) == []


class TestFaebloomTrickResolve:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        trick = FaebloomTrick(owner=p1, controller=p1)
        their_bear = _bear(p2, "Their Bear")
        set_board_state(game, 0, hand=[trick], mana={ManaType.BLUE: 3})
        set_board_state(game, 1, battlefield=[their_bear])
        return game, p1, p2, trick, their_bear

    def test_creates_two_flying_faeries_and_taps_target(self):
        game, p1, p2, trick, their_bear = self._setup()
        cast_spell(game, 0, FaebloomTrick, targets=[their_bear])
        faeries = _faeries(game, p1)
        assert len(faeries) == 2
        for f in faeries:
            assert (f.base_power, f.base_toughness) == (1, 1)
            assert Keyword.FLYING & f.keywords
        # Reflexive trigger tapped the chosen opponent creature.
        assert their_bear.is_tapped is True

    def test_cost_is_paid(self):
        game, p1, p2, trick, their_bear = self._setup()
        cast_spell(game, 0, FaebloomTrick, targets=[their_bear])
        assert p1.mana_pool.total() == 0

    def test_castable_with_no_target_still_makes_tokens(self):
        """Optional target: with no opponent creature the spell still resolves
        and makes both tokens; nothing is tapped."""
        game = create_game()
        p1, p2 = game.players
        trick = FaebloomTrick(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[trick], mana={ManaType.BLUE: 3})
        cast_spell(game, 0, FaebloomTrick)  # no targets available/needed
        assert len(_faeries(game, p1)) == 2


class TestFaebloomTrickRevalidation:
    """Rule 608.2b: the reflexive tap revalidates the FULL predicate ("a
    creature an opponent controls") at resolution, not merely presence."""

    def test_no_tap_when_target_leaves_opponent_control(self):
        game = create_game()
        p1, p2 = game.players
        trick = FaebloomTrick(owner=p1, controller=p1)
        their_bear = _bear(p2, "Their Bear")
        set_board_state(game, 0, hand=[trick], mana={ManaType.BLUE: 3})
        set_board_state(game, 1, battlefield=[their_bear])

        _resolve_spell_only(game, 0, trick, [their_bear])
        (reflexive,) = game.stack.objects()
        assert reflexive.targets == [their_bear]
        # Before the reflexive trigger resolves, control of the target passes
        # to the caster — it is no longer "a creature an opponent controls".
        their_bear.controller = p1
        resolve_top_of_stack(game)

        # Tap did nothing; the tokens still appeared.
        assert their_bear.is_tapped is False
        assert len(_faeries(game, p1)) == 2


class TestFaebloomTrickTokenIdentity:
    """The two minted tokens carry the exact 1/1 blue flying Faerie identity
    (subtypes, explicit blue colour, base P/T, flying, ``is_token``) that
    replay correlation keys to the Faerie grpId."""

    def test_tokens_are_blue_flying_faeries(self):
        game = create_game()
        p1 = game.players[0]
        trick = FaebloomTrick(owner=p1, controller=p1)
        # No opponent creature / no chosen target: the reflexive tap is a no-op
        # and only the two-token mint runs.
        trick.on_resolve(game)

        faeries = _faeries(game, p1)
        assert len(faeries) == 2
        for tok in faeries:
            assert tok.subtypes == {"Faerie"}
            assert get_colors(tok) == {Color.BLUE}
            assert (tok.base_power, tok.base_toughness) == (1, 1)
            assert Keyword.FLYING & tok.keywords
            assert tok.is_token is True
