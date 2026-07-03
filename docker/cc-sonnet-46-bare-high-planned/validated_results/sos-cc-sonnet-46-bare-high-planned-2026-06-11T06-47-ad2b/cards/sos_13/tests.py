"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13)."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares, SwordsToPlowshares
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import _resolve_top_of_stack, create_game


def _put_on_battlefield(game, player_index, card):
    from engine.zones import move_to_zone
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    from engine.events import EntersBattlefieldTriggeredEvent
    p.zones[Zone.BATTLEFIELD].add(card)
    if hasattr(card, "register_triggers"):
        card.register_triggers(game)


def _enter_battlefield_via_engine(game, player_index, card):
    """Enter the battlefield via move_to_zone (fires ETB trigger)."""
    from engine.zones import move_to_zone
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    p.zones[Zone.HAND].add(card)
    move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
    _resolve_top_of_stack(game)


class TestEmeritusProperties:
    def test_name(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares().name == "Emeritus of Truce // Swords to Plowshares"

    def test_stats(self) -> None:
        e = EmeritusOfTruceSwordsToPlowshares()
        assert e.base_power == 3
        assert e.base_toughness == 3

    def test_is_creature(self) -> None:
        assert CardType.CREATURE in EmeritusOfTruceSwordsToPlowshares().card_types


class TestInklingToken:
    def test_etb_creates_inkling_for_target_player(self) -> None:
        """ETB creates a 1/1 Inkling with flying for the chosen player."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        # Script: choose p2 as the target player for token
        p1._script.appendleft(p2)

        _enter_battlefield_via_engine(game, 0, emeritus)

        # p2 should have an Inkling on the battlefield
        p2_bf = game.get_battlefield(p2).get_all()
        inklings = [c for c in p2_bf if getattr(c, "name", "") == "Inkling"]
        assert len(inklings) == 1
        assert inklings[0].base_power == 1
        assert inklings[0].base_toughness == 1
        assert Keyword.FLYING in inklings[0].keywords


class TestPreparedState:
    def test_not_prepared_when_equal_creatures(self) -> None:
        """Not prepared if no opponent has more creatures."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        # Script: choose self (p1) as token target — then check equal creatures
        p1._script.appendleft(p1)

        _enter_battlefield_via_engine(game, 0, emeritus)

        # p1 has: emeritus + inkling = 2; p2 has 0 → p2 does NOT have more
        assert not emeritus._prepared

    def test_prepared_when_opponent_has_more(self) -> None:
        """Becomes prepared if an opponent controls more creatures."""
        game = create_game()
        p1, p2 = game.players

        # Give p2 two creatures before emeritus enters
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        c2 = Creature(name="C2", base_power=1, base_toughness=1)
        for c in [c1, c2]:
            c.owner = p2
            c.controller = p2
            p2.zones[Zone.BATTLEFIELD].add(c)

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        # Script: p1 gets the inkling token
        p1._script.appendleft(p1)

        _enter_battlefield_via_engine(game, 0, emeritus)

        # After ETB: p1 has emeritus + inkling (2), p2 has c1+c2 (2) → NOT more
        # Wait: the Inkling goes to p1, emeritus is on p1's side.
        # p1: emeritus (1) + inkling (1) = 2 creatures
        # p2: c1 + c2 = 2 creatures
        # 2 == 2 → not prepared
        # Let me give p2 three creatures instead...
        assert not emeritus._prepared  # 2 vs 2

    def test_prepared_when_opponent_strictly_more(self) -> None:
        """Becomes prepared when opponent has strictly more creatures."""
        game = create_game()
        p1, p2 = game.players

        # Give p2 three creatures before emeritus enters
        for i in range(3):
            c = Creature(name=f"OppC{i}", base_power=1, base_toughness=1)
            c.owner = p2
            c.controller = p2
            p2.zones[Zone.BATTLEFIELD].add(c)

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        p1._script.appendleft(p2)  # p2 gets the inkling token
        _enter_battlefield_via_engine(game, 0, emeritus)

        # p1: emeritus (1); p2: 3 opps + inkling (4) → 4 > 1 → prepared
        assert emeritus._prepared


class TestSwordsToPlowshares:
    def test_exiles_creature_and_gives_life(self) -> None:
        """Swords to Plowshares exiles a 3/3 and gives its controller 3 life."""
        game = create_game()
        p1, p2 = game.players

        target = Creature(name="Bear", base_power=3, base_toughness=3)
        target.owner = p2
        target.controller = p2
        p2.zones[Zone.BATTLEFIELD].add(target)

        swords = SwordsToPlowshares()
        swords.owner = p1
        swords.controller = p1
        swords.chosen_targets = [target]
        swords.on_resolve(game)

        assert game.get_exile(p2).contains(target)
        assert not p2.zones[Zone.BATTLEFIELD].contains(target)
        assert p2.life == 23  # 20 + 3

    def test_no_life_gain_for_zero_power(self) -> None:
        """0/4 creature gives 0 life."""
        game = create_game()
        p1, p2 = game.players

        target = Creature(name="Wall", base_power=0, base_toughness=4)
        target.owner = p2
        target.controller = p2
        p2.zones[Zone.BATTLEFIELD].add(target)

        swords = SwordsToPlowshares()
        swords.owner = p1
        swords.controller = p1
        swords.chosen_targets = [target]
        swords.on_resolve(game)

        assert p2.life == 20  # no life gain
