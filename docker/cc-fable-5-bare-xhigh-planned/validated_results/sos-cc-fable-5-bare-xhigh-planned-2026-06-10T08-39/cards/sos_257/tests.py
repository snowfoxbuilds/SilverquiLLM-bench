"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Zone
from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _activate_mana(game, player, land, index: int) -> None:
    """Activate a printed mana ability by index (the engine's path)."""
    ability = land.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ability.cost,
        effect=ability.mana_produced,
        is_mana_ability=True,
    )
    activate_ability(game, player, inst)


def _activate(game, player, card, index: int) -> None:
    """Activate a printed (non-mana) activated ability by index and resolve."""
    ability = card.get_activated_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=card,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        is_mana_ability=False,
    )
    activate_ability(game, player, inst)
    priority_loop(game)


class TestManaAbilities:
    def test_tap_for_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall])
        _activate_mana(game, p1, hall, 0)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped

    def test_restricted_mana_pays_for_instant(self) -> None:
        """Second ability: pay 1 life, add restricted colored mana; it can
        cast an instant."""
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[hall], hand=[spell])
        _activate_mana(game, p1, hall, 1)
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        cast_spell(game, 0, "Probe")
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_restricted_mana_cannot_pay_for_creature(self) -> None:
        game = create_game(scripts=([ManaType.GREEN], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{G}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[hall], hand=[bear])
        _activate_mana(game, p1, hall, 1)
        assert p1.mana_pool.get(ManaType.GREEN) == 1
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Bear")


class TestAnimation:
    def test_five_mana_animates_to_2_4_wizard_still_a_land(self) -> None:
        game = create_game(scripts=(["pass"] * 2, ["pass"] * 2))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 5})
        _activate(game, p1, hall, 0)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_animated_pump_per_instant_or_sorcery(self) -> None:
        """Each instant/sorcery you cast gives +1/+0 until end of turn."""
        game = create_game(scripts=(["pass"] * 2, ["pass"] * 2))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        s1 = Instant(name="One")
        s2 = Instant(name="Two")
        set_board_state(game, 0, battlefield=[hall], hand=[s1, s2],
                        mana={ManaType.COLORLESS: 5})
        _activate(game, p1, hall, 0)
        cast_spell(game, 0, "One")
        assert hall.power == 3
        cast_spell(game, 0, "Two")
        assert hall.power == 4
        assert hall.toughness == 4  # +1/+0 only

    def test_activation_while_already_creature_does_nothing(self) -> None:
        """Second activation doesn't re-animate or double the pump."""
        game = create_game(scripts=(["pass"] * 4, ["pass"] * 4))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        spell = Instant(name="One")
        set_board_state(game, 0, battlefield=[hall], hand=[spell],
                        mana={ManaType.COLORLESS: 10})
        _activate(game, p1, hall, 0)
        _activate(game, p1, hall, 0)
        cast_spell(game, 0, "One")
        assert hall.power == 3  # single pump trigger registered

    def test_unanimated_land_does_not_pump(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        spell = Instant(name="One")
        set_board_state(game, 0, battlefield=[hall], hand=[spell])
        cast_spell(game, 0, "One")
        assert CardType.CREATURE not in hall.card_types
        assert hall.power == 0  # no creature stats
