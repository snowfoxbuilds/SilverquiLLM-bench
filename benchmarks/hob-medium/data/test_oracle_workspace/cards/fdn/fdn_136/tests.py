"""Reference test for FDN 136 — Angel of Finality.

Pattern 1 — targeted ETB on a creature. The target (a **player**) is chosen at
cast via a real Player Query answered by an Intent (built here by
``cast_spell(targets=...)``), captured on the stack, and read from
``chosen_targets`` in ``on_resolve``, which exiles that player's whole
graveyard. No dead test backdoors — targeting flows through real engine channels.
"""

from __future__ import annotations

from cards.fdn.fdn_136.card_impl import AngelOfFinality
from engine.card import Creature
from engine.decisions import DecisionKind
from engine.types import Keyword, ManaCost, Zone
from test_utils import cast_spell, create_game, set_board_state
from engine.types import ManaType


def _card(name="Corpse"):
    return Creature(name=name, base_power=1, base_toughness=1)


class TestAngelOfFinalityProperties:
    def test_static_data(self):
        angel = AngelOfFinality(owner=None)
        assert angel.name == "Angel of Finality"
        assert angel.mana_cost == ManaCost.parse("{3}{W}")
        assert (angel.base_power, angel.base_toughness) == (3, 4)
        assert "Angel" in angel.subtypes
        assert Keyword.FLYING in angel.keywords


class TestAngelOfFinalityETB:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        angel = AngelOfFinality(owner=p1, controller=p1)
        gy = [_card("A"), _card("B"), _card("C")]
        set_board_state(game, 0, hand=[angel], mana={ManaType.WHITE: 4})
        set_board_state(game, 1, graveyard=gy)
        return game, p1, p2, angel, gy

    def test_exiles_target_players_graveyard(self):
        game, p1, p2, angel, gy = self._setup()
        cast_spell(game, 0, "Angel of Finality", targets=[p2])
        assert len(p2.zones[Zone.GRAVEYARD].get_all()) == 0
        exile = p2.zones[Zone.EXILE].get_all()
        assert all(c in exile for c in gy)
        # The Angel itself entered the battlefield.
        assert game.get_battlefield(p1).contains(angel)

    def test_can_target_own_graveyard(self):
        game = create_game()
        p1, p2 = game.players
        angel = AngelOfFinality(owner=p1, controller=p1)
        mine = [_card("Mine1"), _card("Mine2")]
        set_board_state(game, 0, hand=[angel], graveyard=mine, mana={ManaType.WHITE: 4})
        cast_spell(game, 0, "Angel of Finality", targets=[p1])
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 0
        assert all(c in p1.zones[Zone.EXILE].get_all() for c in mine)

    def test_target_query_offers_only_players(self):
        """Option-set invariant: the ETB target query offers players, nothing else."""
        game, p1, p2, angel, gy = self._setup()
        cast_spell(game, 0, "Angel of Finality", targets=[p2])
        player_queries = [
            r for r in p1.transcript.all()
            if any(o.kind is DecisionKind.PLAYER for o in r.options)
        ]
        assert player_queries, "no player-target query was raised"
        for record in player_queries:
            assert all(o.kind is DecisionKind.PLAYER for o in record.options)
            assert len(record.options) == 2
