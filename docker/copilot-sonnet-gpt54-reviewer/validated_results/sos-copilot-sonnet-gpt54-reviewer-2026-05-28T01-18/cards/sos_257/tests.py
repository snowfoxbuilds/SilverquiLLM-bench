"""Tests for sos_257 — Great Hall of the Biblioplex.

Tests cover:
  1. Basic card properties (name, Land type, no mana cost, no P/T).
  2. {T}: Add {C} mana ability.
  3. {T}, Pay 1 life: Add one mana of any color mana ability.
  4. {5} animation: becomes 2/4 Wizard creature-land.
  5. Animation guard: only if not already a creature.
  6. Pump trigger registration and fire on instant/sorcery cast.
  7. Pump wearing off at end of turn.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Land
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import advance_to_phase, create_game, set_board_state
from engine.types import Phase, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card() -> GreatHallOfTheBiblioplex:
    """Create a card instance with no owner (for property tests)."""
    return GreatHallOfTheBiblioplex(owner=None)


def _make_game_with_card() -> tuple[Any, Any, GreatHallOfTheBiblioplex]:
    """Create a game with the card on p1's battlefield; return (game, p1, card)."""
    game = create_game()
    p1 = game.players[0]
    card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
    game.get_battlefield(p1).add(card)
    return game, p1, card


# ---------------------------------------------------------------------------
# 1. Basic properties
# ---------------------------------------------------------------------------

class TestGreatHallProperties:
    """Static card data must match the sos_257 spec."""

    def test_name(self) -> None:
        assert _make_card().name == "Great Hall of the Biblioplex"

    def test_is_land_subclass(self) -> None:
        assert isinstance(_make_card(), Land)

    def test_has_land_card_type(self) -> None:
        assert CardType.LAND in _make_card().card_types

    def test_no_mana_cost(self) -> None:
        """Lands have no mana cost — the mana_cost field should be empty."""
        mc = _make_card().mana_cost
        assert mc == ManaCost()

    def test_not_creature_by_default(self) -> None:
        """The card is not a creature until animated."""
        card = _make_card()
        assert CardType.CREATURE not in card.card_types

    def test_no_power_toughness_before_animation(self) -> None:
        """Before animation the card has no creature P/T attributes,
        or they are None / absent — it is not a creature."""
        card = _make_card()
        # Land base class has no base_power/base_toughness;
        # if the attribute exists it should signal the 'not yet animated' state.
        has_power = hasattr(card, "base_power")
        if has_power:
            # If implemented on the class, unanimate state should show 0 or None
            assert card.base_power in (0, None)


# ---------------------------------------------------------------------------
# 2. {T}: Add {C} mana ability
# ---------------------------------------------------------------------------

class TestGreatHallColorlessMana:
    """{T}: Add {C}."""

    def test_has_at_least_one_mana_ability(self) -> None:
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_colorless_mana_ability_exists(self) -> None:
        """At least one mana ability should produce colorless (C) mana."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        descriptions = [a.description for a in abilities]
        has_colorless = any("{C}" in d or "colorless" in d.lower() for d in descriptions)
        assert has_colorless, f"No colorless mana ability found; descriptions: {descriptions}"

    def test_colorless_ability_taps_land(self) -> None:
        """The tap cost of the colorless ability taps the land."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        # Find the colorless ability
        colorless_ability = next(
            (a for a in abilities if "{C}" in a.description or "colorless" in a.description.lower()),
            None,
        )
        assert colorless_ability is not None, "No colorless mana ability found"
        card.is_tapped = False
        colorless_ability.cost(game, card)
        assert card.is_tapped is True

    def test_colorless_ability_adds_colorless_mana(self) -> None:
        """After the mana effect fires, the controller has colorless mana."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        colorless_ability = next(
            (a for a in abilities if "{C}" in a.description or "colorless" in a.description.lower()),
            None,
        )
        assert colorless_ability is not None
        card.is_tapped = False
        colorless_ability.cost(game, card)
        before = p1.mana_pool.total()
        colorless_ability.mana_produced(game)
        after = p1.mana_pool.total()
        assert after == before + 1
        assert p1.mana_pool.get(ManaType.COLORLESS) >= 1

    def test_colorless_ability_cannot_activate_when_already_tapped(self) -> None:
        """The tap cost should return False (or not tap) when already tapped."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        colorless_ability = next(
            (a for a in abilities if "{C}" in a.description or "colorless" in a.description.lower()),
            None,
        )
        assert colorless_ability is not None
        card.is_tapped = True
        result = colorless_ability.cost(game, card)
        # Should return False and leave tapped (not double-tap)
        assert result is False


