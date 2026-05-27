"""Tests for sos_257 — Great Hall of the Biblioplex.

Card spec:
  Mana cost: (none — it's a land)
  Type: Land
  Oracle text:
    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
      an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
      "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
      until end of turn." It's still a land.

Requirements tested:
  1. Static properties: name, no mana cost, LAND type, not initially a creature.
  2. Two mana abilities: colorless tap and colored tap+life.
  3. Colorless ability: taps the land and adds {C} to the pool.
  4. Colorless ability: fails if already tapped.
  5. Colored ability: taps the land, deducts 1 life, adds one colored mana.
  6. Colored ability: fails if already tapped.
  7. Activated ability {5}: transforms non-creature land into 2/4 Wizard.
  8. Transformation adds CREATURE type but retains LAND type.
  9. Transformation adds "Wizard" subtype.
  10. Transformation sets base_power=2, base_toughness=4.
  11. Transformation is a no-op when card is already a creature.
  12. Activated ability requires 5 generic mana as cost.
  13. After becoming a creature, registers trigger for SpellCastTriggeredEvent.
  14. Trigger condition: true for instant cast by controller while on battlefield.
  15. Trigger condition: true for sorcery cast by controller while on battlefield.
  16. Trigger condition: false for non-instant/sorcery spells.
  17. Trigger condition: false for spells cast by opponent.
  18. Trigger fires and boosts power by +1/+0 when instant cast.
"""

from __future__ import annotations

