"""Tests for sos_257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Creature, Land, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestGreatHallProperties:
    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).name == "Great Hall of the Biblioplex"

    def test_is_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_starts_untapped(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.is_tapped is False

    def test_starts_as_non_creature(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card._is_creature_form is False
        assert CardType.CREATURE not in card.card_types

    def test_has_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 2


class TestGreatHallBasicManaAbility:
    """{T}: Add {C}."""

    def test_basic_ability_taps_and_produces_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        assert hall.is_tapped is False
        abilities = hall.get_mana_abilities()
        basic = abilities[0]
        # Activate cost.
        result = basic.cost(game)
        assert result is True
        assert hall.is_tapped is True
        mana = basic.mana_produced(game)
        assert mana.get(ManaType.COLORLESS, 0) == 1

    def test_basic_ability_fails_when_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        hall.is_tapped = True
        abilities = hall.get_mana_abilities()
        basic = abilities[0]
        result = basic.cost(game)
        assert result is False


class TestGreatHallLifeAbility:
    """{T}, Pay 1 life: Add one mana of any color."""

    def test_life_ability_taps_and_costs_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        hall.controller = p1
        abilities = hall.get_mana_abilities()
        life_ab = abilities[1]
        result = life_ab.cost(game)
        assert result is True
        assert hall.is_tapped is True
        assert p1.life == 19  # paid 1 life

    def test_life_ability_fails_when_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        hall.is_tapped = True
        abilities = hall.get_mana_abilities()
        life_ab = abilities[1]
        result = life_ab.cost(game)
        assert result is False

    def test_life_ability_fails_when_life_too_low(self) -> None:
        game = create_game(player1_life=1)
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        abilities = hall.get_mana_abilities()
        life_ab = abilities[1]
        result = life_ab.cost(game)
        assert result is False


class TestGreatHallAnimate:
    """{5}: Become a 2/4 Wizard creature (still a land)."""

    def test_animate_requires_five_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])
        # No mana — should fail.
        result = hall.animate(game)
        assert result is False
        assert hall._is_creature_form is False

    def test_animate_succeeds_with_five_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        result = hall.animate(game)
        assert result is True
        assert hall._is_creature_form is True

    def test_animated_hall_is_creature_and_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        hall.animate(game)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types

    def test_animated_hall_is_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        hall.animate(game)
        assert "Wizard" in hall.subtypes

    def test_animated_hall_power_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        hall.animate(game)
        assert hall.power == 2
        assert hall.toughness == 4

    def test_animate_is_no_op_when_already_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 10})
        hall.animate(game)
        result = hall.animate(game)
        assert result is False  # Already a creature.


class TestGreatHallPumpTrigger:
    """When animated and an instant/sorcery is cast, gets +1/+0 until EOT."""

    def test_pump_trigger_registered_on_animate(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        before = len(game.trigger_manager.get_triggers())
        hall.animate(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_casting_instant_pushes_pump_trigger(self) -> None:
        from engine.events import SpellCastTriggeredEvent
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        hall.animate(game)
        instant = Creature.__new__(Creature)
        from engine.card import Instant as I
        instant = I(name="Bolt", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=instant, controller=p1)
        before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) > before
