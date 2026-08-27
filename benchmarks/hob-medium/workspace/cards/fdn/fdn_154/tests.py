"""Regression tests for FDN 154 — Extravagant Replication.

"At the beginning of your upkeep, create a token that's a copy of another
target nonland permanent you control." The copy is minted through
:func:`engine.game.mint_token_copy` (rule 707.2): the placed token is a distinct
game object — its own ``object_id``, de-aliased characteristic containers, and
none of the copied permanent's counters/damage/tap — carrying only the copiable
characteristics. Before the engine primitive landed the impl used a bare
``copy.copy`` that shared the original's ``object_id`` while both were live.
"""

from __future__ import annotations

from cards.fdn.fdn_154.card_impl import ExtravagantReplication
from engine.card import Creature, Enchantment
from engine.decisions import Decision, GameRef
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import add_counter
from engine.intent_player import Intent
from engine.stack import priority_loop
from engine.types import ManaCost, Zone
from test_utils import create_game, set_board_state


def _copy_tokens(game, player, name):
    return [
        o
        for o in game.get_battlefield(player).get_all()
        if getattr(o, "is_token", False) and getattr(o, "name", None) == name
    ]


def _fire_upkeep_copying(game, p1, replication, chosen):
    """Fire the upkeep trigger, choosing *chosen* to copy via an Intent."""
    replication.register_triggers(game)
    chosen_iid = game.refs.instance_id(chosen, Zone.BATTLEFIELD.value)
    p1.start_intent(
        "replicate",
        Intent(pattern=GameRef(), preferences=(Decision.obj(instance=chosen_iid),)),
    )
    try:
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        priority_loop(game)
    finally:
        p1.end_intent("replicate")


class TestExtravagantReplicationProperties:
    def test_is_enchantment(self) -> None:
        assert isinstance(ExtravagantReplication(owner=None), Enchantment)

    def test_mana_cost(self) -> None:
        assert ExtravagantReplication(owner=None).mana_cost == ManaCost.parse("{4}{U}{U}")


class TestExtravagantReplicationCopyToken:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        replication = ExtravagantReplication(owner=p1, controller=p1)
        bear = Creature(
            name="Grizzly Bears", base_power=2, base_toughness=2,
            subtypes={"Bear"}, owner=p1, controller=p1,
        )
        set_board_state(game, 0, battlefield=[replication, bear])
        assert game.active_player is p1  # upkeep trigger only fires on your turn
        return game, p1, replication, bear

    def test_upkeep_creates_one_token_copy(self) -> None:
        game, p1, replication, bear = self._setup()
        _fire_upkeep_copying(game, p1, replication, bear)
        assert len(_copy_tokens(game, p1, "Grizzly Bears")) == 1

    def test_token_is_a_distinct_object(self) -> None:
        """The placed token differs in identity from the copied permanent — the
        crux the object_id re-mint fixes (copy.copy shared the id)."""
        game, p1, replication, bear = self._setup()
        _fire_upkeep_copying(game, p1, replication, bear)
        token = _copy_tokens(game, p1, "Grizzly Bears")[0]
        assert token is not bear
        assert token.object_id != bear.object_id

    def test_token_carries_copiable_characteristics(self) -> None:
        """Existing behaviour preserved: the token is a functional copy."""
        game, p1, replication, bear = self._setup()
        _fire_upkeep_copying(game, p1, replication, bear)
        token = _copy_tokens(game, p1, "Grizzly Bears")[0]
        assert (token.base_power, token.base_toughness) == (2, 2)
        assert token.subtypes == {"Bear"}
        assert token.is_token is True
        assert token.controller is p1

    def test_token_containers_are_de_aliased(self) -> None:
        game, p1, replication, bear = self._setup()
        _fire_upkeep_copying(game, p1, replication, bear)
        token = _copy_tokens(game, p1, "Grizzly Bears")[0]
        assert token.subtypes is not bear.subtypes
        token.subtypes.add("Zombie")
        assert "Zombie" not in bear.subtypes

    def test_token_excludes_the_originals_counters(self) -> None:
        """Counters are not copiable (rule 707.2): the copy of a buffed creature
        is a base-P/T token, not a buffed one."""
        game, p1, replication, bear = self._setup()
        add_counter(game, bear, "+1/+1", 3)
        assert bear.power == 5
        _fire_upkeep_copying(game, p1, replication, bear)
        token = _copy_tokens(game, p1, "Grizzly Bears")[0]
        assert token.plus_one_counters == 0
        assert token.power == 2
