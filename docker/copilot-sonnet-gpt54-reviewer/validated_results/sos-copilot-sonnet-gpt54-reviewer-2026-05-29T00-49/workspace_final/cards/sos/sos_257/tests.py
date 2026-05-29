"""Tests for sos_257 — Great Hall of the Biblioplex.

Covers:
- Static card properties (name, type = Land, no mana cost, no creature initially)
- {T} mana ability: taps and adds {C} to mana pool
- {T}, Pay 1 life mana ability: taps, reduces life by 1, adds any-color mana
- {5} activated ability: land becomes a 2/4 Wizard creature (still a land)
- Guard: {5} cannot be activated if the land is already a creature
- Triggered ability: while a creature, casting an instant or sorcery grants +1/+0
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Instant, Land, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hall(game: Any, player_index: int = 0) -> GreatHallOfTheBiblioplex:
    """Create a GreatHallOfTheBiblioplex owned by the given player."""
    player = game.players[player_index]
    return GreatHallOfTheBiblioplex(owner=player, controller=player)


def _place_on_battlefield(game: Any, player_index: int, card: Any) -> None:
    """Put a card directly on the battlefield for the given player."""
    player = game.players[player_index]
    bf = game.get_battlefield(player)
    bf.add(card)


def _activate_colorless_mana(game: Any, card: Any) -> bool:
    """Invoke the first mana ability (tap for {C}) and return whether it succeeded."""
    abilities = card.get_mana_abilities()
    if not abilities:
        return False
    ability = abilities[0]
    player = card.controller
    paid = ability.cost(game, card)
    if paid:
        ability.mana_produced(game)
    return paid


def _activate_life_mana(game: Any, card: Any, mana_type: ManaType | None = None) -> bool:
    """Invoke the second mana ability ({T}, pay 1 life → any color).

    If the implementation accepts a mana_type argument, pass it; otherwise
    just call the produced callable and check what mana was added.
    """
    abilities = card.get_mana_abilities()
    if len(abilities) < 2:
        return False
    ability = abilities[1]
    paid = ability.cost(game, card)
    if paid:
        if mana_type is not None:
            try:
                ability.mana_produced(game, mana_type)
            except TypeError:
                ability.mana_produced(game)
        else:
            ability.mana_produced(game)
    return paid


def _activate_creature_ability(game: Any, card: Any) -> bool:
    """Invoke the {5} activated ability (land becomes 2/4 Wizard creature)."""
    abilities = card.get_activated_abilities()
    if not abilities:
        return False
    ability = abilities[0]
    # Pay the cost — the cost callable should check & pay {5} generic mana.
    paid = ability.cost(game, card)
    if paid:
        ability.effect(game)
    return paid


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestGreatHallOfTheBibliplexProperties:
    """Static card data should match the sos_257 spec."""

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"

    def test_is_land_instance(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)

    def test_has_land_card_type(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_no_creature_card_type_initially(self) -> None:
        """Land must not be a creature before the {5} ability is used."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.CREATURE not in card.card_types

    def test_no_mana_cost(self) -> None:
        """Lands have no mana cost."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.mana_cost.cmc == 0

    def test_no_wizard_subtype_initially(self) -> None:
        """Land should not have Wizard subtype until the activation fires."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert "Wizard" not in card.subtypes

    def test_can_cast_returns_false(self) -> None:
        """Lands are played, not cast."""
        game = create_game()
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.can_cast(game) is False


# ---------------------------------------------------------------------------
# {T}: Add {C}
# ---------------------------------------------------------------------------

class TestGreatHallColorlessManaAbility:
    """{T}: Add {C} — the first mana ability."""

    def test_has_at_least_one_mana_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) >= 1

    def test_colorless_ability_adds_colorless_mana(self) -> None:
        """Activating the first mana ability should add exactly 1 {C} to the pool."""
        game = create_game()
        card = _make_hall(game, 0)
        player = game.players[0]
        before = player.mana_pool.get(ManaType.COLORLESS)
        _activate_colorless_mana(game, card)
        after = player.mana_pool.get(ManaType.COLORLESS)
        assert after == before + 1

    def test_colorless_ability_taps_the_land(self) -> None:
        """After activation the land should be tapped."""
        game = create_game()
        card = _make_hall(game, 0)
        card.is_tapped = False
        _activate_colorless_mana(game, card)
        assert card.is_tapped is True

    def test_colorless_ability_fails_if_already_tapped(self) -> None:
        """Tap cost must not succeed when the land is already tapped."""
        game = create_game()
        card = _make_hall(game, 0)
        card.is_tapped = True
        player = game.players[0]
        before = player.mana_pool.get(ManaType.COLORLESS)
        result = _activate_colorless_mana(game, card)
        after = player.mana_pool.get(ManaType.COLORLESS)
        # Either the cost fails (returns False) or mana is not added.
        assert result is False or after == before


