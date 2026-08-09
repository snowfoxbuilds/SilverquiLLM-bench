"""Reference test for FDN 215 — Bushwhack.

Pattern 5 — modal spell ("choose one —"). The mode is chosen in
``get_targets`` via ``choose_mode`` (a real MODE Player Query):

* Fight mode returns two ``TargetRequirement`` specs (a creature you control and
  a creature you don't control); ``on_resolve`` makes each deal damage equal to
  its power to the other (implemented as two ``deal_damage`` calls, since the
  engine has no ``fight`` primitive).
* Search mode is non-target: ``on_resolve`` runs a ``choose_object`` over the
  basic lands in the controller's library and moves the chosen one to hand.

A single Intent answers the MODE query and (for Fight) both target queries.
No dead test backdoors — targeting flows through real engine channels.
"""

from __future__ import annotations

from cards.fdn.fdn_215.card_impl import Bushwhack
from engine.basic_lands import Forest
from engine.card import Creature, Land
from engine.decisions import Decision, DecisionKind, GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _cast_bushwhack(game, mode_name, obj_instance_ids):
    """Cast Bushwhack; one Intent answers the MODE query then each OBJECT query."""
    p1 = game.players[0]
    prefs = (Decision.mode(mode_name),) + tuple(
        Decision.obj(instance=i) for i in obj_instance_ids
    )
    p1.start_intent("bw", Intent(
        pattern=GameRef(card=frozenset({("name", "Bushwhack")})),
        preferences=prefs,
    ))
    try:
        cast_spell(game, 0, "Bushwhack")
    finally:
        p1.end_intent("bw")


def _put_in_library(game, player, card):
    card.owner = player
    card.controller = player
    player.zones[Zone.LIBRARY].add(card)
    card.instance_id = game.refs.instance_id(card, Zone.LIBRARY.value)
    return card


class TestBushwhackProperties:
    def test_static_data(self):
        bw = Bushwhack(owner=None)
        assert bw.name == "Bushwhack"
        assert bw.mana_cost == ManaCost.parse("{G}")
        assert len(bw.get_modes()) == 2


class TestBushwhackFight:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        bw = Bushwhack(owner=p1, controller=p1)
        ours = Creature(name="Ours", base_power=3, base_toughness=3)
        theirs = Creature(name="Theirs", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[bw], battlefield=[ours], mana={ManaType.GREEN: 1})
        set_board_state(game, 1, battlefield=[theirs])
        return game, p1, p2, ours, theirs

    def test_each_creature_deals_its_power_to_the_other(self):
        game, p1, p2, ours, theirs = self._setup()
        _cast_bushwhack(game, "Fight", [ours.instance_id, theirs.instance_id])
        # Ours (3/3) deals 3 → Theirs (1/1) dies; Theirs deals 1 → Ours survives.
        assert p2.zones[Zone.GRAVEYARD].contains(theirs)
        assert game.get_battlefield(p1).contains(ours)
        assert ours.damage_marked == 1

    def test_mutual_destruction(self):
        game = create_game()
        p1, p2 = game.players
        bw = Bushwhack(owner=p1, controller=p1)
        ours = Creature(name="Ours", base_power=2, base_toughness=2)
        theirs = Creature(name="Theirs", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[bw], battlefield=[ours], mana={ManaType.GREEN: 1})
        set_board_state(game, 1, battlefield=[theirs])
        _cast_bushwhack(game, "Fight", [ours.instance_id, theirs.instance_id])
        assert p1.zones[Zone.GRAVEYARD].contains(ours)
        assert p2.zones[Zone.GRAVEYARD].contains(theirs)

    def test_fight_targets_split_by_control(self):
        """Option-set invariant: the first target is a creature you control, the
        second a creature you don't control — the two option sets are disjoint."""
        game, p1, p2, ours, theirs = self._setup()
        _cast_bushwhack(game, "Fight", [ours.instance_id, theirs.instance_id])
        obj_records = p1.transcript.queries(DecisionKind.OBJECT)
        assert len(obj_records) == 2
        first = {dict(o.attrs).get("name") for o in obj_records[0].options}
        second = {dict(o.attrs).get("name") for o in obj_records[1].options}
        assert first == {"Ours"}
        assert second == {"Theirs"}


class TestBushwhackSearch:
    def test_finds_basic_land_and_puts_it_in_hand(self):
        game = create_game()
        p1, p2 = game.players
        bw = Bushwhack(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[bw], mana={ManaType.GREEN: 1})
        forest = _put_in_library(game, p1, Forest(name="Forest"))
        _put_in_library(game, p1, Land(name="Nonbasic Land"))
        _cast_bushwhack(game, "Search", [forest.instance_id])
        assert game.get_hand(p1).contains(forest)
        assert not p1.zones[Zone.LIBRARY].contains(forest)

    def test_search_offers_only_basics(self):
        """Option-set invariant: only basic lands are search candidates."""
        game = create_game()
        p1, p2 = game.players
        bw = Bushwhack(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[bw], mana={ManaType.GREEN: 1})
        forest = _put_in_library(game, p1, Forest(name="Forest"))
        _put_in_library(game, p1, Land(name="Nonbasic Land"))
        _cast_bushwhack(game, "Search", [forest.instance_id])
        offered = {
            dict(o.attrs).get("name")
            for r in p1.transcript.queries(DecisionKind.OBJECT)
            for o in r.options
            if o.kind is DecisionKind.OBJECT
        }
        assert offered == {"Forest"}
