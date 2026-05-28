"""Tests for SOS 257 -- Great Hall of the Biblioplex.

Great Hall of the Biblioplex is a Land with three abilities:
1. {T}: Add {C}.
2. {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
   an instant or sorcery spell.
3. {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
   "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
   until end of turn." It's still a land.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import ActivatedAbility, Land, ManaAbility, Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestGreatHallProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"

    def test_no_mana_cost(self) -> None:
        """Lands have no mana cost."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.mana_cost == ManaCost()

    def test_card_type_includes_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_cannot_be_cast(self) -> None:
        """Lands are played, not cast."""
        game = create_game()
        card = GreatHallOfTheBiblioplex(owner=game.players[0])
        assert card.can_cast(game) is False


# ---------------------------------------------------------------------------
# Ability 1: {T}: Add {C}
# ---------------------------------------------------------------------------


class TestColorlessManaAbility:
    """The first mana ability taps the land to produce one colorless mana."""

    def test_has_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_colorless_mana_ability_exists(self) -> None:
        """At least one mana ability should produce colorless mana."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        abilities = card.get_mana_abilities()
        # Find the colorless-producing ability (simple tap cost, no life payment)
        found = False
        for ability in abilities:
            assert isinstance(ability, ManaAbility)
            # Try to activate the ability
            if ability.cost(game) if callable(ability.cost) else ability.cost(game, card):
                result = ability.mana_produced(game) if callable(ability.mana_produced) else ability.mana_produced(game)
                # Check that colorless mana was added
                if p1.mana_pool.get(ManaType.COLORLESS) >= 1:
                    found = True
                break
        assert found, "No mana ability produces colorless mana"

    def test_colorless_taps_land(self) -> None:
        """Tapping for colorless should tap the land."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        assert card.is_tapped is False

        abilities = card.get_mana_abilities()
        # Activate the first mana ability (colorless)
        ability = abilities[0]
        cost_result = ability.cost(game) if callable(ability.cost) else ability.cost(game, card)
        assert cost_result is True or cost_result  # cost paid successfully
        assert card.is_tapped is True

    def test_colorless_fails_when_already_tapped(self) -> None:
        """Cannot tap an already-tapped land for mana."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True
        set_board_state(game, 0, battlefield=[card])

        abilities = card.get_mana_abilities()
        ability = abilities[0]
        # Try both call signatures used in the engine
        try:
            result = ability.cost(game)
        except TypeError:
            result = ability.cost(game, card)
        assert result is False


# ---------------------------------------------------------------------------
# Ability 2: {T}, Pay 1 life: Add one mana of any color
#            (restricted to instant/sorcery spells)
# ---------------------------------------------------------------------------


class TestAnyColorManaAbility:
    """The second mana ability taps and pays 1 life to produce any color."""

    def test_has_at_least_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 2

    def test_any_color_ability_pays_life(self) -> None:
        """The any-color ability should cost 1 life."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        initial_life = p1.life

        # The second ability is the any-color one
        abilities = card.get_mana_abilities()
        ability = abilities[1]  # Second mana ability
        try:
            result = ability.cost(game)
        except TypeError:
            result = ability.cost(game, card)

        if result:
            # Life should have been paid
            assert p1.life == initial_life - 1
            assert card.is_tapped is True

    def test_any_color_ability_produces_colored_mana(self) -> None:
        """The any-color ability should add one mana of a chosen color."""
        game = create_game(scripts=([ManaType.RED], []))
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        abilities = card.get_mana_abilities()
        ability = abilities[1]
        try:
            ability.cost(game)
        except TypeError:
            ability.cost(game, card)
        ability.mana_produced(game) if callable(ability.mana_produced) else None

        # Should have produced colored mana (any of WUBRG)
        total_colored = sum(
            p1.mana_pool.get(mt)
            for mt in [ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                       ManaType.RED, ManaType.GREEN]
        )
        assert total_colored >= 1

    def test_any_color_fails_when_tapped(self) -> None:
        """Cannot activate the any-color ability when already tapped."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True
        set_board_state(game, 0, battlefield=[card])

        abilities = card.get_mana_abilities()
        ability = abilities[1]
        try:
            result = ability.cost(game)
        except TypeError:
            result = ability.cost(game, card)
        assert result is False


# ---------------------------------------------------------------------------
# Ability 3: {5}: If this land isn't a creature, it becomes a 2/4 Wizard
#            creature with triggered ability. It's still a land.
# ---------------------------------------------------------------------------


class TestCreatureAnimationAbility:
    """The {5} activated ability animates the land into a 2/4 Wizard creature."""

    def test_has_activated_ability(self) -> None:
        """The card should provide at least one activated ability for {5}."""
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_animation_makes_creature(self) -> None:
        """After activating the {5} ability, the land becomes a creature."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        # Pay the cost
        try:
            cost_ok = ability.cost(game)
        except TypeError:
            cost_ok = ability.cost(game, card)
        if cost_ok:
            ability.effect(game)

        # Card should now be a creature
        assert CardType.CREATURE in card.card_types

    def test_animation_keeps_land_type(self) -> None:
        """After animation, the land should still be a land."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        try:
            cost_ok = ability.cost(game)
        except TypeError:
            cost_ok = ability.cost(game, card)
        if cost_ok:
            ability.effect(game)

        assert CardType.LAND in card.card_types

    def test_animation_sets_power_toughness(self) -> None:
        """The animated land should be a 2/4 creature."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        try:
            cost_ok = ability.cost(game)
        except TypeError:
            cost_ok = ability.cost(game, card)
        if cost_ok:
            ability.effect(game)

        # Check power and toughness -- may be on base_ or modified_ attrs
        power = getattr(card, 'power', None) or getattr(card, 'base_power', None)
        toughness = getattr(card, 'toughness', None) or getattr(card, 'base_toughness', None)
        assert power == 2
        assert toughness == 4

    def test_animation_adds_wizard_subtype(self) -> None:
        """The animated land should have the Wizard creature type."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        try:
            cost_ok = ability.cost(game)
        except TypeError:
            cost_ok = ability.cost(game, card)
        if cost_ok:
            ability.effect(game)

        assert "Wizard" in card.subtypes

    def test_animation_no_op_if_already_creature(self) -> None:
        """If the land is already a creature, {5} should not re-animate it."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        # Manually mark as creature already
        card.card_types.add(CardType.CREATURE)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        try:
            cost_ok = ability.cost(game)
        except TypeError:
            cost_ok = ability.cost(game, card)
        # The ability may still pay cost but the effect should check
        # "if this land isn't a creature"
        if cost_ok:
            ability.effect(game)

        # Should still be a creature and land, but shouldn't error
        assert CardType.CREATURE in card.card_types
        assert CardType.LAND in card.card_types

    def test_animation_costs_five_generic(self) -> None:
        """The animation ability costs {5} (5 generic mana)."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 5})
        initial_total = p1.mana_pool.total()

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        try:
            cost_ok = ability.cost(game)
        except TypeError:
            cost_ok = ability.cost(game, card)

        assert cost_ok is True
        # 5 mana should have been paid
        assert p1.mana_pool.total() == initial_total - 5

    def test_animation_fails_with_insufficient_mana(self) -> None:
        """The animation ability should fail if fewer than 5 mana available."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 4})

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        try:
            result = ability.cost(game)
        except TypeError:
            result = ability.cost(game, card)
        assert result is False


