"""Known-Best checks moved out of fdn_248's FDN Audited Tests: no FDN card gains control of an enchantment, and no free cast reaches a card in the graveyard,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from typing import Any

from cards.fdn.fdn_248.card_impl import ThousandYearStorm, ThousandYearStormAbility1
from engine.card import Instant, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.casting import cast_spell_free
from engine.decisions import GameRef
from engine.stack import resolve_top_of_stack
from engine.types import ManaCost
from engine.zones import move_to_zone
from test_interface import Decision, Phase, Zone
from test_utils import Intent, enter_permanent, resolve_stack, set_board_state
from test_utils import create_game as legacy_create_game

STORM = ThousandYearStormAbility1
MAIN = (Phase.PRECOMBAT_MAIN, 0)
KEEP_TARGETS = Decision.no()
NEW_TARGETS = Decision.yes()


# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Each trigger keeps its own spell and copy count
# ---------------------------------------------------------------------------


class TestStormPerTriggerState:

    def _legacy_setup(self, hand):
        game = legacy_create_game()
        p1, _p2 = game.players
        storm = ThousandYearStorm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=hand, battlefield=[])
        game.active_player_index = 0
        enter_permanent(game, storm.controller, storm)  # count starts at 0, this turn — no seeding
        return game, p1, storm

    def test_control_change_after_fire_retains_fire_time_controller(self):
        """The trigger's controller is fixed at fire time. Changing control of
        Thousand-Year Storm *after* the trigger fires does not shift "you": the
        copy is still controlled by the fire-time controller."""
        prior, a = _Signal("Prior"), _Signal("Spell A")
        game, p1, storm = self._legacy_setup([prior, a])
        p2 = game.players[1]
        # One prior qualifying spell this turn — cast through the real pipeline
        # (no manual count seeding) — so A's trigger makes exactly one copy.
        _cast(game, p1, prior)
        _cast(game, p1, a)

        storm.controller = p2  # Storm changes hands before resolution

        new = _resolve_top_collect_new(game)  # resolve the Storm trigger
        assert len(new) == 1
        assert new[0].controller is p1  # fire-time controller, not p2


# ---------------------------------------------------------------------------
# Retargeting a copy uses the copied spell's whole targeting rules
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# The copy count is the caster's instant and sorcery casts this turn
# ---------------------------------------------------------------------------


class TestStormAuthoritativeCount:

    def test_control_change_reads_new_controllers_history(self):
        game = legacy_create_game()
        p1, p2 = game.players
        first, second, other = _Signal("First"), _Signal("Second"), _Signal("Other")
        set_board_state(game, 0, hand=[first, second])
        set_board_state(game, 1, hand=[other])
        storm = enter_permanent(game, p1, _legacy_storm(p1))
        _cast(game, p1, first)
        _cast(game, p1, second)
        _change_control(game, storm, p2)
        _cast(game, p2, other)
        assert _copy_count(game, other) == 0

    def test_separate_player_histories_are_not_merged_by_control_change(self):
        game = legacy_create_game()
        p1, p2 = game.players
        for name in ("A", "B", "C"):
            card = _Signal(name, owner=p1)
            game.get_hand(p1).add(card)
            _cast(game, p1, card)
        other = _Signal("Opponent", owner=p2)
        game.get_hand(p2).add(other)
        _cast(game, p2, other)
        storm = enter_permanent(game, p1, _legacy_storm(p1))
        _change_control(game, storm, p2)
        probe = _Signal("P2 probe", owner=p2)
        game.get_hand(p2).add(probe)
        _cast(game, p2, probe)
        assert _copy_count(game, probe) == 1
        _change_control(game, storm, p1)
        mine = _Signal("P1 probe", owner=p1)
        game.get_hand(p1).add(mine)
        _cast(game, p1, mine)
        assert _copy_count(game, mine) == 3

    def test_earlier_casts_still_count_after_regaining_control(self):
        game = legacy_create_game()
        p1, p2 = game.players
        first, second = _Signal("S1"), _Signal("S2")
        set_board_state(game, 0, hand=[first, second])
        storm = enter_permanent(game, p1, _legacy_storm(p1))
        _cast(game, p1, first)
        _change_control(game, storm, p2)
        _change_control(game, storm, p1)
        _cast(game, p1, second)
        assert _copy_count(game, second) == 1


# ---------------------------------------------------------------------------
# Casting the same card again counts each cast
# ---------------------------------------------------------------------------


class TestStormRepeatedObjectCasts:
    def _legacy_setup(self, hand):
        game = legacy_create_game()
        p1, _p2 = game.players
        storm = ThousandYearStorm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=hand, battlefield=[])
        game.active_player_index = 0
        enter_permanent(game, storm.controller, storm)  # no seeding — count starts at 0 this turn
        return game, p1, storm

    def _legacy_copy_count(self, game, storm, spell):
        assert game.stack.peek().source is storm
        return _copy_count(game, spell)

    def _legacy_return_to_hand(self, game, spell):
        """Resolve the stack (the just-cast instant goes to its graveyard) and
        move the very same object back to hand so it can be recast."""
        resolve_stack(game)
        move_to_zone(game, spell, Zone.GRAVEYARD, Zone.HAND)

    def test_free_recast_counts_prior_cast_and_records_once(self):
        """Through a free-cast path (cascade / exile casting): a previous normal
        cast of the same object still counts, and the free cast is recorded
        exactly once (the history gains a single occurrence)."""
        a = _Signal("Spell A")
        game, p1, storm = self._legacy_setup([a])

        _cast(game, p1, a)  # normal cast: 0
        assert self._legacy_copy_count(game, storm, a) == 0
        self._legacy_return_to_hand(game, a)

        turn = game.turn_number
        before = len(p1.instant_or_sorcery_casts_this_turn(turn))
        cast_spell_free(game, p1, a, Zone.HAND)  # free cast of SAME object
        game.trigger_manager.put_pending_on_stack(game)
        assert self._legacy_copy_count(game, storm, a) == 1  # the prior cast counts
        after = len(p1.instant_or_sorcery_casts_this_turn(turn))
        assert after - before == 1  # recorded exactly once


# ---------------------------------------------------------------------------
# Positions play cannot reach keep the legacy helpers below: no FDN card
# changes control of an enchantment, recasts the same spell a third time this
# turn, or casts it again for free from the graveyard.
# ---------------------------------------------------------------------------


class _Signal(Instant):
    """A {0} instant with no targets — used to drive the cast/count pipeline
    without any target queries."""

    def __init__(self, name: str, **kwargs: Any) -> None:
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost.parse("{0}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list:
        return []

    def on_resolve(self, game: Any) -> None:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cast(game, p1, spell, target_prefs=None):
    """Cast *spell* through the real pipeline, answering its cast-time target
    query (when it targets) with *target_prefs*, routed by the spell's own name."""
    if target_prefs is not None:
        p1.start_intent(
            "cast",
            Intent(
                pattern=GameRef(card=frozenset({("printed", printed_class(spell))})),
                preferences=tuple(target_prefs),
            ),
        )
        try:
            engine_cast_spell(game, p1, spell)
            game.trigger_manager.put_pending_on_stack(game)
        finally:
            p1.end_intent("cast")
    else:
        engine_cast_spell(game, p1, spell)
        # What the cast triggered goes on the stack before anyone would
        # receive priority (rule 117.5, 603.3).
        game.trigger_manager.put_pending_on_stack(game)


def _resolve_top_collect_new(game):
    """Resolve exactly the top stack object; return the objects it pushed."""
    before = list(game.stack.objects())
    resolve_top_of_stack(game)
    return [so for so in game.stack.objects() if all(so is not b for b in before)]


def _copy_count(game, spell):
    created = _resolve_top_collect_new(game)
    assert all(obj.source.name == spell.name and obj.source is not spell for obj in created)
    return len(created)


def _change_control(game, card, player):
    previous = card.controller
    game.get_battlefield(previous).remove(card)
    game.get_battlefield(player).add(card)
    card.controller = player


def _legacy_storm(p):
    return ThousandYearStorm(owner=p, controller=p)
