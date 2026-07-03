"""Tests for The Dawning Archaic (sos_1)."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, declare_attackers, set_board_state


def _put_on_battlefield(game, player_index, card):
    """Place a card on the battlefield and register its triggers."""
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    game.players[player_index].zones[Zone.BATTLEFIELD].add(card)
    card.register_triggers(game)
    if hasattr(card, "register_replacement_effects"):
        card.register_replacement_effects(game)


class TestTheDawningArchaicProperties:
    def test_name(self) -> None:
        assert TheDawningArchaic().name == "The Dawning Archaic"

    def test_stats(self) -> None:
        c = TheDawningArchaic()
        assert c.base_power == 7
        assert c.base_toughness == 7

    def test_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic().keywords


class TestCostReduction:
    def test_reduction_counts_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        _put_on_battlefield(game, 0, archaic)
        a = Instant(name="A", mana_cost=ManaCost.parse("{1}"))
        b = Sorcery(name="B", mana_cost=ManaCost.parse("{2}"))
        c = Creature(name="C", base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[a, b, c])
        assert archaic.cost_reduction(game) == 2  # only instant + sorcery

    def test_no_reduction_empty_graveyard(self) -> None:
        game = create_game()
        archaic = TheDawningArchaic()
        _put_on_battlefield(game, 0, archaic)
        set_board_state(game, 0, graveyard=[])
        assert archaic.cost_reduction(game) == 0

    def test_cost_reduction_applied_to_casting(self) -> None:
        """Archaic costs less when instants/sorceries are in GY."""
        from engine.casting import get_cost_reduction
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        inst = Instant(name="I", mana_cost=ManaCost.parse("{1}"))
        inst.owner = p1
        inst.controller = p1
        p1.zones[Zone.GRAVEYARD].add(inst)
        reduction = get_cost_reduction(game, archaic, p1)
        # {10} generic, 1 instant in GY -> reduction of 1 (clamped to 1)
        assert reduction == 1


class TestAttackTrigger:
    def test_cast_instant_from_graveyard_on_attack(self) -> None:
        """When archaic attacks, may cast instant from GY; result goes to exile."""
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic()
        archaic.summoning_sick = False
        inst = Instant(name="MyInstant", mana_cost=ManaCost.parse("{3}"))
        _put_on_battlefield(game, 0, archaic)
        set_board_state(game, 0, graveyard=[inst])

        # Script: choose the instant from graveyard
        p1._script.appendleft(inst)

        declare_attackers(game, ["The Dawning Archaic"])

        # Resolve attack trigger + spell
        from test_utils import _resolve_top_of_stack
        _resolve_top_of_stack(game)

        # Instant went to exile (exile-instead), not graveyard
        assert game.get_exile(p1).contains(inst)
        assert not game.get_graveyard(p1).contains(inst)

    def test_empty_graveyard_trigger_fires_but_no_cast(self) -> None:
        """Trigger fires with empty GY; no cast."""
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic()
        archaic.summoning_sick = False
        _put_on_battlefield(game, 0, archaic)
        set_board_state(game, 0, graveyard=[])

        declare_attackers(game, ["The Dawning Archaic"])
        from test_utils import _resolve_top_of_stack
        _resolve_top_of_stack(game)
        assert game.get_graveyard(p1).get_all() == []

    def test_decline_cast_keeps_spell_in_graveyard(self) -> None:
        """Declining the cast (choose_card returns None) leaves spell in GY."""
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic()
        archaic.summoning_sick = False
        inst = Instant(name="Inst", mana_cost=ManaCost.parse("{2}"))
        _put_on_battlefield(game, 0, archaic)
        set_board_state(game, 0, graveyard=[inst])

        # Script None to decline
        p1._script.appendleft(None)

        declare_attackers(game, ["The Dawning Archaic"])
        from test_utils import _resolve_top_of_stack
        _resolve_top_of_stack(game)

        # Spell still in graveyard
        assert game.get_graveyard(p1).contains(inst)
