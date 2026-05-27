"""Tests for SOS 257 — Great Hall of the Biblioplex.

Great Hall of the Biblioplex is a Land with three abilities:
  1. {T}: Add {C}. (colorless mana ability)
  2. {T}, Pay 1 life: Add one mana of any color.
     Spend this mana only to cast an instant or sorcery spell.
  3. {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
     with 'Whenever you cast an instant or sorcery spell, this creature
     gets +1/+0 until end of turn.' It's still a land.

Tests cover:
- Static card properties (name, type, mana cost)
- Ability 1: tap for colorless — adds {C}, taps the land, blocked when tapped
- Ability 2: tap + pay 1 life for colored mana — adds colored mana, taps,
  deducts 1 life, blocked when tapped
- Ability 3: {5} animate to 2/4 Wizard creature-land —
  card types include CREATURE + LAND, subtypes include "Wizard",
  power/toughness are 2/4
- Guard condition: animate ability does nothing if already a creature
- Triggered ability (when animated): fires for instant/sorcery cast by
  controller, boosts power +1/+0; does NOT fire for permanents or
  opponent's spells
"""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Creature, Instant, Land, ManaAbility, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instant(name: str = "TestInstant") -> Instant:
    return Instant(name=name)


def _make_sorcery(name: str = "TestSorcery") -> Sorcery:
    return Sorcery(name=name)


