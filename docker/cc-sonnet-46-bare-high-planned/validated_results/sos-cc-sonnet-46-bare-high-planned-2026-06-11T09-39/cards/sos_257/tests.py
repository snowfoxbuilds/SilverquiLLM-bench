"""Tests for sos_257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest
from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Instant, Sorcery, Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell, _resolve_top_of_stack


class TestGreatHallProperties:
    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex().name == "Great Hall of the Biblioplex"

    def test_is_land(self) -> None:
        hall = GreatHallOfTheBiblioplex()
        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE not in hall.card_types

    def test_has_two_mana_abilities(self) -> None:
        hall = GreatHallOfTheBiblioplex()
        assert len(hall.get_mana_abilities()) == 2

    def test_has_one_activated_ability(self) -> None:
        hall = GreatHallOfTheBiblioplex()
        assert len(hall.get_activated_abilities()) == 1


class TestColorlessManaAbility:
    def test_tap_adds_colorless(self) -> None:
        """{T}: Add {C} — taps the land and adds 1 colorless mana."""
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall])

        ability = hall.get_mana_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p0,
            cost=ability.cost,
            effect=ability.mana_produced,
            is_mana_ability=True,
        )
        activate_ability(game, p0, instance)

        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped is True

    def test_tapped_land_cannot_activate_colorless(self) -> None:
        """Tapped land refuses the {T} cost."""
        from engine.abilities import AbilityError

        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        hall.is_tapped = True
        set_board_state(game, 0, battlefield=[hall])

        ability = hall.get_mana_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p0,
            cost=ability.cost,
            effect=ability.mana_produced,
            is_mana_ability=True,
        )
        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, p0, instance)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0


class TestLifePaymentManaAbility:
    def test_tap_and_life_adds_colored_mana(self) -> None:
        """{T}, Pay 1 life: Add one mana of any color (restricted)."""
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall], life=20)

        # Script the color choice: Blue
        p0._script.append(ManaType.BLUE)

        ability = hall.get_mana_abilities()[1]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p0,
            cost=ability.cost,
            effect=ability.mana_produced,
            is_mana_ability=True,
        )
        activate_ability(game, p0, instance)

        assert p0.life == 19
        assert hall.is_tapped is True
        assert p0.mana_pool.get(ManaType.BLUE) == 1

    def test_life_payment_fails_at_one_life(self) -> None:
        """Cannot activate if player has only 1 life."""
        from engine.abilities import AbilityError

        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall], life=1)

        ability = hall.get_mana_abilities()[1]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p0,
            cost=ability.cost,
            effect=ability.mana_produced,
            is_mana_ability=True,
        )
        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, p0, instance)
        assert p0.life == 1


class TestAnimateAbility:
    def test_animate_adds_creature_type(self) -> None:
        """{5}: Land becomes a 2/4 Wizard creature (still a land)."""
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        from engine.game_state import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ability = hall.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p0,
            cost=ability.cost,
            effect=ability.effect,
            is_mana_ability=False,
        )
        activate_ability(game, p0, instance)
        # Resolve the ability from the stack
        _resolve_top_of_stack(game)

        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert hall.modified_power == 2
        assert hall.modified_toughness == 4
        assert "Wizard" in hall.subtypes

    def test_animate_idempotent_when_already_creature(self) -> None:
        """{5} does nothing if already a creature (cost check gates it)."""
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        hall.card_types.add(CardType.CREATURE)  # pre-animate
        set_board_state(game, 0, battlefield=[hall])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        from engine.game_state import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ability = hall.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p0,
            cost=ability.cost,
            effect=ability.effect,
            is_mana_ability=False,
        )
        # The cost should return False when already a creature
        result = ability.cost(game, hall)
        assert result is False

    def test_animate_deducts_five_mana(self) -> None:
        """{5} costs exactly 5 generic mana."""
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        from engine.game_state import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ability = hall.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p0,
            cost=ability.cost,
            effect=ability.effect,
            is_mana_ability=False,
        )
        activate_ability(game, p0, instance)
        _resolve_top_of_stack(game)

        # All 5 mana spent
        assert p0.mana_pool.total() == 0


class TestAnimatedPumpTrigger:
    def test_pump_on_instant_cast(self) -> None:
        """After animation, casting an instant gives +1/+0 until EOT."""
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        from engine.game_state import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        # Animate
        ability = hall.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p0,
            cost=ability.cost,
            effect=ability.effect,
            is_mana_ability=False,
        )
        activate_ability(game, p0, instance)
        _resolve_top_of_stack(game)

        assert hall.modified_power == 2

        # Cast an instant — fires E1 → pump trigger → +1/+0
        zap = Instant(name="Zap", mana_cost=ManaCost(generic=0))
        set_board_state(game, 0, hand=[zap])

        cast_spell(game, 0, "Zap")

        assert hall.modified_power == 3

    def test_pump_does_not_fire_for_opponent_spell(self) -> None:
        """Pump trigger is gated on controller's spells only."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        from engine.game_state import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        # Animate Hall
        ability = hall.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p0,
            cost=ability.cost,
            effect=ability.effect,
            is_mana_ability=False,
        )
        activate_ability(game, p0, instance)
        _resolve_top_of_stack(game)

        assert hall.modified_power == 2

        # Opponent casts an instant — should NOT pump Hall
        zap = Instant(name="Zap", mana_cost=ManaCost(generic=0))
        set_board_state(game, 1, hand=[zap])
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        from engine.casting import cast_spell as _engine_cast
        _engine_cast(game, p1, zap)
        _resolve_top_of_stack(game)

        assert hall.modified_power == 2
