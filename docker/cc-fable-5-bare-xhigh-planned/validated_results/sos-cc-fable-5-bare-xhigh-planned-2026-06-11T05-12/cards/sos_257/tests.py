"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import AbilityError, ActivateAbility
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


class CheapTrick(Instant):
    """Probe instant {U} with a no-op resolution."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cheap Trick")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


def _vanilla(n: int) -> list[Creature]:
    return [
        Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        for i in range(n)
    ]


class TestManaAbilities:
    def test_tap_adds_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall])
        ActivateAbility(game, p1, hall, 0)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped

    def test_second_ability_pays_life_and_adds_restricted(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall])
        ActivateAbility(game, p1, hall, 1)
        assert p1.life == 19
        assert hall.is_tapped
        assert p1.mana_pool.get_restricted(ManaType.BLUE) == 1

    def test_restricted_mana_casts_instant(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        trick = CheapTrick()
        set_board_state(game, 0, battlefield=[hall], hand=[trick])
        ActivateAbility(game, p1, hall, 1)
        cast_spell(game, 0, "Cheap Trick")
        assert p1.zones[Zone.GRAVEYARD].contains(trick)
        assert p1.mana_pool.total() == 0

    def test_restricted_mana_cannot_cast_creature(self) -> None:
        game = create_game(scripts=([ManaType.GREEN], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        bear = Creature(name="Bear", mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[hall], hand=[bear])
        ActivateAbility(game, p1, hall, 1)
        assert p1.mana_pool.get_restricted(ManaType.GREEN) == 1
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Bear")


class TestAnimation:
    def _animate(self, game: Any, hall: Any) -> None:
        p1 = game.players[0]
        ActivateAbility(game, p1, hall, 2)
        priority_loop(game)

    def test_becomes_2_4_wizard_still_land(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 5})
        self._animate(game, hall)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2 and hall.toughness == 4
        assert game.players[0].mana_pool.total() == 0

    def test_cost_must_be_paid(self) -> None:
        game = create_game()
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 4})
        with pytest.raises(AbilityError):
            ActivateAbility(game, game.players[0], hall, 2)

    def test_second_activation_is_noop_when_already_creature(self) -> None:
        game = create_game(scripts=(["pass", "pass"], ["pass", "pass"]))
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 10})
        self._animate(game, hall)
        self._animate(game, hall)
        assert hall.power == 2 and hall.toughness == 4
        # The pump trigger is registered exactly once.
        assert len(game.trigger_manager.get_triggers_for_source(hall)) == 1

    def test_pump_per_instant_and_reset_at_end_of_turn(self) -> None:
        from engine.turn import run_turn

        game = create_game(deck1=_vanilla(10), deck2=_vanilla(10),
                           scripts=(["pass"], ["pass"]))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 5})
        set_board_state(game, 0, hand=[CheapTrick(), CheapTrick()])
        self._animate(game, hall)
        set_board_state(game, 0, mana={ManaType.BLUE: 2})
        cast_spell(game, 0, "Cheap Trick")
        assert hall.power == 3
        cast_spell(game, 0, "Cheap Trick")
        assert hall.power == 4
        # Finish the turn through the real turn loop; pump expires at cleanup.
        p1._script.append(None)  # decline to declare attackers
        run_turn(game)
        assert hall.power == 2
        assert CardType.CREATURE in hall.card_types  # animation persists

    def test_creature_spells_do_not_pump(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        hall = GreatHallOfTheBiblioplex()
        bear = Creature(name="Bear", mana_cost=ManaCost(generic=1),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[hall], hand=[bear],
                        mana={ManaType.COLORLESS: 6})
        self._animate(game, hall)
        cast_spell(game, 0, "Bear")
        assert hall.power == 2