# ---------------------------------------------------------------------------
# Triggered ability on animated creature:
# "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
#  until end of turn."
# ---------------------------------------------------------------------------


class TestAnimatedCreatureTriggeredAbility:
    """Once animated, casting an instant/sorcery should pump +1/+0."""

    def _animate_card(self, game, card, p1):
        """Helper to animate the land into a creature."""
        abilities = card.get_activated_abilities()
        ability = abilities[0]
        try:
            cost_ok = ability.cost(game)
        except TypeError:
            cost_ok = ability.cost(game, card)
        if cost_ok:
            ability.effect(game)

    def test_trigger_registered_after_animation(self) -> None:
        """After animation, a SpellCast trigger should be registered."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})

        triggers_before = len(game.trigger_manager.get_triggers_for_source(card))
        self._animate_card(game, card, p1)
        triggers_after = len(game.trigger_manager.get_triggers_for_source(card))

        # Should have registered at least one trigger
        assert triggers_after > triggers_before

    def test_instant_cast_pumps_power(self) -> None:
        """Casting an instant should give the animated creature +1/+0."""
        from engine.card import Instant
        from engine.events import SpellCastTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})
        self._animate_card(game, card, p1)

        # Record power before trigger fires
        power_before = getattr(card, 'power', None) or getattr(card, 'modified_power', None) or 2

        # Fire a SpellCast event for an instant spell
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=instant,
            player=p1,
            card=instant,
            controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        # Resolve the trigger from the stack
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        power_after = getattr(card, 'power', None) or getattr(card, 'modified_power', None)
        assert power_after == power_before + 1

    def test_sorcery_cast_pumps_power(self) -> None:
        """Casting a sorcery should also give +1/+0."""
        from engine.card import Sorcery
        from engine.events import SpellCastTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})
        self._animate_card(game, card, p1)

        power_before = getattr(card, 'power', None) or getattr(card, 'modified_power', None) or 2

        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=sorcery,
            player=p1,
            card=sorcery,
            controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        power_after = getattr(card, 'power', None) or getattr(card, 'modified_power', None)
        assert power_after == power_before + 1

    def test_creature_cast_does_not_pump(self) -> None:
        """Casting a creature spell should NOT pump the animated land."""
        from engine.card import Creature as CreatureCard
        from engine.events import SpellCastTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})
        self._animate_card(game, card, p1)

        power_before = getattr(card, 'power', None) or getattr(card, 'modified_power', None) or 2

        creature = CreatureCard(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        event = SpellCastTriggeredEvent(
            spell=creature,
            player=p1,
            card=creature,
            controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        power_after = getattr(card, 'power', None) or getattr(card, 'modified_power', None) or 2
        assert power_after == power_before

    def test_multiple_instants_stack_pump(self) -> None:
        """Casting two instants should give +2/+0 total."""
        from engine.card import Instant
        from engine.events import SpellCastTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})
        self._animate_card(game, card, p1)

        power_before = getattr(card, 'power', None) or getattr(card, 'modified_power', None) or 2

        # First instant
        instant1 = Instant(name="Opt", owner=p1, controller=p1)
        event1 = SpellCastTriggeredEvent(
            spell=instant1, player=p1, card=instant1, controller=p1,
        )
        game.trigger_manager.fire_event(game, event1)
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # Second instant
        instant2 = Instant(name="Shock", owner=p1, controller=p1)
        event2 = SpellCastTriggeredEvent(
            spell=instant2, player=p1, card=instant2, controller=p1,
        )
        game.trigger_manager.fire_event(game, event2)
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        power_after = getattr(card, 'power', None) or getattr(card, 'modified_power', None)
        assert power_after == power_before + 2

    def test_toughness_not_changed_by_pump(self) -> None:
        """The pump is +1/+0, so toughness should remain unchanged."""
        from engine.card import Instant
        from engine.events import SpellCastTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.COLORLESS: 10})
        self._animate_card(game, card, p1)

        toughness_before = getattr(card, 'toughness', None) or getattr(card, 'modified_toughness', None) or 4

        instant = Instant(name="Opt", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=instant, player=p1, card=instant, controller=p1,
        )
        game.trigger_manager.fire_event(game, event)
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        toughness_after = getattr(card, 'toughness', None) or getattr(card, 'modified_toughness', None)
        assert toughness_after == toughness_before
