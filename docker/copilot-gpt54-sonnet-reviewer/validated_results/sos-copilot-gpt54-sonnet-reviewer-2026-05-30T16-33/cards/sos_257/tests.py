"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _activate_mana_ability(
    game,
    player,
    hall: GreatHallOfTheBiblioplex,
    index: int,
) -> None:
    ability = hall.get_mana_abilities()[index]
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=hall,
            controller=player,
            cost=ability.cost,
            effect=ability.mana_produced,
            is_mana_ability=True,
            description=ability.description,
        ),
    )


def _animate_hall(game, player, hall: GreatHallOfTheBiblioplex) -> None:
    ability = hall.get_activated_abilities()[0]
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=hall,
            controller=player,
            cost=ability.cost,
            effect=ability.effect,
            description=ability.description,
        ),
    )
    stack_obj = game.stack.pop()
    stack_obj.on_resolve(game)
    game.effect_manager.apply_all(game)


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data should match the SOS 257 spec."""

    def test_name_type_rules_text_and_land_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert card.name == "Great Hall of the Biblioplex"
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types
        assert card.mana_cost == ManaCost()
        assert card.rules_text == (
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            "creature with \"Whenever you cast an instant or sorcery spell, "
            "this creature gets +1/+0 until end of turn.\" It's still a land."
        )
        assert len(card.get_mana_abilities()) == 2
        assert len(card.get_activated_abilities()) == 1


class TestGreatHallOfTheBiblioplexManaAbilities:
    """The land should produce mana per its two tap abilities."""

    def test_colorless_mana_ability_taps_the_land_and_adds_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])

        _activate_mana_ability(game, p1, hall, 0)

        assert hall.is_tapped is True
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_any_color_mana_ability_costs_one_life_and_adds_the_chosen_color(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], life=20)

        _activate_mana_ability(game, p1, hall, 1)

        assert hall.is_tapped is True
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1

    def test_restricted_mana_can_be_spent_to_cast_an_instant(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Quick Study", mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[hall], hand=[spell])

        _activate_mana_ability(game, p1, hall, 1)
        cast_spell(game, 0, "Quick Study")

        assert game.get_graveyard(p1).contains(spell)
        assert not game.get_hand(p1).contains(spell)

    def test_restricted_mana_cannot_be_spent_to_cast_a_creature_spell(self) -> None:
        game = create_game(scripts=([ManaType.GREEN], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature = Creature(
            name="Campus Bear",
            mana_cost=ManaCost.parse("{G}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[hall], hand=[creature])

        _activate_mana_ability(game, p1, hall, 1)

        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Campus Bear")

    def test_cannot_activate_a_tap_mana_ability_twice_in_the_same_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])

        _activate_mana_ability(game, p1, hall, 0)

        with pytest.raises(AbilityError):
            _activate_mana_ability(game, p1, hall, 1)


class TestGreatHallOfTheBiblioplexAnimation:
    """The five-mana activation should animate the land and grant a spell-cast trigger."""

    def test_animation_makes_it_a_two_four_wizard_creature_thats_still_a_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _animate_hall(game, p1, hall)

        assert p1.mana_pool.total() == 0
        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4

    def test_second_animation_activation_is_a_noop_when_the_land_is_already_a_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 10},
        )

        _animate_hall(game, p1, hall)
        _animate_hall(game, p1, hall)

        assert hall.power == 2
        assert hall.toughness == 4
        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types

    def test_unanimated_land_does_not_trigger_when_you_cast_an_instant_or_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Lecture Notes", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[hall])
        hall.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell,
                player=p1,
                card=spell,
                controller=p1,
            ),
        )

        assert game.stack.is_empty()

    def test_casting_your_instant_or_sorcery_pushes_one_trigger_for_the_animated_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Pop Quiz", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _animate_hall(game, p1, hall)
        hall.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell,
                player=p1,
                card=spell,
                controller=p1,
            ),
        )

        assert len(game.stack) == 1

    def test_casting_your_instant_or_sorcery_gives_the_animated_land_plus_one_zero_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _animate_hall(game, p1, hall)
        hall.register_triggers(game)

        spell = Instant(name="Pop Quiz", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell,
                player=p1,
                card=spell,
                controller=p1,
            ),
        )
        trigger = game.stack.pop()
        trigger.on_resolve(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4

    def test_opponents_instant_or_sorcery_does_not_pump_the_animated_land(self) -> None:
        game = create_game()
        p1, p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _animate_hall(game, p1, hall)
        hall.register_triggers(game)

        spell = Instant(name="Enemy Lesson", owner=p2, controller=p2, mana_cost=ManaCost.parse("{U}"))
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell,
                player=p2,
                card=spell,
                controller=p2,
            ),
        )
        game.effect_manager.apply_all(game)

        assert game.stack.is_empty()
        assert hall.power == 2
        assert hall.toughness == 4

    def test_spell_cast_pump_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _animate_hall(game, p1, hall)
        hall.register_triggers(game)

        spell = Instant(name="Study Break", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell,
                player=p1,
                card=spell,
                controller=p1,
            ),
        )
        trigger = game.stack.pop()
        trigger.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 3

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 2
        assert hall.toughness == 4
