"""Tests for Great Hall of the Biblioplex (sos_257)."""

import pytest
from test_utils import create_game, set_board_state
from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Instant, Sorcery
from engine.types import CardType, ManaType, Zone, ManaCost
from test_utils import _resolve_top_of_stack


def _sorcery_speed(game):
    from engine.types import Phase
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0


class TestGreatHallOfTheBiblioplex:
    def test_colorless_mana_ability(self):
        """{T}: Add {C} gives 1 colorless mana."""
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        hall.owner = p1
        hall.controller = p1
        set_board_state(game, 0, battlefield=[hall])
        hall.controller = p1

        mana_abs = hall.get_mana_abilities()
        colorless_ab = mana_abs[0]

        before = p1.mana_pool.get(ManaType.COLORLESS)
        ok = colorless_ab.cost(game, hall)
        assert ok
        colorless_ab.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == before + 1
        assert hall.is_tapped

    def test_colorless_mana_requires_untap(self):
        """{T} cost fails when already tapped."""
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        hall.owner = p1
        hall.controller = p1
        hall.is_tapped = True

        mana_abs = hall.get_mana_abilities()
        ok = mana_abs[0].cost(game, hall)
        assert not ok

    def test_life_mana_ability_taps_and_costs_life(self):
        """{T}, Pay 1 life adds any color mana and reduces life."""
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        hall.owner = p1
        hall.controller = p1
        set_board_state(game, 0, battlefield=[hall], life=20)
        hall.controller = p1

        # Script: choose blue
        p1._script.appendleft(ManaType.BLUE)

        mana_abs = hall.get_mana_abilities()
        life_ab = mana_abs[1]
        life_before = p1.life
        ok = life_ab.cost(game, hall)
        assert ok
        life_ab.mana_produced(game)
        assert p1.life == life_before - 1
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert hall.is_tapped

    def test_animation_makes_creature(self):
        """{5} animates the land into a 2/4 Wizard creature."""
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        hall.owner = p1
        hall.controller = p1
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        hall.controller = p1
        _sorcery_speed(game)

        # Activate the {5} animation ability directly.
        abilities = hall.get_activated_abilities()
        anim_ab = abilities[0]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p1,
            cost=anim_ab.cost,
            effect=anim_ab.effect,
            is_mana_ability=False,
        )
        activate_ability(game, p1, instance)
        # The effect is on the stack; resolve it.
        _resolve_top_of_stack(game)

        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types  # still a land
        assert "Wizard" in hall.subtypes
        assert hall.base_power == 2
        assert hall.base_toughness == 4

    def test_animation_idempotent(self):
        """{5} has no effect if land is already a creature."""
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        hall.owner = p1
        hall.controller = p1
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 10})
        hall.controller = p1
        _sorcery_speed(game)

        abilities = hall.get_activated_abilities()
        anim_ab = abilities[0]

        def _activate():
            instance = ActivatedAbilityInstance(
                source=hall,
                controller=p1,
                cost=anim_ab.cost,
                effect=anim_ab.effect,
                is_mana_ability=False,
            )
            activate_ability(game, p1, instance)
            _resolve_top_of_stack(game)

        _activate()
        assert CardType.CREATURE in hall.card_types
        assert hall._pump_trigger_registered

        # Second activation shouldn't re-register trigger.
        _activate()
        assert hall._pump_trigger_registered
        # Only one trigger should be registered (same source).
        triggers = game.trigger_manager.get_triggers_for_source(hall)
        assert len(triggers) == 1

    def test_pump_trigger_after_animation(self):
        """After animation, casting an instant pumps the Hall +1/+0 until EOT."""
        game = create_game()
        p1 = game.players[0]

        class DoNothingInstant(Instant):
            def __init__(self):
                super().__init__(name="Zap", mana_cost=ManaCost.parse("{R}"))

        hall = GreatHallOfTheBiblioplex()
        hall.owner = p1
        hall.controller = p1
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 10, ManaType.RED: 5})
        hall.controller = p1
        _sorcery_speed(game)

        # Animate first.
        abilities = hall.get_activated_abilities()
        anim_ab = abilities[0]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p1,
            cost=anim_ab.cost,
            effect=anim_ab.effect,
            is_mana_ability=False,
        )
        activate_ability(game, p1, instance)
        _resolve_top_of_stack(game)

        # Confirm animated with base 2/4.
        game.effect_manager.apply_all(game)
        assert hall.modified_power == 2
        assert hall.modified_toughness == 4

        # Cast an instant.
        zap = DoNothingInstant()
        zap.owner = p1
        set_board_state(game, 0, hand=[zap], mana={ManaType.RED: 5})
        hall.controller = p1  # re-set after set_board_state
        _sorcery_speed(game)

        from engine.casting import cast_spell
        cast_spell(game, p1, zap)

        # Pump trigger is on the stack (fired when spell was cast).
        # Resolve the pump trigger first.
        _resolve_top_of_stack(game)  # pump trigger

        # Apply effects to see updated power.
        game.effect_manager.apply_all(game)
        assert hall.modified_power == 3  # 2 base + 1 pump
        assert hall.modified_toughness == 4
