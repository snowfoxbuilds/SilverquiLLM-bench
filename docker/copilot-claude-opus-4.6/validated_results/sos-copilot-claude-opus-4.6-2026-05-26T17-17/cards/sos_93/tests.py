"""Tests for SOS 93 — Postmortem Professor."""

from __future__ import annotations

import pytest

from cards.sos.sos_93.card_impl import PostmortemProfessor
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell, declare_attackers


class TestPostmortemProfessorProperties:
    """Static card data should match the SOS 93 spec."""

    def test_is_creature(self) -> None:
        card = PostmortemProfessor(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert PostmortemProfessor(owner=None).name == "Postmortem Professor"

    def test_mana_cost(self) -> None:
        assert PostmortemProfessor(owner=None).mana_cost == ManaCost.parse("{1}{B}")

    def test_power_toughness(self) -> None:
        card = PostmortemProfessor(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = PostmortemProfessor(owner=None)
        assert "Zombie" in card.subtypes
        assert "Warlock" in card.subtypes


class TestPostmortemProfessorCantBlock:
    """This creature can't block."""

    def test_cant_block(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        prof = PostmortemProfessor(owner=p2, controller=p2)
        attacker = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        attacker.summoning_sick = False
        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[prof])

        # Professor cannot be declared as a blocker
        assert prof.can_block(game) is False


class TestPostmortemProfessorAttackTrigger:
    """Whenever this creature attacks, each opponent loses 1 life and you gain 1 life."""

    def test_attack_drains_opponent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        prof = PostmortemProfessor(owner=p1, controller=p1)
        prof.summoning_sick = False
        set_board_state(game, 0, battlefield=[prof])

        life_p1_before = p1.life
        life_p2_before = p2.life

        declare_attackers(game, ["Postmortem Professor"])

        assert p2.life == life_p2_before - 1
        assert p1.life == life_p1_before + 1


class TestPostmortemProfessorGraveyardAbility:
    """Pay {1}{B}, exile an instant/sorcery from graveyard: return from graveyard to battlefield."""

    def test_returns_from_graveyard_with_instant_exiled(self) -> None:
        game = create_game()
        p1 = game.players[0]

        prof = PostmortemProfessor(owner=p1, controller=p1)
        spell_card = Instant(name="Dark Ritual", owner=p1, controller=p1)

        set_board_state(game, 0, graveyard=[prof, spell_card],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        # Activate the graveyard ability
        prof.activate_ability(game, 0, costs_paid=True, targets=[spell_card])

        # Professor should be on battlefield
        battlefield = game.get_battlefield(p1)
        assert any(c.name == "Postmortem Professor" for c in battlefield)

        # The instant should be exiled
        graveyard = game.get_graveyard(p1)
        assert not any(c.name == "Dark Ritual" for c in graveyard)

    def test_cannot_activate_without_instant_or_sorcery_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        prof = PostmortemProfessor(owner=p1, controller=p1)
        # Only creatures in graveyard, no instants or sorceries
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)

        set_board_state(game, 0, graveyard=[prof, bear],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        # Should not be able to activate without a valid exile target
        abilities = prof.get_activated_abilities(game)
        # Either no abilities available or they should be unactivatable
        can_activate = any(a.can_activate(game) for a in abilities) if abilities else False
        assert can_activate is False
