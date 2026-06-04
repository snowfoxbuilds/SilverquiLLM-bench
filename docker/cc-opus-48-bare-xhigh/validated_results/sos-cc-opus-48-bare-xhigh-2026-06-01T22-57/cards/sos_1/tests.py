"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.casting import resolve_top
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestProperties:
    def test_basics(self) -> None:
        c = TheDawningArchaic(owner=None)
        assert c.name == "The Dawning Archaic"
        assert c.mana_cost == ManaCost.parse("{10}")
        assert c.base_power == 7 and c.base_toughness == 7
        assert Supertype.LEGENDARY in c.supertypes
        assert "Avatar" in c.subtypes
        assert c.keywords & Keyword.REACH


class TestCostReduction:
    def test_reduces_per_instant_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        gy = [
            Instant(name="I1", mana_cost=ManaCost.parse("{R}")),
            Sorcery(name="S1", mana_cost=ManaCost.parse("{2}")),
            Creature(name="Bear", base_power=2, base_toughness=2),
        ]
        set_board_state(game, 0, graveyard=gy)
        archaic.controller = p1
        # Only the instant and sorcery count → {2} less.
        assert archaic.cost_reduction(game) == 2

    def test_no_instants_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[])
        archaic.controller = p1
        assert archaic.cost_reduction(game) == 0


class TestAttackTrigger:
    def test_free_casts_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bolt])
        archaic.register_triggers(game)
        p1._script.extend([True, bolt])  # yes, choose the instant
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        )
        resolve_top(game)  # resolve the attack trigger → free-cast the spell
        # Bolt left the graveyard (now on the stack).
        assert bolt not in p1.zones[Zone.GRAVEYARD].get_all()
        assert not game.stack.is_empty()
        # Casting from graveyard sets the replace-graveyard-with-exile flag.
        assert bolt._replace_graveyard_with_exile is True

    def test_decline_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bolt])
        archaic.register_triggers(game)
        p1._script.extend([False])  # decline
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        )
        resolve_top(game)
        assert bolt in p1.zones[Zone.GRAVEYARD].get_all()
        assert game.stack.is_empty()

    def test_no_trigger_for_other_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bolt])
        archaic.register_triggers(game)
        other = Creature(name="Other", base_power=2, base_toughness=2)
        other.controller = p1
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=other, attacker=other)
        )
        assert game.stack.is_empty()
