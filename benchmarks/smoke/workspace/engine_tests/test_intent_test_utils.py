"""Phase 3 smoke tests: the rewritten test_utils drives the engine through the
intent-based DeterministicPlayer (board setup + action directives survive; the
choice channel is Intents, not a positional script)."""

from __future__ import annotations

from engine.card import Creature, Instant
from engine.decisions import Decision, DecisionKind, GameRef
from engine.intent_player import Intent
from engine.types import CardType, ManaCost, Zone
from test_utils import (
    cast_spell,
    create_game,
    put_on_battlefield,
    set_board_state,
)


class Zap(Instant):
    """Deal a 'zap' to target creature (marks ``zapped`` on resolve)."""

    def __init__(self):
        super().__init__(name="Zap", mana_cost=ManaCost(), card_types={CardType.INSTANT})

    def get_targets(self, game):
        from engine.types import TargetRequirement

        return [
            TargetRequirement(
                filter_fn=lambda o: CardType.CREATURE in getattr(o, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game):
        for target in getattr(self, "chosen_targets", []) or []:
            target.zapped = True


def _bear(name="Bear", **kw):
    return Creature(name=name, mana_cost=ManaCost(generic=1),
                    base_power=2, base_toughness=2, **kw)


class TestTargetsConvenience:
    def test_cast_with_targets_resolves_on_chosen_object(self):
        game = create_game()
        bear = put_on_battlefield(game, game.players[1], _bear())
        set_board_state(game, 0, hand=[Zap()])

        cast_spell(game, 0, "Zap", targets=[bear])

        assert getattr(bear, "zapped", False) is True


class TestExplicitIntent:
    def test_intent_preference_and_postcondition(self):
        game = create_game()
        p0 = game.players[0]
        # Two creatures: the intent must hit the chosen one by instance id.
        bear = put_on_battlefield(game, game.players[1], _bear("Bear"))
        ox = put_on_battlefield(game, game.players[1], _bear("Ox"))
        set_board_state(game, 0, hand=[Zap()])

        p0.start_intent("zap-bear", Intent(
            pattern=GameRef(card=frozenset({("name", "Zap")})),
            preferences=(Decision.obj(instance=bear.instance_id),),
            postcondition=lambda g: getattr(bear, "zapped", False),
        ))
        cast_spell(game, 0, "Zap")
        p0.end_intent("zap-bear")  # postcondition checked here

        assert getattr(bear, "zapped", False) is True
        assert getattr(ox, "zapped", False) is False

        # Option-set invariant over the transcript: only creatures were offered.
        last = p0.transcript.queries(kind=DecisionKind.OBJECT)[-1]
        assert all(("type", "creature") in opt.attrs for opt in last.options)
