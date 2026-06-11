"""Tests for Lorehold, the Historian (sos_201)."""

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class LifeGainInstant(Instant):
    def __init__(self, name="LG", **kw):
        kw.setdefault("mana_cost", ManaCost.parse("{3}"))
        super().__init__(name=name, **kw)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 1


def _setup(library_top=None):
    """Lorehold on p0's battlefield with triggers registered."""
    game = create_game()
    p0 = game.players[0]
    lh = LoreholdTheHistorian()
    set_board_state(game, 0, battlefield=[lh])
    lh.register_triggers(game)
    if library_top is not None:
        lib = p0.zones[Zone.LIBRARY]
        for c in library_top:
            c.owner = c.controller = p0
            lib.add(c)  # last added = top
    return game, p0, lh


class TestLoreholdTheHistorian:
    def test_keywords(self):
        lh = LoreholdTheHistorian()
        assert Keyword.FLYING in lh.keywords
        assert Keyword.HASTE in lh.keywords

    def test_miracle_first_draw_instant(self):
        trick = LifeGainInstant("Drawn Trick")
        game, p0, _ = _setup(library_top=[trick])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p0)
        # trigger on stack: pass, yes to miracle, then pass the cast spell
        p0._script.extend(["pass", True, "pass"])
        game.players[1]._script.extend(["pass", "pass"])
        priority_loop(game)
        assert p0.life == 21                     # spell resolved
        assert p0.mana_pool.total() == 0         # {2} miracle cost paid
        assert game.get_graveyard(p0).contains(trick)

    def test_no_miracle_on_second_draw(self):
        c1 = Creature(name="Bear1", base_power=2, base_toughness=2)
        trick = LifeGainInstant("Late Trick")
        game, p0, _ = _setup(library_top=[trick, c1])  # top: c1 then trick
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p0)   # first draw: creature, no trigger
        draw_card(game, p0)   # second draw: instant but not first
        assert game.stack.is_empty()
        assert game.get_hand(p0).contains(trick)

    def test_no_miracle_for_noninstant(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, _ = _setup(library_top=[bear])
        draw_card(game, p0)
        assert game.stack.is_empty()

    def test_miracle_declined_card_stays_in_hand(self):
        trick = LifeGainInstant("Kept Trick")
        game, p0, _ = _setup(library_top=[trick])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p0)
        p0._script.extend(["pass", False])
        game.players[1]._script.extend(["pass"])
        priority_loop(game)
        assert game.get_hand(p0).contains(trick)
        assert p0.life == 20

    def test_opponent_upkeep_loot(self):
        from engine.turn import run_turn
        game, p0, _ = _setup()
        p1 = game.players[1]
        # p0's hand: a card to discard; p0's library: a creature to draw.
        to_discard = LifeGainInstant("Chaff")
        to_draw = Creature(name="Fresh Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[to_discard])
        lib0 = p0.zones[Zone.LIBRARY]
        to_draw.owner = to_draw.controller = p0
        lib0.add(to_draw)
        # Opponent's library so their draw step works.
        deck1 = Creature(name="OppCard", base_power=1, base_toughness=1)
        deck1.owner = deck1.controller = p1
        p1.zones[Zone.LIBRARY].add(deck1)
        # Run p1's turn: at their upkeep the loot trigger fires.
        game.active_player_index = 1
        game.priority_player_index = 1
        p1._script.extend(["pass"])
        p0._script.extend(["pass", to_discard])
        run_turn(game)
        assert game.get_graveyard(p0).contains(to_discard)
        assert game.get_hand(p0).contains(to_draw)

    def test_no_loot_on_own_upkeep(self):
        from engine.turn import run_turn
        game, p0, _ = _setup()
        p1 = game.players[1]
        set_board_state(game, 0, hand=[LifeGainInstant("Chaff")])
        # give both players library cards for draw steps
        for p in game.players:
            c = Creature(name="Filler", base_power=1, base_toughness=1)
            c.owner = c.controller = p
            p.zones[Zone.LIBRARY].add(c)
        p0._script.append([])  # declare no attackers
        run_turn(game)  # p0's own turn — no loot prompt expected
        assert len(game.get_graveyard(p0)) == 0