from engine.card import ActivatedAbility, Creature, Instant, Land, ManaAbility, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestGreatHallProperties:
    """Static card data should match the sos_257 spec."""

    def test_is_land(self) -> None:
        assert isinstance(GreatHallOfTheBiblioplex(owner=None), Land)

    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).name == "Great Hall of the Biblioplex"

    def test_mana_cost_is_empty(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.mana_cost == ManaCost()

    def test_has_land_card_type(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_is_not_a_creature_initially(self) -> None:
        """Lands start as non-creatures; {5} is needed to animate it."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.CREATURE not in card.card_types


# ---------------------------------------------------------------------------
# Mana abilities
# ---------------------------------------------------------------------------


class TestGreatHallManaAbilities:
    """get_mana_abilities() must return exactly two mana abilities."""

    def test_has_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 2

    def test_all_mana_ability_instances(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        for ability in card.get_mana_abilities():
            assert isinstance(ability, ManaAbility)


class TestGreatHallColorlessManaAbility:
    """{T}: Add {C} — the first mana ability."""

    def test_tapping_adds_colorless_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        abilities = card.get_mana_abilities()
        # First ability is {T}: Add {C}
        colorless_ability = abilities[0]
        before = p1.mana_pool.get(ManaType.COLORLESS)
        colorless_ability.cost(game, card)
        colorless_ability.mana_produced(game)
        after = p1.mana_pool.get(ManaType.COLORLESS)
        assert after == before + 1

    def test_tapping_taps_the_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        abilities = card.get_mana_abilities()
        colorless_ability = abilities[0]
        result = colorless_ability.cost(game, card)
        assert result is True
        assert card.is_tapped is True

    def test_colorless_ability_fails_when_already_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True
        abilities = card.get_mana_abilities()
        colorless_ability = abilities[0]
        result = colorless_ability.cost(game, card)
        assert result is False


class TestGreatHallColoredManaAbility:
    """{T}, Pay 1 life: Add one mana of any color."""

    def test_colored_ability_deducts_one_life(self) -> None:
        """Paying the cost reduces the controller's life by 1."""
        # Script the color choice so choose() doesn't raise ScriptExhaustedError.
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        abilities = card.get_mana_abilities()
        # Second ability is the life-cost ability
        life_ability = abilities[1]
        life_before = p1.life
        life_ability.cost(game, card)
        life_ability.mana_produced(game)
        assert p1.life == life_before - 1

    def test_colored_ability_taps_the_land(self) -> None:
        """The tap portion of {T}, Pay 1 life also taps the land."""
        game = create_game(scripts=([ManaType.RED], []))
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        abilities = card.get_mana_abilities()
        life_ability = abilities[1]
        result = life_ability.cost(game, card)
        assert result is True
        assert card.is_tapped is True

    def test_colored_ability_fails_when_already_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True
        abilities = card.get_mana_abilities()
        life_ability = abilities[1]
        result = life_ability.cost(game, card)
        assert result is False

    def test_colored_ability_adds_one_colored_mana(self) -> None:
        """Using the ability adds exactly 1 colored mana to the pool."""
        game = create_game(scripts=([ManaType.GREEN], []))
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        abilities = card.get_mana_abilities()
        life_ability = abilities[1]
        pool_before = p1.mana_pool.total()
        life_ability.cost(game, card)
        life_ability.mana_produced(game)
        # Total mana pool increased by exactly 1
        assert p1.mana_pool.total() == pool_before + 1


# ---------------------------------------------------------------------------
# Activated ability — {5}: become a 2/4 Wizard creature-land
# ---------------------------------------------------------------------------


class TestGreatHallCreatureAbility:
    """{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature."""

    def test_has_activated_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_activated_ability_is_activated_ability_instance(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        for ability in card.get_activated_abilities():
            assert isinstance(ability, ActivatedAbility)

    def test_creature_ability_requires_five_mana(self) -> None:
        """Cost requires {5} — activating without mana should fail."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        # No mana in pool
        assert p1.mana_pool.total() == 0
        abilities = card.get_activated_abilities()
        creature_ability = abilities[0]
        result = creature_ability.cost(game, card)
        assert result is False

    def test_creature_ability_cost_succeeds_with_five_mana(self) -> None:
        """Cost succeeds when exactly 5 generic mana is available."""
        from test_utils import set_board_state
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        abilities = card.get_activated_abilities()
        creature_ability = abilities[0]
        result = creature_ability.cost(game, card)
        assert result is True

    def test_creature_ability_adds_creature_type(self) -> None:
        """After activation, the land gains CREATURE card type."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        abilities = card.get_activated_abilities()
        creature_ability = abilities[0]
        creature_ability.cost(game, card)
        creature_ability.effect(game)
        assert CardType.CREATURE in card.card_types

    def test_creature_ability_retains_land_type(self) -> None:
        """After activation, the card is still a land (it's still a land)."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        abilities = card.get_activated_abilities()
        creature_ability = abilities[0]
        creature_ability.cost(game, card)
        creature_ability.effect(game)
        assert CardType.LAND in card.card_types

    def test_creature_ability_adds_wizard_subtype(self) -> None:
        """After activation, the card gains the Wizard subtype."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        abilities = card.get_activated_abilities()
        creature_ability = abilities[0]
        creature_ability.cost(game, card)
        creature_ability.effect(game)
        assert "Wizard" in card.subtypes

    def test_creature_ability_sets_power_2_toughness_4(self) -> None:
        """After activation, the creature is a 2/4."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        abilities = card.get_activated_abilities()
        creature_ability = abilities[0]
        creature_ability.cost(game, card)
        creature_ability.effect(game)
        # After animation, power=2 and toughness=4
        assert getattr(card, "base_power", None) == 2 or getattr(card, "modified_power", None) == 2
        assert getattr(card, "base_toughness", None) == 4 or getattr(card, "modified_toughness", None) == 4

    def test_creature_ability_is_noop_if_already_a_creature(self) -> None:
        """If the land is already a creature, the {5} ability does nothing new."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 10})
        abilities = card.get_activated_abilities()
        creature_ability = abilities[0]
        # First activation: should work
        creature_ability.cost(game, card)
        creature_ability.effect(game)
        assert CardType.CREATURE in card.card_types
        # Second activation: cost should return False since it's already a creature
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        result = creature_ability.cost(game, card)
        assert result is False


# ---------------------------------------------------------------------------
# Triggered ability — SpellCastTriggeredEvent → +1/+0
# ---------------------------------------------------------------------------


class TestGreatHallWizardTrigger:
    """After becoming a creature, registers a trigger that gives +1/+0 on instant/sorcery cast."""

    def _activate_creature_form(self, game, card) -> None:
        """Helper: pay cost and fire effect to animate the land into a creature."""
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        abilities = card.get_activated_abilities()
        creature_ability = abilities[0]
        creature_ability.cost(game, card)
        creature_ability.effect(game)

    def _get_spell_cast_trigger(self, game, card):
        """Return the SpellCastTriggeredEvent trigger registered by card."""
        triggers = game.trigger_manager.get_triggers_for_source(card)
        for t in triggers:
            if t.event_type is SpellCastTriggeredEvent or (
                isinstance(t.event_type, type)
                and issubclass(SpellCastTriggeredEvent, t.event_type)
            ):
                return t
        return None

    def test_becoming_creature_registers_spell_cast_trigger(self) -> None:
        """Activating the {5} ability registers a SpellCastTriggeredEvent trigger."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        self._activate_creature_form(game, card)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

    def test_trigger_condition_true_for_instant_cast_by_controller(self) -> None:
        """Trigger condition returns True for an instant cast by the controller."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        self._activate_creature_form(game, card)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True

    def test_trigger_condition_true_for_sorcery_cast_by_controller(self) -> None:
        """Trigger condition returns True for a sorcery cast by the controller."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        self._activate_creature_form(game, card)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=sorcery, player=p1, controller=p1)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True

    def test_trigger_condition_false_for_creature_spell(self) -> None:
        """Trigger condition returns False for non-instant/sorcery spells."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        self._activate_creature_form(game, card)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        creature_spell = Creature(
            name="Test Creature", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        event = SpellCastTriggeredEvent(spell=creature_spell, player=p1, controller=p1)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False

    def test_trigger_condition_false_for_opponent_spell(self) -> None:
        """Trigger condition returns False when the spell is cast by an opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        self._activate_creature_form(game, card)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        instant = Instant(name="Opponent Instant", owner=p2, controller=p2)
        event = SpellCastTriggeredEvent(spell=instant, player=p2, controller=p2)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False

    def test_trigger_fires_pushes_to_stack_on_instant(self) -> None:
        """Firing SpellCastTriggeredEvent with instant pushes trigger onto stack."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        self._activate_creature_form(game, card)
        card.register_triggers(game)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) > stack_before

    def test_trigger_effect_boosts_power_by_one(self) -> None:
        """When the trigger resolves, the creature's power increases by +1/+0."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        self._activate_creature_form(game, card)
        card.register_triggers(game)

        power_before = getattr(card, "modified_power", getattr(card, "base_power", 2))
        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)
        # Resolve the trigger from the stack
        stack_item = game.stack[-1]
        stack_item.on_resolve(game)
        power_after = getattr(card, "modified_power", getattr(card, "base_power", 2))
        assert power_after == power_before + 1

    def test_trigger_does_not_fire_for_sorcery_without_activation(self) -> None:
        """If the land was never activated, no trigger fires for spells."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        # Do NOT activate — the land is still a non-creature
        card.register_triggers(game)

        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=sorcery, player=p1, controller=p1)
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        # No trigger should have been pushed since it's not a creature yet
        assert len(game.stack) == stack_before