def _make_creature(name: str = "TestCreature") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"

    def test_has_land_card_type(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        """Lands have no mana cost."""
        card = GreatHallOfTheBiblioplex(owner=None)
        # ManaCost() with no args is the empty/no-cost sentinel
        assert card.mana_cost == ManaCost()

    def test_starts_untapped(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.is_tapped is False

    def test_cannot_be_cast(self) -> None:
        """Lands use a special play action, not casting."""
        game = create_game()
        card = GreatHallOfTheBiblioplex(owner=game.players[0])
        assert card.can_cast(game) is False


# ---------------------------------------------------------------------------
# Ability 1 — {T}: Add {C}
# ---------------------------------------------------------------------------


class TestGreatHallColorlessManaAbility:
    """The land must expose a mana ability for {T}: Add {C}."""

    def test_has_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_mana_abilities_are_mana_ability_instances(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        for ability in card.get_mana_abilities():
            assert isinstance(ability, ManaAbility)

    def test_colorless_ability_taps_land_and_adds_colorless(self) -> None:
        """Activating the colorless mana ability taps the land and adds {C}."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        # Find the colorless ability: its effect adds COLORLESS to mana pool
        # Identify it by activating each and checking which adds colorless
        # We test via mana_produced callable
        colorless_ability = None
        for ab in card.get_mana_abilities():
            pool_before = p1.mana_pool.get(ManaType.COLORLESS)
            # Pay cost to tap
            card.is_tapped = False
            paid = ab.cost(game, card)
            if paid:
                ab.mana_produced(game)
                pool_after = p1.mana_pool.get(ManaType.COLORLESS)
                if pool_after > pool_before:
                    colorless_ability = ab
                break
            p1.mana_pool.empty()

        assert colorless_ability is not None, (
            "Expected a mana ability that produces {C}"
        )
        assert card.is_tapped is True

    def test_colorless_ability_cost_fails_when_tapped(self) -> None:
        """If the land is already tapped, the tap cost should fail."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True

        for ab in card.get_mana_abilities():
            result = ab.cost(game, card)
            if result is False:
                return  # At least one ability correctly rejects when tapped

        # If we reach here, all abilities accepted a tapped land — that's wrong
        # (test will fail if no ability returned False for tapped land)
        assert False, "Expected at least one mana ability to reject when land is tapped"

    def test_has_at_least_two_mana_abilities(self) -> None:
        """Card has two distinct mana abilities: {T}→{C} and {T}+1life→color."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert len(card.get_mana_abilities()) >= 2


# ---------------------------------------------------------------------------
# Ability 2 — {T}, Pay 1 life: Add one mana of any color
# ---------------------------------------------------------------------------


class TestGreatHallColoredManaAbility:
    """{T}, Pay 1 life: Add one mana of any color."""

    def test_colored_ability_taps_land(self) -> None:
        """Activating the colored mana ability should tap the land."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        starting_life = p1.life

        # Try activating each non-colorless mana ability
        # The colored ability taps AND costs 1 life
        colored_ability = None
        for ab in card.get_mana_abilities():
            card.is_tapped = False
            p1.life = 20
            p1.mana_pool.empty()

            paid = ab.cost(game, card)
            if paid:
                ab.mana_produced(game)
                # Check if life decreased (colored mana ability)
                if p1.life < 20:
                    colored_ability = ab
                    assert card.is_tapped is True
                    break
            card.is_tapped = False

        assert colored_ability is not None, (
            "Expected a mana ability that costs 1 life"
        )

    def test_colored_ability_deducts_one_life(self) -> None:
        """Activating the colored mana ability costs 1 life."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        p1.life = 20

        for ab in card.get_mana_abilities():
            card.is_tapped = False
            p1.mana_pool.empty()
            paid = ab.cost(game, card)
            if paid:
                ab.mana_produced(game)
                if p1.life < 20:
                    # Found the life-costing ability
                    assert p1.life == 19
                    return
            card.is_tapped = False

        assert False, "Expected a mana ability that deducts 1 life"

    def test_colored_ability_adds_colored_mana(self) -> None:
        """The colored ability should add at least one colored mana to the pool."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        p1.life = 20

        colored_types = {
            ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
            ManaType.RED, ManaType.GREEN,
        }

        for ab in card.get_mana_abilities():
            card.is_tapped = False
            p1.mana_pool.empty()
            life_before = p1.life
            paid = ab.cost(game, card)
            if paid:
                ab.mana_produced(game)
                if p1.life < life_before:
                    # Found the life-costing ability; check it added colored mana
                    total_colored = sum(
                        p1.mana_pool.get(mt) for mt in colored_types
                    )
                    assert total_colored >= 1, (
                        "Expected at least 1 colored mana after ability activation"
                    )
                    return
            card.is_tapped = False

        assert False, "Expected to find a life-costing colored mana ability"

    def test_colored_ability_blocked_when_tapped(self) -> None:
        """The {T}, Pay 1 life ability cannot be activated if the land is tapped."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True
        life_before = p1.life

        for ab in card.get_mana_abilities():
            result = ab.cost(game, card)
            # All tap-cost abilities must return False when land is tapped
            if result is False:
                assert p1.life == life_before, (
                    "Life should not be deducted when tap cost fails"
                )


# ---------------------------------------------------------------------------
# Ability 3 — {5}: Animate to 2/4 Wizard creature-land
# ---------------------------------------------------------------------------


class TestGreatHallAnimateAbility:
    """{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature.
    It's still a land."""

    def test_has_activated_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_animate_effect_adds_creature_type(self) -> None:
        """After animation, the land should also have CardType.CREATURE."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        # Activate the animate ability effect directly
        for ab in card.get_activated_abilities():
            ab.effect(game)
            break  # Only one animate ability expected

        assert CardType.CREATURE in card.card_types

    def test_animate_effect_retains_land_type(self) -> None:
        """After animation, the card should still have CardType.LAND."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        for ab in card.get_activated_abilities():
            ab.effect(game)
            break

        assert CardType.LAND in card.card_types

    def test_animate_effect_sets_power_two(self) -> None:
        """After animation, the land-creature's base power should be 2."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        for ab in card.get_activated_abilities():
            ab.effect(game)
            break

        # Power is accessible via base_power or modified_power
        assert getattr(card, "base_power", None) == 2 or \
               getattr(card, "modified_power", None) == 2

    def test_animate_effect_sets_toughness_four(self) -> None:
        """After animation, the land-creature's base toughness should be 4."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        for ab in card.get_activated_abilities():
            ab.effect(game)
            break

        assert getattr(card, "base_toughness", None) == 4 or \
               getattr(card, "modified_toughness", None) == 4

    def test_animate_effect_adds_wizard_subtype(self) -> None:
        """After animation, the card should have 'Wizard' as a subtype."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        for ab in card.get_activated_abilities():
            ab.effect(game)
            break

        assert "Wizard" in card.subtypes

    def test_animate_guard_does_not_apply_when_already_creature(self) -> None:
        """If the land is already a creature, the animate ability should do
        nothing (the oracle text says 'if this land isn't a creature')."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        # First animation — should work
        for ab in card.get_activated_abilities():
            ab.effect(game)
            break

        # At this point the card IS a creature
        assert CardType.CREATURE in card.card_types

        # Try to animate a second time — the guard should prevent mutation
        # We capture the state before the second activation
        power_before = getattr(card, "base_power", getattr(card, "modified_power", None))

        for ab in card.get_activated_abilities():
            ab.effect(game)
            break

        # Power must not have doubled (guard prevents re-animation)
        power_after = getattr(card, "base_power", getattr(card, "modified_power", None))
        assert power_after == power_before, (
            "Animate ability must be a no-op when land is already a creature"
        )


# ---------------------------------------------------------------------------
# Triggered ability — fires when controller casts instant or sorcery
# ---------------------------------------------------------------------------


class TestGreatHallAnimatedCreatureTrigger:
    """When animated, 'Whenever you cast an instant or sorcery spell,
    this creature gets +1/+0 until end of turn.'"""

    def _animate_card(self, game, card) -> None:
        """Helper: trigger the animate effect on the card."""
        for ab in card.get_activated_abilities():
            ab.effect(game)
            break

    def test_register_triggers_adds_spell_cast_trigger(self) -> None:
        """After animation, register_triggers should register a trigger
        for SpellCastTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        # Animate first so the creature trigger is active
        self._animate_card(game, card)

        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())

        assert after > before

    def test_trigger_event_type_is_spell_cast(self) -> None:
        """The registered trigger must respond to SpellCastTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        self._animate_card(game, card)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) > 0
        event_types = [t.event_type for t in triggers]
        assert SpellCastTriggeredEvent in event_types

    def test_trigger_fires_for_instant_cast_by_controller(self) -> None:
        """Casting an instant while the animated Hall is on the battlefield
        should push the +1/+0 trigger onto the stack."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        self._animate_card(game, card)
        card.register_triggers(game)

        instant = _make_instant("LightningBolt")
        instant.owner = p1
        instant.controller = p1

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=instant, player=p1, card=instant, controller=p1
            ),
        )

        assert not game.stack.is_empty(), (
            "Expected a trigger on the stack after controller casts instant"
        )

    def test_trigger_fires_for_sorcery_cast_by_controller(self) -> None:
        """Casting a sorcery while animated should also trigger."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        self._animate_card(game, card)
        card.register_triggers(game)

        sorcery = _make_sorcery("Divination")
        sorcery.owner = p1
        sorcery.controller = p1

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=sorcery, player=p1, card=sorcery, controller=p1
            ),
        )

        assert not game.stack.is_empty()

    def test_trigger_does_not_fire_for_creature_spell(self) -> None:
        """Casting a creature should NOT trigger the +1/+0 ability."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        self._animate_card(game, card)
        card.register_triggers(game)

        creature_spell = _make_creature("GrizzlyBears")
        creature_spell.owner = p1
        creature_spell.controller = p1

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=creature_spell,
                player=p1,
                card=creature_spell,
                controller=p1,
            ),
        )

        assert game.stack.is_empty(), (
            "Creature spell should NOT trigger the +1/+0 ability"
        )

    def test_trigger_does_not_fire_for_opponents_instant(self) -> None:
        """An opponent casting an instant should NOT trigger the Hall's ability."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        self._animate_card(game, card)
        card.register_triggers(game)

        opp_instant = _make_instant("OpponentSpell")
        opp_instant.owner = p2
        opp_instant.controller = p2

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=opp_instant, player=p2, card=opp_instant, controller=p2
            ),
        )

        assert game.stack.is_empty(), (
            "Opponent's spell must not trigger the Hall's +1/+0 ability"
        )

    def test_trigger_resolution_boosts_power(self) -> None:
        """When the trigger resolves, the animated Hall's modified_power
        increases by 1."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        self._animate_card(game, card)
        card.register_triggers(game)

        instant = _make_instant("PowerBolt")
        instant.owner = p1
        instant.controller = p1

        power_before = getattr(card, "modified_power", getattr(card, "base_power", 2))

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=instant, player=p1, card=instant, controller=p1
            ),
        )

        # Resolve the trigger
        assert not game.stack.is_empty()
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        power_after = getattr(card, "modified_power", getattr(card, "base_power", 2))
        assert power_after == power_before + 1, (
            f"Expected power to increase by 1 (from {power_before} to "
            f"{power_before + 1}), got {power_after}"
        )

    def test_trigger_does_not_boost_toughness(self) -> None:
        """The +1/+0 effect must only boost power, not toughness."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        self._animate_card(game, card)
        card.register_triggers(game)

        instant = _make_instant("ToughnessCheck")
        instant.owner = p1
        instant.controller = p1

        toughness_before = getattr(
            card, "modified_toughness", getattr(card, "base_toughness", 4)
        )

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=instant, player=p1, card=instant, controller=p1
            ),
        )

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        toughness_after = getattr(
            card, "modified_toughness", getattr(card, "base_toughness", 4)
        )
        assert toughness_after == toughness_before, (
            "Toughness must not change from the +1/+0 trigger"
        )
