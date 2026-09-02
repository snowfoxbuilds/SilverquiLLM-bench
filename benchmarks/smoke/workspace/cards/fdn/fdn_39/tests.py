"""Reference test for FDN 39 — Grappling Kraken.

Exemplar for a **triggered ability that targets** (Phase D): a landfall trigger
whose target is chosen when the ability resolves (the engine's trigger channel
has no cast-time targeting), via ``choose_object`` answered by an Intent. On
resolution the chosen opponent creature is tapped (through the
``engine.game.tap`` helper, never a raw tapped-field write) and gains a stun
counter.
"""

from __future__ import annotations

from cards.fdn.fdn_39.card_impl import GrapplingKraken
from engine.card import Creature, Land
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, Phase, Zone
from engine.zones import move_to_zone
from test_utils import create_game, resolve_stack, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _prefer(game, player, source_name, target):
    """Start an Intent on *player* selecting *target* for the landfall query."""
    inst = game.refs.instance_id(target, Zone.BATTLEFIELD.value)
    player.start_intent(
        "kraken",
        Intent(
            pattern=GameRef(card=frozenset({("name", source_name)})),
            preferences=(Decision.obj(instance=inst),),
        ),
    )


def _trigger_landfall(game, controller):
    """Move a land onto *controller*'s battlefield, firing landfall."""
    land = Land(name="Island", owner=controller, controller=controller)
    controller.zones[Zone.HAND].add(land)
    land.instance_id = game.refs.instance_id(land, "hand")
    move_to_zone(game, land, Zone.HAND, Zone.BATTLEFIELD)


def _setup():
    game = create_game()
    p1, p2 = game.players
    game.active_player_index = 0
    kraken = GrapplingKraken(owner=p1, controller=p1)
    opp = _bear("Opp Bear")
    set_board_state(game, 0, battlefield=[kraken])
    set_board_state(game, 1, battlefield=[opp])
    kraken.register_triggers(game)  # normally wired by move_to_zone on ETB
    game.phase = Phase.PRECOMBAT_MAIN
    return game, p1, p2, kraken, opp


class TestGrapplingKrakenProperties:
    def test_static_data(self):
        card = GrapplingKraken(owner=None)
        assert card.name == "Grappling Kraken"
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")
        assert (card.base_power, card.base_toughness) == (5, 6)
        assert card.subtypes == {"Kraken"}


class TestGrapplingKrakenLandfall:
    def test_landfall_taps_and_stuns_opponent_creature(self):
        game, p1, p2, kraken, opp = _setup()
        assert opp.is_tapped is False
        _prefer(game, p1, "Grappling Kraken", opp)
        _trigger_landfall(game, p1)          # pushes the landfall trigger
        assert not game.stack.is_empty()
        resolve_stack(game)
        p1.end_intent("kraken")

        assert opp.is_tapped is True
        assert opp.counters.get("stun") == 1

    def test_no_opponent_creature_is_a_noop(self):
        """Option-set invariant: with no opponent creature there is no legal
        target — landfall resolves doing nothing (no query, no error)."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        kraken = GrapplingKraken(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[kraken])
        kraken.register_triggers(game)
        game.phase = Phase.PRECOMBAT_MAIN

        _trigger_landfall(game, p1)
        resolve_stack(game)  # must not raise even with nothing to target

    def test_landfall_only_from_your_own_land(self):
        """The trigger condition ignores a land an opponent plays — only *your*
        land's entry triggers landfall, so the opponent creature stays untapped."""
        game, p1, p2, kraken, opp = _setup()
        # An opponent land entering must not fire the Kraken's landfall.
        _trigger_landfall(game, p2)
        assert game.stack.is_empty()
        assert opp.is_tapped is False
