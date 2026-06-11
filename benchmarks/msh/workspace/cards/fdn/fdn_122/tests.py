"""Reference test for FDN 122 — Kykar, Zephyr Awakener.

Illustrative test covering the **flicker leg of the cast trigger**: exile
another creature you control, return it at the beginning of the next end
step. The flicker drives both legs through ``move_to_zone``, so it also
pins the instance-id contract — a zone change yields a new object, and the
returned creature must carry a fresh instance id even though no query ever
observes the exile stint.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_122.card_impl import KykarZephyrAwakener
from engine.card import Creature, Instant
from engine.decisions import Decision, GameRef, UnmatchedQueryError
from engine.events import EndStepTriggeredEvent, SpellCastTriggeredEvent
from engine.intent_player import Intent
from engine.types import ManaCost, Zone
from test_utils import create_game, set_board_state


def _flicker_setup():
    """Kykar + a bear on p1's battlefield, triggers registered."""
    game = create_game()
    p1 = game.players[0]
    kykar = KykarZephyrAwakener()
    bear = Creature(name="Bear", base_power=2, base_toughness=2)
    set_board_state(game, 0, battlefield=[kykar, bear])
    kykar.register_triggers(game)
    return game, p1, kykar, bear


def _cast_noncreature(game, p1):
    """Fire the cast event for a noncreature spell and resolve the trigger."""
    from engine.stack import priority_loop

    spell = Instant(name="Some Instant", owner=p1, controller=p1)
    game.trigger_manager.fire_event(
        game, SpellCastTriggeredEvent(spell=spell, player=p1)
    )
    priority_loop(game)  # resolve the pushed trigger (auto-pass)


class TestKykarProperties:
    """Static card data should match the FDN 122 spec."""

    def test_name(self) -> None:
        assert KykarZephyrAwakener().name == "Kykar, Zephyr Awakener"

    def test_mana_cost(self) -> None:
        assert KykarZephyrAwakener().mana_cost == ManaCost.parse("{2}{W}{U}")


class TestKykarFlicker:
    """Flicker mode: exile via move_to_zone, return at the next end step."""

    def test_flicker_exiles_then_returns_with_fresh_instance_id(self) -> None:
        game, p1, kykar, bear = _flicker_setup()
        pre_flicker = game.refs.instance_id(bear, "battlefield")

        # One intent answers both queries the trigger raises: the MODE query
        # (flicker) and the OBJECT query (the bear).
        p1.start_intent("kykar", Intent(
            pattern=GameRef(card=frozenset({("name", "Kykar, Zephyr Awakener")})),
            preferences=(
                Decision.mode("flicker"),
                Decision.obj(instance=pre_flicker),
            ),
        ))
        _cast_noncreature(game, p1)
        p1.end_intent("kykar")

        # Exile leg: the bear left the battlefield with no query observing it.
        assert p1.zones[Zone.EXILE].contains(bear)
        assert not p1.zones[Zone.BATTLEFIELD].contains(bear)

        # Return leg at the next end step.
        from engine.stack import priority_loop

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))
        priority_loop(game)
        assert p1.zones[Zone.BATTLEFIELD].contains(bear)

        # The returned creature is a new object: fresh instance id even
        # though the exile stint was never observed (the real fdn_122 path
        # the registry's stint-minting must cover).
        post_flicker = game.refs.instance_id(bear, "battlefield")
        assert post_flicker != pre_flicker

    def test_unanswered_query_is_a_hard_failure_not_a_token(self) -> None:
        # Fault attribution: with no intent and no baseline, the trigger's
        # MODE query must surface as UnmatchedQueryError (test-fault) — never
        # silently become "make a token" the way the deleted V1-era
        # try/except-Exception fallback made it.
        from engine.stack import priority_loop

        game, p1, kykar, bear = _flicker_setup()
        spell = Instant(name="Some Instant", owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=spell, player=p1)
        )
        with pytest.raises(UnmatchedQueryError):
            priority_loop(game)
        bf = p1.zones[Zone.BATTLEFIELD].get_all()
        assert not any(getattr(c, "name", "") == "Spirit" for c in bf)

    def test_token_mode_creates_spirit_and_no_flicker(self) -> None:
        game, p1, kykar, bear = _flicker_setup()
        p1.start_intent("kykar", Intent(
            pattern=GameRef(card=frozenset({("name", "Kykar, Zephyr Awakener")})),
            preferences=(Decision.mode("token"),),
        ))
        _cast_noncreature(game, p1)
        p1.end_intent("kykar")
        bf = p1.zones[Zone.BATTLEFIELD].get_all()
        assert any(getattr(c, "name", "") == "Spirit" for c in bf)
        assert p1.zones[Zone.BATTLEFIELD].contains(bear)
        assert not p1.zones[Zone.EXILE].contains(bear)
