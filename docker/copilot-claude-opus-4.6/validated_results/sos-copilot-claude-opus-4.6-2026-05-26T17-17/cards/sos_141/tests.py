"""Tests for SOS 141 — Burrog Barrage.

Burrog Barrage is a {1}{G} Instant:
  Target creature you control gets +1/+0 until end of turn if you've cast
  another instant or sorcery spell this turn. Then it deals damage equal to
  its power to up to one target creature an opponent controls.
"""

from __future__ import annotations

from cards.sos.sos_141.card_impl import BurrogBarrage
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestBurrogBarrageProperties:
    """Static card data should match spec."""

    def test_is_instant(self) -> None:
        assert isinstance(BurrogBarrage(owner=None), Instant)

    def test_name(self) -> None:
        assert BurrogBarrage(owner=None).name == "Burrog Barrage"

    def test_mana_cost(self) -> None:
        assert BurrogBarrage(owner=None).mana_cost == ManaCost.parse("{1}{G}")


class TestBurrogBarrageResolution:
    """Resolution behavior: conditional pump then fight-like damage."""

    def _setup_game(self):
        """Set up game with a creature on each side."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        attacker = Creature(
            name="Test Bear",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        attacker.card_types = {CardType.CREATURE}

        target = Creature(
            name="Enemy Creature",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=4,
        )
        target.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[target])
        return game, p1, p2, attacker, target

    def test_no_prior_spell_no_pump(self) -> None:
        """Without a prior instant/sorcery this turn, no +1/+0 bonus."""
        game, p1, p2, attacker, target = self._setup_game()

        spell = BurrogBarrage(owner=p1, controller=p1)
        spell.chosen_targets = [attacker, target]
        spell.on_resolve(game)

        # Damage dealt should equal base power (3), no pump
        assert target.damage_dealt_to_it >= 3
        # No pump applied
        assert attacker.get_power() == 3

    def test_prior_spell_grants_pump(self) -> None:
        """With a prior instant/sorcery this turn, creature gets +1/+0."""
        game, p1, p2, attacker, target = self._setup_game()

        # Mark that another instant/sorcery was cast this turn
        if not hasattr(game, 'spells_cast_this_turn'):
            game.spells_cast_this_turn = []
        game.spells_cast_this_turn.append(
            Instant(name="Some Spell", owner=p1, controller=p1)
        )

        spell = BurrogBarrage(owner=p1, controller=p1)
        spell.chosen_targets = [attacker, target]
        spell.on_resolve(game)

        # With pump, power should be 4 and damage should be 4
        assert target.damage_dealt_to_it >= 4

    def test_no_opponent_target_still_pumps(self) -> None:
        """'up to one' means zero targets for opponent creature is legal."""
        game = create_game()
        p1 = game.players[0]

        attacker = Creature(
            name="Test Bear",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        attacker.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[attacker])

        # Mark prior spell cast
        if not hasattr(game, 'spells_cast_this_turn'):
            game.spells_cast_this_turn = []
        game.spells_cast_this_turn.append(
            Instant(name="Some Spell", owner=p1, controller=p1)
        )

        spell = BurrogBarrage(owner=p1, controller=p1)
        # Only one target (your creature), no opponent target
        spell.chosen_targets = [attacker]
        spell.on_resolve(game)

        # Pump still applies
        assert attacker.get_power() == 4

    def test_damage_equals_power_after_pump(self) -> None:
        """Damage is calculated after pump is applied."""
        game, p1, p2, attacker, target = self._setup_game()

        # Mark prior spell
        if not hasattr(game, 'spells_cast_this_turn'):
            game.spells_cast_this_turn = []
        game.spells_cast_this_turn.append(
            Instant(name="Prior Spell", owner=p1, controller=p1)
        )

        spell = BurrogBarrage(owner=p1, controller=p1)
        spell.chosen_targets = [attacker, target]
        spell.on_resolve(game)

        # Power should be 4 (3 base + 1 pump), damage dealt should equal that
        assert target.damage_dealt_to_it == 4