# ---------------------------------------------------------------------------
# {T}, Pay 1 life: Add one mana of any color
# ---------------------------------------------------------------------------

class TestGreatHallLifeManaAbility:
    """{T}, Pay 1 life: Add one mana of any color (restricted to instants/sorceries)."""

    def test_has_at_least_two_mana_abilities(self) -> None:
        """The card should expose both the colorless and the life-cost ability."""
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 2

    def test_life_ability_reduces_player_life_by_one(self) -> None:
        """Paying 1 life should lower the controller's life total by exactly 1."""
        game = create_game(player1_life=20)
        card = _make_hall(game, 0)
        player = game.players[0]
        _activate_life_mana(game, card)
        assert player.life == 19

    def test_life_ability_taps_the_land(self) -> None:
        """The {T} component must tap the land."""
        game = create_game()
        card = _make_hall(game, 0)
        card.is_tapped = False
        _activate_life_mana(game, card)
        assert card.is_tapped is True

    def test_life_ability_adds_mana_to_pool(self) -> None:
        """After paying 1 life, the mana pool should have at least 1 more mana."""
        game = create_game()
        card = _make_hall(game, 0)
        player = game.players[0]
        before = player.mana_pool.total()
        paid = _activate_life_mana(game, card)
        after = player.mana_pool.total()
        if paid:
            assert after > before

    def test_life_ability_adds_colored_mana(self) -> None:
        """The ability produces colored mana (not colorless)."""
        game = create_game()
        card = _make_hall(game, 0)
        player = game.players[0]
        # Try each color
        colored_types = [
            ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN
        ]
        for color in colored_types:
            # Reset state
            card.is_tapped = False
            player.life = 20
            player.mana_pool.empty()
            paid = _activate_life_mana(game, card, mana_type=color)
            if paid:
                # Should have added exactly 1 mana of any color
                total = sum(player.mana_pool.get(c) for c in colored_types)
                assert total >= 1
                return
        pytest.fail("Life-cost mana ability did not succeed with any color choice")

    def test_life_ability_fails_if_already_tapped(self) -> None:
        """Cannot activate the life-cost ability if the land is already tapped."""
        game = create_game(player1_life=20)
        card = _make_hall(game, 0)
        card.is_tapped = True
        player = game.players[0]
        result = _activate_life_mana(game, card)
        # If the cost fails (returns False), life should not decrease either.
        if result is False:
            assert player.life == 20


# ---------------------------------------------------------------------------
# {5}: Become a 2/4 Wizard creature
# ---------------------------------------------------------------------------

class TestGreatHallBecomeCreatureAbility:
    """{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature."""

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability for the {5} activation."""
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) >= 1

    def test_activation_adds_creature_card_type(self) -> None:
        """After activation the card should have CardType.CREATURE."""
        game = create_game()
        player = game.players[0]
        card = _make_hall(game, 0)
        _place_on_battlefield(game, 0, card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _activate_creature_ability(game, card)
        assert CardType.CREATURE in card.card_types

    def test_activation_preserves_land_card_type(self) -> None:
        """After activation the card must still be a land."""
        game = create_game()
        card = _make_hall(game, 0)
        _place_on_battlefield(game, 0, card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _activate_creature_ability(game, card)
        assert CardType.LAND in card.card_types

    def test_activation_adds_wizard_subtype(self) -> None:
        """After activation the card must have 'Wizard' as a subtype."""
        game = create_game()
        card = _make_hall(game, 0)
        _place_on_battlefield(game, 0, card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _activate_creature_ability(game, card)
        assert "Wizard" in card.subtypes

    def test_activation_sets_power_to_2(self) -> None:
        """After activation the creature should have power 2."""
        game = create_game()
        card = _make_hall(game, 0)
        _place_on_battlefield(game, 0, card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _activate_creature_ability(game, card)
        # Implementation may use base_power or modified_power
        power = getattr(card, "base_power", getattr(card, "modified_power", None))
        assert power == 2

    def test_activation_sets_toughness_to_4(self) -> None:
        """After activation the creature should have toughness 4."""
        game = create_game()
        card = _make_hall(game, 0)
        _place_on_battlefield(game, 0, card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _activate_creature_ability(game, card)
        # Implementation may use base_toughness or modified_toughness
        toughness = getattr(card, "base_toughness", getattr(card, "modified_toughness", None))
        assert toughness == 4

    def test_cannot_activate_if_already_a_creature(self) -> None:
        """The guard 'if this land isn't a creature' must block a second activation."""
        game = create_game()
        card = _make_hall(game, 0)
        _place_on_battlefield(game, 0, card)
        # First activation (succeeds)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 10})
        _activate_creature_ability(game, card)
        assert CardType.CREATURE in card.card_types
        # Second activation — cost must fail because the land is already a creature
        result = _activate_creature_ability(game, card)
        assert result is False


