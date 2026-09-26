"""Reference test for FDN 38 — Faebloom Trick.

Pattern 1 — targeted spell, but with an *optional* ("up to one") target. The
spell always creates two Faerie tokens; its reflexive "when you do, tap target
creature an opponent controls" is modelled as an optional TargetRequirement so
the spell stays castable (and still makes tokens) when there is no opponent
creature. Targeting is intent-style via ``cast_spell(targets=...)``.
"""

from __future__ import annotations

from cards.fdn.fdn_38.card_impl import FaebloomTrick
from engine.card import Creature
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
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
from test_utils import cast_spell, set_board_state
from test_utils import scenario_game as create_game


def _cast_no_resolve(game, player_index, card, targets):
    """Cast *card* but leave it on the stack (targets chosen, not resolved)."""
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    prefs = tuple(
        Decision.obj(instance=game.refs.instance_id(t, Zone.BATTLEFIELD.value)) for t in targets
    )
    player.start_intent(
        "cast",
        Intent(
            pattern=GameRef(card=frozenset({("name", card.name)})),
            preferences=prefs,
        ),
    )
    try:
        engine_cast_spell(game, player, card)
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
        assert c.name == "Faebloom Trick"
        assert c.mana_cost == ManaCost.parse("{2}{U}")
        assert CardType.INSTANT in c.card_types


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
        game, p1, _p2, _trick, their_bear = self._setup()
        cast_spell(game, 0, "Faebloom Trick", targets=[their_bear])
        faeries = _faeries(game, p1)
        assert len(faeries) == 2
        for f in faeries:
            assert (f.base_power, f.base_toughness) == (1, 1)
            assert Keyword.FLYING & f.keywords
        # Reflexive trigger tapped the chosen opponent creature.
        assert their_bear.is_tapped is True

    def test_cost_is_paid(self):
        game, p1, _p2, _trick, their_bear = self._setup()
        cast_spell(game, 0, "Faebloom Trick", targets=[their_bear])
        assert p1.mana_pool.total() == 0

    def test_castable_with_no_target_still_makes_tokens(self):
        """Optional target: with no opponent creature the spell still resolves
        and makes both tokens; nothing is tapped."""
        game = create_game()
        p1, _p2 = game.players
        trick = FaebloomTrick(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[trick], mana={ManaType.BLUE: 3})
        cast_spell(game, 0, "Faebloom Trick")  # no targets available/needed
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

        _cast_no_resolve(game, 0, trick, [their_bear])
        # Before resolution, control of the target passes to the caster — it is
        # no longer "a creature an opponent controls".
        their_bear.controller = p1
        while not game.stack.is_empty():
            resolve_top_of_stack(game)

        # Tap did nothing; the tokens still appeared.
        assert their_bear.is_tapped is False
        assert len(_faeries(game, p1)) == 2


class TestFaebloomTrickTokenIdentity:
    """The two minted tokens carry the exact 1/1 blue flying Faerie identity
    (subtypes, explicit blue colour, base P/T, flying, ``is_token``) that
    replay correlation keys to the Faerie grpId."""

    def test_tokens_are_blue_flying_faeries(self):
        from test_utils import cast_card, fund_mana_cost

        game = create_game()
        p1 = game.players[0]
        spell = FaebloomTrick(owner=p1)
        fund_mana_cost(p1, spell.mana_cost)
        cast_card(game, p1, spell)
        tokens = [
            card for card in game.get_battlefield(p1).get_all() if getattr(card, "is_token", False)
        ]
        assert len(tokens) == 2
        for token in tokens:
            assert token.subtypes == {"Faerie"} and get_colors(token) == {Color.BLUE}
            assert (token.power, token.toughness) == (1, 1) and token.keywords & Keyword.FLYING
