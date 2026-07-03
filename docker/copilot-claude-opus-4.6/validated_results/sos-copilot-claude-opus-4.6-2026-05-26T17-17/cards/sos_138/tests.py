"""Tests for SOS 138 — Aberrant Manawurm.

A {3}{G} 2/5 Creature — Wurm with Trample.
Whenever you cast an instant or sorcery spell, this creature gets +X/+0 until
end of turn, where X is the amount of mana spent to cast that spell.
"""

from __future__ import annotations

from cards.sos.sos_138.card_impl import AberrantManawurm
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestAberrantManawurmProperties:
    """Static card data should match the SOS 138 spec."""

    def test_is_creature(self) -> None:
        card = AberrantManawurm(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = AberrantManawurm(owner=None)
        assert card.name == "Aberrant Manawurm"

    def test_mana_cost(self) -> None:
        card = AberrantManawurm(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{G}")

    def test_power_toughness(self) -> None:
        card = AberrantManawurm(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 5

    def test_has_trample(self) -> None:
        card = AberrantManawurm(owner=None)
        assert Keyword.TRAMPLE in card.keywords


class TestAberrantManawurmTriggeredAbility:
    """Whenever you cast an instant or sorcery, get +X/+0 where X = mana spent."""

    def test_gains_power_equal_to_mana_spent_on_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]

        wurm = AberrantManawurm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wurm)

        # Simulate casting a 3-mana instant
        trigger_spell = Instant(name="Test Spell", owner=p1)
        trigger_spell.mana_spent = 3

        wurm.on_spell_cast(game, trigger_spell)

        # Power should be base 2 + 3 = 5
        assert wurm.get_power() == 5
        # Toughness unchanged
        assert wurm.get_toughness() == 5

    def test_gains_power_equal_to_mana_spent_on_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]

        wurm = AberrantManawurm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wurm)

        # Simulate casting a 5-mana sorcery
        trigger_spell = Sorcery(name="Big Sorcery", owner=p1)
        trigger_spell.mana_spent = 5

        wurm.on_spell_cast(game, trigger_spell)

        assert wurm.get_power() == 7  # 2 + 5

    def test_multiple_spells_stack_bonus(self) -> None:
        game = create_game()
        p1 = game.players[0]

        wurm = AberrantManawurm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wurm)

        spell1 = Instant(name="Spell A", owner=p1)
        spell1.mana_spent = 2
        spell2 = Instant(name="Spell B", owner=p1)
        spell2.mana_spent = 3

        wurm.on_spell_cast(game, spell1)
        wurm.on_spell_cast(game, spell2)

        # Both bonuses apply in same turn: 2 + 2 + 3 = 7
        assert wurm.get_power() == 7

    def test_bonus_is_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]

        wurm = AberrantManawurm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wurm)

        spell = Instant(name="Spell", owner=p1)
        spell.mana_spent = 4

        wurm.on_spell_cast(game, spell)
        assert wurm.get_power() == 6  # 2 + 4

        # End of turn resets
        wurm.end_turn_cleanup()
        assert wurm.get_power() == 2

    def test_does_not_trigger_on_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]

        wurm = AberrantManawurm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wurm)

        creature_spell = Creature(name="Bear", owner=p1, base_power=2, base_toughness=2)
        creature_spell.mana_spent = 3
        creature_spell.card_types = {CardType.CREATURE}

        wurm.on_spell_cast(game, creature_spell)

        # Should not gain power from creature spell
        assert wurm.get_power() == 2