# ---------------------------------------------------------------------------
# 3. {T}, Pay 1 life: Add one mana of any color
# ---------------------------------------------------------------------------

class TestGreatHallColoredMana:
    """{T}, Pay 1 life: Add one mana of any color."""

    def test_has_at_least_two_mana_abilities(self) -> None:
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 2

    def test_colored_mana_ability_exists(self) -> None:
        """There should be an ability that describes paying 1 life for colored mana."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        descriptions = [a.description for a in abilities]
        has_life = any("life" in d.lower() or "1 life" in d for d in descriptions)
        assert has_life, f"No life-paying mana ability found; descriptions: {descriptions}"

    def test_colored_mana_ability_taps_land(self) -> None:
        """The {T}, Pay 1 life ability taps the land."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        life_ability = next(
            (a for a in abilities if "life" in a.description.lower()),
            None,
        )
        assert life_ability is not None, "No life-paying mana ability found"
        card.is_tapped = False
        p1.life = 20
        life_ability.cost(game, card)
        assert card.is_tapped is True

    def test_colored_mana_ability_pays_one_life(self) -> None:
        """The {T}, Pay 1 life ability deducts exactly 1 life from the controller."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        life_ability = next(
            (a for a in abilities if "life" in a.description.lower()),
            None,
        )
        assert life_ability is not None
        card.is_tapped = False
        p1.life = 20
        life_ability.cost(game, card)
        assert p1.life == 19

    def test_colored_mana_ability_produces_colored_mana(self) -> None:
        """The colored mana ability should add at least one colored mana to the pool."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        life_ability = next(
            (a for a in abilities if "life" in a.description.lower()),
            None,
        )
        assert life_ability is not None
        card.is_tapped = False
        p1.life = 20
        life_ability.cost(game, card)
        before_total = p1.mana_pool.total()
        life_ability.mana_produced(game)
        after_total = p1.mana_pool.total()
        assert after_total == before_total + 1
        # It should be a colored mana (not colorless)
        colored_total = sum(
            p1.mana_pool.get(mt)
            for mt in (ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN)
        )
        assert colored_total >= 1

    def test_colored_mana_ability_cannot_activate_when_tapped(self) -> None:
        """The {T}, Pay 1 life ability can't fire when the land is already tapped."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_mana_abilities()
        life_ability = next(
            (a for a in abilities if "life" in a.description.lower()),
            None,
        )
        assert life_ability is not None
        card.is_tapped = True
        p1.life = 20
        result = life_ability.cost(game, card)
        assert result is False
        # Life should not be lost since cost was rejected
        assert p1.life == 20


# ---------------------------------------------------------------------------
# 4. {5} Animation: becomes 2/4 Wizard creature-land
# ---------------------------------------------------------------------------

class TestGreatHallAnimation:
    """{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature-land."""

    def test_has_animation_activated_ability(self) -> None:
        """The card should expose an activated ability for animation."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_animation_ability_has_five_cost(self) -> None:
        """The animation ability costs {5}."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_activated_abilities()
        has_five = any("{5}" in getattr(a, "description", "") or "5" in getattr(a, "description", "") for a in abilities)
        assert has_five, f"No {5} ability found; descriptions: {[a.description for a in abilities]}"

    def test_animation_adds_creature_type(self) -> None:
        """After the animation effect fires, the land gains CREATURE type."""
        game, p1, card = _make_game_with_card()
        assert CardType.CREATURE not in card.card_types
        abilities = card.get_activated_abilities()
        anim_ability = abilities[0]
        anim_ability.effect(game)
        assert CardType.CREATURE in card.card_types

    def test_animation_preserves_land_type(self) -> None:
        """After animation the card is still a Land."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_activated_abilities()
        anim_ability = abilities[0]
        anim_ability.effect(game)
        assert CardType.LAND in card.card_types

    def test_animation_power_is_2(self) -> None:
        """After animation, power (base or modified) should be 2."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_activated_abilities()
        anim_ability = abilities[0]
        anim_ability.effect(game)
        power = getattr(card, "base_power", None) or getattr(card, "modified_power", None)
        assert power == 2

    def test_animation_toughness_is_4(self) -> None:
        """After animation, toughness (base or modified) should be 4."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_activated_abilities()
        anim_ability = abilities[0]
        anim_ability.effect(game)
        toughness = getattr(card, "base_toughness", None) or getattr(card, "modified_toughness", None)
        assert toughness == 4

    def test_animation_adds_wizard_subtype(self) -> None:
        """After animation, 'Wizard' appears in the card's subtypes."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_activated_abilities()
        anim_ability = abilities[0]
        anim_ability.effect(game)
        assert "Wizard" in card.subtypes

    def test_animation_guard_skips_if_already_creature(self) -> None:
        """If the land is already a creature, the animation ability does nothing."""
        game, p1, card = _make_game_with_card()
        abilities = card.get_activated_abilities()
        anim_ability = abilities[0]

        # Animate once — becomes a creature
        anim_ability.effect(game)
        assert CardType.CREATURE in card.card_types

        # Record power/toughness after first animation
        power_after_first = getattr(card, "base_power", None) or getattr(card, "modified_power", None)

        # Try to animate again — should be a no-op
        anim_ability.effect(game)
        power_after_second = getattr(card, "base_power", None) or getattr(card, "modified_power", None)
        assert power_after_first == power_after_second

    def test_animation_does_not_change_land_subtype(self) -> None:
        """Animation should not strip any existing land subtypes (e.g. Plains)."""
        game, p1, card = _make_game_with_card()
        card.subtypes.add("School")  # hypothetical subtype
        abilities = card.get_activated_abilities()
        anim_ability = abilities[0]
        anim_ability.effect(game)
        assert "School" in card.subtypes


# ---------------------------------------------------------------------------
# 5. Pump trigger: registers and fires on instant/sorcery
# ---------------------------------------------------------------------------

class TestGreatHallPumpTrigger:
    """'Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn.'"""

    def _animate(self, game: Any, card: GreatHallOfTheBiblioplex) -> None:
        """Animate the card and register triggers."""
        abilities = card.get_activated_abilities()
        anim_ability = abilities[0]
        anim_ability.effect(game)
        card.register_triggers(game)

    def test_register_triggers_adds_trigger_when_animated(self) -> None:
        """After animation, register_triggers should add at least one trigger."""
        game, p1, card = _make_game_with_card()
        self._animate(game, card)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1

    def test_trigger_watches_spell_cast_event(self) -> None:
        """The registered trigger should respond to SpellCastTriggeredEvent."""
        game, p1, card = _make_game_with_card()
        self._animate(game, card)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        event_types = {t.event_type for t in triggers}
        assert SpellCastTriggeredEvent in event_types

    def test_trigger_fires_for_instant_spell(self) -> None:
        """Casting an instant puts the pump trigger on the stack."""
        from engine.card import Instant

        game, p1, card = _make_game_with_card()
        self._animate(game, card)

        instant_spell = Instant(owner=p1, controller=p1)
        instant_spell.card_types = {CardType.INSTANT}

        stack_before = game.stack.size()
        event = SpellCastTriggeredEvent(
            spell=instant_spell,
            player=p1,
            controller=p1,
        )
        game.trigger_manager.fire_event(game, event)
        assert game.stack.size() > stack_before

    def test_trigger_fires_for_sorcery_spell(self) -> None:
        """Casting a sorcery puts the pump trigger on the stack."""
        from engine.card import Sorcery

        game, p1, card = _make_game_with_card()
        self._animate(game, card)

        sorcery_spell = Sorcery(owner=p1, controller=p1)
        sorcery_spell.card_types = {CardType.SORCERY}

        stack_before = game.stack.size()
        event = SpellCastTriggeredEvent(
            spell=sorcery_spell,
            player=p1,
            controller=p1,
        )
        game.trigger_manager.fire_event(game, event)
        assert game.stack.size() > stack_before

    def test_trigger_condition_rejects_creature_spell(self) -> None:
        """A creature spell does NOT trigger the pump."""
        from engine.card import Creature

        game, p1, card = _make_game_with_card()
        self._animate(game, card)

        creature_spell = Creature(name="Test Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        creature_spell.card_types = {CardType.CREATURE}

        stack_before = game.stack.size()
        event = SpellCastTriggeredEvent(
            spell=creature_spell,
            player=p1,
            controller=p1,
        )
        game.trigger_manager.fire_event(game, event)
        assert game.stack.size() == stack_before

    def test_pump_increases_modified_power_by_one(self) -> None:
        """When the trigger resolves, the creature's power increases by +1/+0."""
        from engine.card import Instant

        game, p1, card = _make_game_with_card()
        self._animate(game, card)

        instant_spell = Instant(owner=p1, controller=p1)
        instant_spell.card_types = {CardType.INSTANT}

        power_before = getattr(card, "modified_power", getattr(card, "base_power", 0))
        event = SpellCastTriggeredEvent(
            spell=instant_spell,
            player=p1,
            controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        # Resolve the trigger from the stack
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        power_after = getattr(card, "modified_power", getattr(card, "base_power", 0))
        assert power_after == power_before + 1

    def test_pump_does_not_affect_toughness(self) -> None:
        """The pump is +1/+0; toughness should stay at 4."""
        from engine.card import Instant

        game, p1, card = _make_game_with_card()
        self._animate(game, card)

        instant_spell = Instant(owner=p1, controller=p1)
        instant_spell.card_types = {CardType.INSTANT}

        event = SpellCastTriggeredEvent(
            spell=instant_spell,
            player=p1,
            controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        toughness = getattr(card, "modified_toughness", getattr(card, "base_toughness", 4))
        assert toughness == 4

    def test_pump_stacks_for_multiple_spells(self) -> None:
        """Casting two instants in a turn gives +2/+0."""
        from engine.card import Instant

        game, p1, card = _make_game_with_card()
        self._animate(game, card)

        power_before = getattr(card, "modified_power", getattr(card, "base_power", 0))

        for _ in range(2):
            spell = Instant(owner=p1, controller=p1)
            spell.card_types = {CardType.INSTANT}
            event = SpellCastTriggeredEvent(spell=spell, player=p1, controller=p1)
            game.trigger_manager.fire_event(game, event)

        # Resolve all triggers
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        power_after = getattr(card, "modified_power", getattr(card, "base_power", 0))
        assert power_after == power_before + 2


# ---------------------------------------------------------------------------
# 6. Pump wears off at end of turn
# ---------------------------------------------------------------------------

class TestGreatHallPumpEOT:
    """The +1/+0 pump expires at end of turn (cleanup step)."""

    def test_pump_wears_off_at_end_of_turn(self) -> None:
        """After advancing to CLEANUP, the pump bonus should be gone."""
        from engine.card import Instant

        game, p1, card = _make_game_with_card()
        abilities = card.get_activated_abilities()
        abilities[0].effect(game)
        card.register_triggers(game)

        instant_spell = Instant(owner=p1, controller=p1)
        instant_spell.card_types = {CardType.INSTANT}
        event = SpellCastTriggeredEvent(spell=instant_spell, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)

        # Resolve the pump trigger
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        pumped_power = getattr(card, "modified_power", getattr(card, "base_power", 0))
        assert pumped_power == 3  # base 2 + 1

        # Advance to cleanup — until-end-of-turn effects expire
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)

        reset_power = getattr(card, "modified_power", getattr(card, "base_power", 0))
        assert reset_power == 2  # back to base 2/4

    def test_no_trigger_registered_before_animation(self) -> None:
        """Before animation, register_triggers adds no SpellCastTriggeredEvent triggers."""
        game, p1, card = _make_game_with_card()
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        spell_cast_triggers = [t for t in triggers if t.event_type is SpellCastTriggeredEvent]
        assert len(spell_cast_triggers) == 0
