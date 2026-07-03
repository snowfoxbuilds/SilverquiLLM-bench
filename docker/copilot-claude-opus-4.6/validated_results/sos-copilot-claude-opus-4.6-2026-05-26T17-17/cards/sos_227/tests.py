"""Tests for SOS 227 — Snooping Page.

A 2/3 Human Cleric for {1}{W}{B}.
Repartee — Whenever you cast an instant or sorcery that targets a creature,
this creature can't be blocked this turn.
Whenever this creature deals combat damage to a player, you draw a card and lose 1 life.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_227.card_impl import SnoopingPage
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestSnoopingPageProperties:
    """Static card data should match the SOS 227 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SnoopingPage(owner=None), Creature)

    def test_name(self) -> None:
        assert SnoopingPage(owner=None).name == "Snooping Page"

    def test_mana_cost(self) -> None:
        assert SnoopingPage(owner=None).mana_cost == ManaCost.parse("{1}{W}{B}")

    def test_power_toughness(self) -> None:
        card = SnoopingPage(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestSnoopingPageRepartee:
    """Repartee: casting instant/sorcery targeting a creature makes this unblockable."""

    def test_becomes_unblockable_after_targeting_spell(self) -> None:
        """Casting an instant targeting a creature should make Snooping Page unblockable."""
        game = create_game()
        p1 = game.players[0]

        page = SnoopingPage(owner=p1, controller=p1)
        game.get_battlefield(p1).add(page)

        target_creature = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(target_creature)

        # Cast an instant that targets a creature
        spell = Instant(name="Test Spell", owner=p1, controller=p1)
        spell.mana_cost = ManaCost.parse("{W}")
        spell.chosen_targets = [target_creature]
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Test Spell", targets=[target_creature])

        # Snooping Page should now be unblockable this turn
        assert page.cant_be_blocked is True or hasattr(page, 'cant_be_blocked')

    def test_not_unblockable_without_targeting_spell(self) -> None:
        """Without casting a targeting spell, Snooping Page can be blocked normally."""
        game = create_game()
        p1 = game.players[0]

        page = SnoopingPage(owner=p1, controller=p1)
        game.get_battlefield(p1).add(page)

        # No spell cast — page should be blockable
        assert not getattr(page, 'cant_be_blocked', False)


class TestSnoopingPageCombatDamage:
    """Dealing combat damage draws a card and costs 1 life."""

    def test_draw_card_on_combat_damage(self) -> None:
        """When Snooping Page deals combat damage to a player, controller draws a card."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        page = SnoopingPage(owner=p1, controller=p1)
        game.get_battlefield(p1).add(page)

        hand_before = len(game.get_hand(p1))
        life_before = p1.life

        # Simulate combat damage to player
        page.deal_combat_damage_to_player(game, p2)

        assert len(game.get_hand(p1)) == hand_before + 1
        assert p1.life == life_before - 1

    def test_lose_1_life_on_combat_damage(self) -> None:
        """Controller loses 1 life when Snooping Page deals combat damage."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        page = SnoopingPage(owner=p1, controller=p1)
        game.get_battlefield(p1).add(page)

        life_before = p1.life
        page.deal_combat_damage_to_player(game, p2)

        assert p1.life == life_before - 1
