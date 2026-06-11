"""Tests for SOS 90 — Melancholic Poet.

{1}{B} Creature — Elf Bard 2/2
Repartee — Whenever you cast an instant or sorcery spell that targets a
creature, each opponent loses 1 life and you gain 1 life.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_90.card_impl import MelancholicPoet
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestMelancholicPoetProperties:
    """Static card data should match the SOS 90 spec."""

    def test_is_creature(self) -> None:
        card = MelancholicPoet(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert MelancholicPoet(owner=None).name == "Melancholic Poet"

    def test_mana_cost(self) -> None:
        assert MelancholicPoet(owner=None).mana_cost == ManaCost.parse("{1}{B}")

    def test_power_and_toughness(self) -> None:
        card = MelancholicPoet(owner=None)
        assert card.power == 2
        assert card.toughness == 2


class TestMelancholicPoetRepartee:
    """Repartee trigger: instant/sorcery targeting creature drains opponent."""

    def test_opponent_loses_life_on_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        poet = MelancholicPoet(owner=p1, controller=p1)
        game.get_battlefield(p1).add(poet)

        target = Creature(
            name="Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = Instant(name="Zap", owner=p1, controller=p1)
        spell.chosen_targets = [target]

        before_p2_life = p2.life
        before_p1_life = p1.life

        poet.on_trigger_spell_cast(game, spell)

        assert p2.life == before_p2_life - 1
        assert p1.life == before_p1_life + 1

    def test_no_trigger_when_spell_targets_player(self) -> None:
        """Spell must target a creature to trigger repartee."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        poet = MelancholicPoet(owner=p1, controller=p1)
        game.get_battlefield(p1).add(poet)

        spell = Instant(name="Bolt Face", owner=p1, controller=p1)
        spell.chosen_targets = [p2]

        before_p2_life = p2.life
        before_p1_life = p1.life

        poet.on_trigger_spell_cast(game, spell)

        assert p2.life == before_p2_life
        assert p1.life == before_p1_life

    def test_triggers_for_each_qualifying_spell(self) -> None:
        """Each qualifying spell independently triggers the drain."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        poet = MelancholicPoet(owner=p1, controller=p1)
        game.get_battlefield(p1).add(poet)

        target = Creature(
            name="Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell1 = Instant(name="Spell A", owner=p1, controller=p1)
        spell1.chosen_targets = [target]
        spell2 = Instant(name="Spell B", owner=p1, controller=p1)
        spell2.chosen_targets = [target]

        poet.on_trigger_spell_cast(game, spell1)
        poet.on_trigger_spell_cast(game, spell2)

        assert p2.life == 18  # lost 2 total
        assert p1.life == 22  # gained 2 total
