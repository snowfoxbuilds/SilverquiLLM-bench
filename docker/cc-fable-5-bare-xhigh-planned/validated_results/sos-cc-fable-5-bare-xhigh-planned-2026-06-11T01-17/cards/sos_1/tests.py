"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, declare_attackers, set_board_state, cast_spell


class ProbeInstant(Instant):
    """Test-only instant: controller gains 3 life on resolve."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Probe Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _archaic_attacking(game) -> TheDawningArchaic:
    """Place a battle-ready Archaic on p1's battlefield with live triggers."""
    archaic = TheDawningArchaic(owner=None)
    set_board_state(game, 0, battlefield=[archaic])
    archaic.summoning_sick = False
    archaic.register_triggers(game)
    return archaic


class TestTheDawningArchaicProperties:
    def test_static_data(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert Keyword.REACH in card.keywords
        assert card.base_power == 7 and card.base_toughness == 7
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes


class TestTheDawningArchaicCostReduction:
    def test_three_spells_in_graveyard_reduce_to_seven(self) -> None:
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        yard = [ProbeInstant(), ProbeInstant(), ProbeInstant()]
        set_board_state(game, 0, hand=[archaic], graveyard=yard,
                        mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(game.players[0]).contains(archaic)

    def test_reduction_clamps_at_zero(self) -> None:
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        yard = [ProbeInstant() for _ in range(12)]
        set_board_state(game, 0, hand=[archaic], graveyard=yard, mana={})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(game.players[0]).contains(archaic)

    def test_creatures_in_graveyard_do_not_reduce(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bears = [Creature(name="Bear", base_power=2, base_toughness=2)
                 for _ in range(5)]
        set_board_state(game, 0, graveyard=bears)
        assert archaic.cost_reduction(game) == 0


class TestTheDawningArchaicAttackTrigger:
    def test_attack_casts_lone_spell_and_exiles_it(self) -> None:
        """Single legal target is auto-selected, cast for free, exiled."""
        game = create_game(scripts=(["pass", "pass"], ["pass", "pass"]))
        p1 = game.players[0]
        archaic = _archaic_attacking(game)
        probe = ProbeInstant()
        set_board_state(game, 0, graveyard=[probe])
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert p1.life == 23  # probe resolved
        assert game.get_exile(p1).contains(probe)
        assert not game.get_graveyard(p1).contains(probe)

    def test_attack_with_empty_graveyard_is_noop(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1 = game.players[0]
        archaic = _archaic_attacking(game)
        set_board_state(game, 0, graveyard=[])
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert p1.life == 20
        assert len(game.get_exile(p1)) == 0

    def test_attack_prompts_among_multiple_and_may_decline(self) -> None:
        """With two candidates the controller picks one; the other stays."""
        probe_a = ProbeInstant()
        probe_b = ProbeInstant()
        game = create_game(
            scripts=(["pass", probe_b, "pass"], ["pass", "pass"]))
        p1 = game.players[0]
        archaic = _archaic_attacking(game)
        set_board_state(game, 0, graveyard=[probe_a, probe_b])
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert p1.life == 23
        assert game.get_exile(p1).contains(probe_b)
        assert game.get_graveyard(p1).contains(probe_a)

    def test_attack_decline_with_none(self) -> None:
        probe_a = ProbeInstant()
        probe_b = ProbeInstant()
        game = create_game(scripts=(["pass", None, "pass"], ["pass", "pass"]))
        p1 = game.players[0]
        archaic = _archaic_attacking(game)
        set_board_state(game, 0, graveyard=[probe_a, probe_b])
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert p1.life == 20
        assert len(game.get_exile(p1)) == 0
        assert len(game.get_graveyard(p1)) == 2
