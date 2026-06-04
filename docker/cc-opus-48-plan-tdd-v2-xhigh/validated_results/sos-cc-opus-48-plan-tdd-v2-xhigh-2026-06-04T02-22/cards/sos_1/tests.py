"""Tests for SOS 1 — The Dawning Archaic (cost reduction + attack free-cast)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, cast_spell, declare_attackers
from test_utils import _resolve_top_of_stack


class LifeGainBolt(Instant):
    """Test-only instant: controller gains 3 life on resolve (no targets)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Life Gain Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


class TestProperties:
    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name_cost_pt(self) -> None:
        c = TheDawningArchaic(owner=None)
        assert c.name == "The Dawning Archaic"
        assert c.mana_cost == ManaCost.parse("{10}")
        assert c.base_power == 7
        assert c.base_toughness == 7

    def test_keywords_and_types(self) -> None:
        c = TheDawningArchaic(owner=None)
        assert Keyword.REACH in c.keywords
        assert "Avatar" in c.subtypes
        assert Supertype.LEGENDARY in c.supertypes


class TestCostReduction:
    def test_counts_instants_and_sorceries_in_graveyard(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bolt1 = LifeGainBolt(owner=p1, controller=p1)
        bolt2 = LifeGainBolt(owner=p1, controller=p1)
        creature = Creature(name="Bear", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        set_board_state(game, 0, hand=[archaic],
                        graveyard=[bolt1, bolt2, creature])
        assert archaic.cost_reduction(game) == 2

    def test_empty_graveyard_no_reduction(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[archaic], graveyard=[])
        assert archaic.cost_reduction(game) == 0

    def test_real_cast_with_reduced_cost(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        gy = [LifeGainBolt(owner=p1, controller=p1) for _ in range(4)]
        set_board_state(game, 0, hand=[archaic], graveyard=gy,
                        mana={ManaType.COLORLESS: 6})

        cast_spell(game, 0, "The Dawning Archaic")

        assert archaic in p1.zones[Zone.BATTLEFIELD].get_all()
        assert p1.mana_pool.total() == 0


class TestAttackTrigger:
    def _board(self, *, accept: bool):
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bolt = LifeGainBolt(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bolt], life=20)
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        if accept:
            p1._script.extend([True, bolt])
        else:
            p1._script.extend([False])
        return game, p1, p2, archaic, bolt

    def test_attack_casts_spell_and_exiles_it(self) -> None:
        game, p1, p2, archaic, bolt = self._board(accept=True)

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_top_of_stack(game)

        assert p1.life == 23  # bolt resolved
        assert bolt in p1.zones[Zone.EXILE].get_all()
        assert bolt not in p1.zones[Zone.GRAVEYARD].get_all()

    def test_declining_does_not_cast(self) -> None:
        game, p1, p2, archaic, bolt = self._board(accept=False)

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_top_of_stack(game)

        assert p1.life == 20
        assert bolt in p1.zones[Zone.GRAVEYARD].get_all()
        assert bolt not in p1.zones[Zone.EXILE].get_all()
