"""Tests for The Dawning Archaic (sos_1)."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant, Sorcery
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, declare_attackers, set_board_state


class _GainLifeInstant(Instant):
    """A no-target instant that gains its controller 2 life on resolve."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Gainer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 2


def _drain_stack(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


class TestProperties:
    def test_static(self):
        c = TheDawningArchaic(owner=None)
        assert c.name == "The Dawning Archaic"
        assert c.mana_cost == ManaCost.parse("{10}")
        assert c.base_power == 7 and c.base_toughness == 7
        assert Keyword.REACH in c.keywords
        assert CardType.CREATURE in c.card_types


class TestCostReduction:
    def test_reduced_by_graveyard_count(self):
        """3 instant/sorcery in gy → {10} costs 7; 7 colorless mana casts it."""
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        gy = [Instant(name=f"I{i}", mana_cost=ManaCost.parse("{1}")) for i in range(2)]
        gy.append(Sorcery(name="S", mana_cost=ManaCost.parse("{1}")))
        set_board_state(game, 0, hand=[archaic], graveyard=gy,
                        mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(game.players[0]).contains(archaic)

    def test_not_reduced_below_zero_and_empty_gy(self):
        """Empty graveyard → no reduction; 9 mana cannot pay {10}."""
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        set_board_state(game, 0, hand=[archaic], graveyard=[],
                        mana={ManaType.COLORLESS: 9})
        import pytest
        with pytest.raises(Exception):
            cast_spell(game, 0, "The Dawning Archaic")
        assert not game.get_battlefield(game.players[0]).contains(archaic)

    def test_reduction_does_not_count_creatures(self):
        """Creature cards in gy do not reduce the cost."""
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        from engine.card import Creature
        gy = [Creature(name="C", base_power=1, base_toughness=1)]
        set_board_state(game, 0, hand=[archaic], graveyard=gy,
                        mana={ManaType.COLORLESS: 9})
        import pytest
        with pytest.raises(Exception):
            cast_spell(game, 0, "The Dawning Archaic")


class TestAttackTrigger:
    def test_casts_single_gy_instant_free_and_exiles(self):
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        gainer = _GainLifeInstant(owner=None)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[gainer])
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        p0 = game.players[0]
        life_before = p0.life

        declare_attackers(game, ["The Dawning Archaic"])
        _drain_stack(game)

        # The free spell resolved (gained 2 life)...
        assert p0.life == life_before + 2
        # ...and was exiled instead of going to the graveyard.
        assert game.get_exile(p0).contains(gainer)
        assert not game.get_graveyard(p0).contains(gainer)

    def test_no_instant_in_graveyard_does_nothing(self):
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        from engine.card import Creature
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[junk])
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        declare_attackers(game, ["The Dawning Archaic"])
        _drain_stack(game)
        # Nothing cast; junk untouched.
        assert game.get_graveyard(game.players[0]).contains(junk)

    def test_decline_with_multiple_targets(self):
        """With 2+ legal targets, the controller may decline (choose None)."""
        game = create_game(scripts=([None], []))
        archaic = TheDawningArchaic(owner=None)
        i1 = _GainLifeInstant(name="A", owner=None)
        i2 = _GainLifeInstant(name="B", owner=None)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[i1, i2])
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        p0 = game.players[0]
        declare_attackers(game, ["The Dawning Archaic"])
        _drain_stack(game)
        # Declined → both still in graveyard, no life gained.
        assert game.get_graveyard(p0).contains(i1)
        assert game.get_graveyard(p0).contains(i2)
        assert p0.life == 20