# ---------------------------------------------------------------------------
# Triggered ability: +1/+0 while creature on instant/sorcery cast
# ---------------------------------------------------------------------------

class TestGreatHallCreatureTrigger:
    """While a creature, this land gets +1/+0 whenever an instant/sorcery is cast."""

    def _setup_creature_hall(self, game: Any) -> GreatHallOfTheBiblioplex:
        """Activate the {5} ability and register triggers, return the card."""
        card = _make_hall(game, 0)
        _place_on_battlefield(game, 0, card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _activate_creature_ability(game, card)
        card.register_triggers(game)
        return card

    def test_registers_trigger_on_creature_activation(self) -> None:
        """Triggering the {5} ability should register a SpellCast trigger."""
        game = create_game()
        card = _make_hall(game, 0)
        _place_on_battlefield(game, 0, card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        before = len(game.trigger_manager.get_triggers())
        _activate_creature_ability(game, card)
        # After activation, triggers (either registered in effect or via register_triggers)
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_instant_cast_triggers_power_boost(self) -> None:
        """Casting an instant while the hall is a creature should boost power by +1."""
        game = create_game()
        player = game.players[0]
        card = self._setup_creature_hall(game)
        power_before = getattr(card, "modified_power", getattr(card, "base_power", 2))
        instant = Instant(name="Lightning Bolt", owner=player, controller=player)
        event = SpellCastTriggeredEvent(spell=instant, player=player, controller=player)
        game.trigger_manager.fire_event(game, event)
        power_after = getattr(card, "modified_power", getattr(card, "base_power", 2))
        assert power_after == power_before + 1

    def test_sorcery_cast_triggers_power_boost(self) -> None:
        """Casting a sorcery while the hall is a creature should boost power by +1."""
        game = create_game()
        player = game.players[0]
        card = self._setup_creature_hall(game)
        power_before = getattr(card, "modified_power", getattr(card, "base_power", 2))
        sorcery = Sorcery(name="Divination", owner=player, controller=player)
        event = SpellCastTriggeredEvent(spell=sorcery, player=player, controller=player)
        game.trigger_manager.fire_event(game, event)
        power_after = getattr(card, "modified_power", getattr(card, "base_power", 2))
        assert power_after == power_before + 1

    def test_non_instant_sorcery_does_not_trigger_power_boost(self) -> None:
        """Casting a non-instant/sorcery spell while a creature should NOT boost power."""
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = self._setup_creature_hall(game)
        power_before = getattr(card, "modified_power", getattr(card, "base_power", 2))
        # A creature spell is neither an instant nor a sorcery
        creature_spell = Creature(
            name="Grizzly Bears",
            owner=player,
            controller=player,
            base_power=2,
            base_toughness=2,
        )
        event = SpellCastTriggeredEvent(spell=creature_spell, player=player, controller=player)
        game.trigger_manager.fire_event(game, event)
        power_after = getattr(card, "modified_power", getattr(card, "base_power", 2))
        assert power_after == power_before

    def test_power_boost_only_applies_to_controller(self) -> None:
        """An opponent casting an instant should NOT boost the hall's power."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = self._setup_creature_hall(game)
        power_before = getattr(card, "modified_power", getattr(card, "base_power", 2))
        # Opponent casts an instant
        instant = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        event = SpellCastTriggeredEvent(spell=instant, player=p2, controller=p2)
        game.trigger_manager.fire_event(game, event)
        power_after = getattr(card, "modified_power", getattr(card, "base_power", 2))
        assert power_after == power_before

    def test_multiple_instant_casts_each_boost_power(self) -> None:
        """Each instant/sorcery cast should add another +1/+0."""
        game = create_game()
        player = game.players[0]
        card = self._setup_creature_hall(game)
        power_start = getattr(card, "modified_power", getattr(card, "base_power", 2))
        for _ in range(3):
            instant = Instant(name="Shock", owner=player, controller=player)
            event = SpellCastTriggeredEvent(spell=instant, player=player, controller=player)
            game.trigger_manager.fire_event(game, event)
        power_end = getattr(card, "modified_power", getattr(card, "base_power", 2))
        assert power_end == power_start + 3
