"""Reference test for FDN 256 — Meteor Golem.

Pattern 1 — required targeted enters trigger on a creature. The Golem enters,
then its enters ability goes on the stack choosing "target nonland permanent
an opponent controls" through a real Player Query (rule 603.3d), and destroys
it as it resolves, checking the target again (rule 608.2b). No dead test
backdoors — targeting flows through real engine channels.
"""

from __future__ import annotations

from cards.fdn.fdn_256.card_impl import MeteorGolem
from engine.basic_lands import Forest
from engine.card import Artifact, Creature, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, DecisionKind, GameRef
from test_utils import Intent
from engine.stack import resolve_top_of_stack
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from engine.zones import move_to_zone
from test_utils import cast_spell, create_game, set_board_state


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


class TestMeteorGolemProperties:
    def test_static_data(self):
        golem = MeteorGolem(owner=None)
        assert printed_class(golem) is MeteorGolem
        assert golem.mana_cost == ManaCost.parse("{7}")
        assert (golem.base_power, golem.base_toughness) == (3, 3)
        assert "Golem" in golem.subtypes


class TestMeteorGolemETB:
    def _setup(self, opp_permanents):
        game = create_game()
        p1, p2 = game.players
        golem = MeteorGolem(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[golem], mana={ManaType.COLORLESS: 7})
        set_board_state(game, 1, battlefield=opp_permanents)
        return game, p1, p2, golem

    def test_destroys_opponents_creature(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, p2, golem = self._setup([bear])
        cast_spell(game, 0, MeteorGolem, targets=[bear])
        assert p2.zones[Zone.GRAVEYARD].contains(bear)
        assert game.get_battlefield(p1).contains(golem)

    def test_destroys_opponents_artifact(self):
        signet = Artifact(name="Signet")
        game, p1, p2, golem = self._setup([signet])
        cast_spell(game, 0, MeteorGolem, targets=[signet])
        assert p2.zones[Zone.GRAVEYARD].contains(signet)

    def test_option_set_excludes_lands_and_own_permanents(self):
        """Legality invariant: no land, and nothing the caster controls, is offered."""
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        forest = Forest(name="Forest")
        game = create_game()
        p1, p2 = game.players
        golem = MeteorGolem(owner=p1, controller=p1)
        mine = Creature(name="My Creature", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[golem], battlefield=[mine], mana={ManaType.COLORLESS: 7})
        set_board_state(game, 1, battlefield=[bear, forest])
        cast_spell(game, 0, MeteorGolem, targets=[bear])
        obj_queries = [
            r for r in p1.transcript.all()
            if any(o.kind is DecisionKind.OBJECT for o in r.options)
        ]
        assert obj_queries, "no target query was raised"
        offered_names = {
            dict(o.attrs).get("name")
            for r in obj_queries
            for o in r.options
            if o.kind is DecisionKind.OBJECT
        }
        assert "Forest" not in offered_names      # land excluded
        assert "My Creature" not in offered_names  # own permanent excluded
        assert "Bear" in offered_names             # opponent's nonland offered

    def test_unchanged_target_is_destroyed_when_the_trigger_resolves(self):
        """Control for the revalidation tests below: with its target unchanged,
        the waiting enters trigger destroys it."""
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, p2, golem = self._setup([bear])
        _cast_and_place_trigger(game, 0, golem, [bear])
        assert game.get_battlefield(p2).contains(bear)          # still waiting
        resolve_top_of_stack(game)
        assert p2.zones[Zone.GRAVEYARD].contains(bear)
        assert game.stack.is_empty()

    def test_target_becomes_caster_controlled_before_resolution_not_destroyed(self):
        """Negative revalidation: the target comes under the trigger
        controller's control before the trigger resolves → no longer 'an
        opponent controls', not destroyed."""
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, p2, golem = self._setup([bear])
        _cast_and_place_trigger(game, 0, golem, [bear])
        bear.controller = p1  # caster now controls it
        resolve_top_of_stack(game)
        assert game.stack.is_empty()
        assert game.get_battlefield(p2).contains(bear)          # not destroyed
        assert not p2.zones[Zone.GRAVEYARD].contains(bear)

    def test_target_becomes_land_before_resolution_not_destroyed(self):
        """Negative revalidation: the target becomes a land before the trigger
        resolves → no longer a 'nonland permanent', so it is not destroyed."""
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, p2, golem = self._setup([bear])
        _cast_and_place_trigger(game, 0, golem, [bear])
        bear.card_types = set(bear.card_types) | {CardType.LAND}  # became a land
        resolve_top_of_stack(game)
        assert game.stack.is_empty()
        assert game.get_battlefield(p2).contains(bear)          # not destroyed
        assert not p2.zones[Zone.GRAVEYARD].contains(bear)

    def test_target_leaves_and_returns_before_resolution_not_destroyed(self):
        """Leave-and-return: the target creature leaves the battlefield and
        returns (a new object in the same Python instance) before the trigger
        resolves. It satisfies the predicate again, but the trigger's captured
        zone stint rejects the returned object — it is not destroyed."""
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, p2, golem = self._setup([bear])
        _cast_and_place_trigger(game, 0, golem, [bear])
        move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.EXILE)
        move_to_zone(game, bear, Zone.EXILE, Zone.BATTLEFIELD)  # new stint
        resolve_top_of_stack(game)
        assert game.stack.is_empty()
        assert game.get_battlefield(p2).contains(bear)          # not destroyed
        assert not p2.zones[Zone.GRAVEYARD].contains(bear)
