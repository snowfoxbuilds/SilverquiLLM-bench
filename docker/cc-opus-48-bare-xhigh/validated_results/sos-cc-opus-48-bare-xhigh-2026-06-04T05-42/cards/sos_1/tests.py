"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import _resolve_top_of_stack, create_game, set_board_state


def _archaic(p):
    c = TheDawningArchaic(owner=p, controller=p)
    return c


class TestProperties:
    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_power_toughness(self) -> None:
        c = TheDawningArchaic(owner=None)
        assert (c.base_power, c.base_toughness) == (7, 7)

    def test_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_legendary_avatar(self) -> None:
        c = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in c.supertypes
        assert "Avatar" in c.subtypes


class TestCostReduction:
    def test_no_reduction_empty_graveyard(self) -> None:
        game = create_game()
        c = _archaic(game.players[0])
        assert c.cost_reduction(game) == 0

    def test_counts_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        gy = [
            Instant(name="I1"),
            Sorcery(name="S1"),
            Instant(name="I2"),
            Creature(name="Bear", base_power=2, base_toughness=2),
        ]
        set_board_state(game, 0, graveyard=gy)
        c = _archaic(p1)
        # 2 instants + 1 sorcery = 3; creature does not count.
        assert c.cost_reduction(game) == 3


class TestAttackTrigger:
    def test_free_cast_from_graveyard_is_exiled(self) -> None:
        # choose_yes_no -> True, choose_card -> the graveyard instant.
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        game = create_game(scripts=([True, bolt], []))
        p1 = game.players[0]
        archaic = _archaic(p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bolt])
        archaic.register_triggers(game)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        )
        _resolve_top_of_stack(game)

        # Bolt was cast from the graveyard and exiled (not returned to GY).
        assert not p1.zones[Zone.GRAVEYARD].contains(bolt)
        assert p1.zones[Zone.EXILE].contains(bolt)

    def test_decline_leaves_graveyard_untouched(self) -> None:
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        archaic = _archaic(p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bolt])
        archaic.register_triggers(game)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        )
        _resolve_top_of_stack(game)
        assert p1.zones[Zone.GRAVEYARD].contains(bolt)

    def test_trigger_ignores_other_attackers(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        archaic = _archaic(p1)
        other = Creature(name="Other", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[archaic, other])
        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=other, attacker=other)
        )
        assert game.stack.is_empty()
