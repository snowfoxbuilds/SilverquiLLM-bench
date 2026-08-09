"""Reference test for FDN 188 — Abrade.

Pattern 5 — modal spell ("choose one —"). The mode is chosen in
``get_targets`` via ``choose_mode`` (a real MODE Player Query); the chosen mode
selects which ``TargetRequirement`` is returned, so mode 0 targets a creature
and mode 1 targets an artifact. A single Intent answers both the MODE query and
the target query. ``on_resolve`` branches on the stashed mode index. No dead test backdoors —
targeting flows through real engine channels.
"""

from __future__ import annotations

from cards.fdn.fdn_188.card_impl import Abrade
from engine.card import Artifact, Creature
from engine.decisions import Decision, DecisionKind, GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _cast_modal(game, idx, name, mode_name, target):
    """Cast a modal spell answering both the MODE query and the target query
    from one Intent."""
    player = game.players[idx]
    inst = game.refs.instance_id(target, Zone.BATTLEFIELD.value)
    player.start_intent("modal", Intent(
        pattern=GameRef(card=frozenset({("name", name)})),
        preferences=(Decision.mode(mode_name), Decision.obj(instance=inst)),
    ))
    try:
        cast_spell(game, idx, name)
    finally:
        player.end_intent("modal")


def _prime(game):
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN


class TestAbradeProperties:
    def test_static_data(self):
        abrade = Abrade(owner=None)
        assert abrade.name == "Abrade"
        assert abrade.mana_cost == ManaCost.parse("{1}{R}")
        assert len(abrade.get_modes()) == 2


class TestAbradeDamageMode:
    def test_deals_3_damage_and_kills(self):
        game = create_game()
        p1, p2 = game.players
        abrade = Abrade(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[abrade], mana={ManaType.RED: 2})
        set_board_state(game, 1, battlefield=[bear])
        _prime(game)
        _cast_modal(game, 0, "Abrade", "Damage", bear)
        assert p2.zones[Zone.GRAVEYARD].contains(bear)

    def test_deals_exactly_3_damage(self):
        game = create_game()
        p1, p2 = game.players
        abrade = Abrade(owner=p1, controller=p1)
        wall = Creature(name="Wall", base_power=0, base_toughness=5)
        set_board_state(game, 0, hand=[abrade], mana={ManaType.RED: 2})
        set_board_state(game, 1, battlefield=[wall])
        _prime(game)
        _cast_modal(game, 0, "Abrade", "Damage", wall)
        assert game.get_battlefield(p2).contains(wall)     # survives (5 > 3)
        assert wall.damage_marked == 3

    def test_damage_mode_offers_only_creatures(self):
        """Option-set invariant: mode 0 targets creatures, never the artifact."""
        game = create_game()
        p1, p2 = game.players
        abrade = Abrade(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        signet = Artifact(name="Signet")
        set_board_state(game, 0, hand=[abrade], mana={ManaType.RED: 2})
        set_board_state(game, 1, battlefield=[bear, signet])
        _prime(game)
        _cast_modal(game, 0, "Abrade", "Damage", bear)
        offered = {
            dict(o.attrs).get("name")
            for r in p1.transcript.queries(DecisionKind.OBJECT)
            for o in r.options
            if o.kind is DecisionKind.OBJECT
        }
        assert "Bear" in offered
        assert "Signet" not in offered


class TestAbradeDestroyArtifactMode:
    def test_destroys_target_artifact(self):
        game = create_game()
        p1, p2 = game.players
        abrade = Abrade(owner=p1, controller=p1)
        signet = Artifact(name="Signet")
        set_board_state(game, 0, hand=[abrade], mana={ManaType.RED: 2})
        set_board_state(game, 1, battlefield=[signet])
        _prime(game)
        _cast_modal(game, 0, "Abrade", "Destroy Artifact", signet)
        assert p2.zones[Zone.GRAVEYARD].contains(signet)

    def test_destroy_mode_offers_only_artifacts(self):
        """Option-set invariant: mode 1 targets artifacts, never the plain creature."""
        game = create_game()
        p1, p2 = game.players
        abrade = Abrade(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        signet = Artifact(name="Signet")
        set_board_state(game, 0, hand=[abrade], mana={ManaType.RED: 2})
        set_board_state(game, 1, battlefield=[bear, signet])
        _prime(game)
        _cast_modal(game, 0, "Abrade", "Destroy Artifact", signet)
        offered = {
            dict(o.attrs).get("name")
            for r in p1.transcript.queries(DecisionKind.OBJECT)
            for o in r.options
            if o.kind is DecisionKind.OBJECT
        }
        assert "Signet" in offered
        assert "Bear" not in offered
