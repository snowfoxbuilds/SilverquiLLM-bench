"""Tests for SOS 257 — Great Hall of the Biblioplex.

TDD red-phase contract for a utility land with:

1. ``{T}: Add {C}.`` — a plain colorless mana ability.
2. ``{T}, Pay 1 life: Add one mana of any color. Spend this mana only to
   cast an instant or sorcery spell.`` — a life-paying any-color mana
   ability restricted to instants/sorceries.
3. ``{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
   with "Whenever you cast an instant or sorcery spell, this creature gets
   +1/+0 until end of turn." It's still a land.``

The card is a :class:`engine.card.Land`. Mana abilities are exposed through
``get_mana_abilities()`` (cost signature ``(game, source) -> bool``, effect
signature ``mana_produced(game) -> None``); the animate ability is exposed
through ``get_activated_abilities()`` (an :class:`ActivatedAbility` with a
``cost(game, source) -> bool`` and ``effect(game) -> None``).
"""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaType
from test_utils import create_game, set_board_state


def _hall(game, player_index: int = 0) -> GreatHallOfTheBiblioplex:
    """Return a Hall controlled by the indexed player, on its battlefield."""
    player = game.players[player_index]
    card = GreatHallOfTheBiblioplex(owner=player, controller=player)
    set_board_state(game, player_index, battlefield=[card])
    return card


class TestGreatHallProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_land(self) -> None:
        assert isinstance(GreatHallOfTheBiblioplex(owner=None), Land)

    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).name == "Great Hall of the Biblioplex"

    def test_is_land_card_type(self) -> None:
        assert CardType.LAND in GreatHallOfTheBiblioplex(owner=None).card_types

    def test_not_creature_by_default(self) -> None:
        """A freshly-made Hall is a plain land, not yet a creature."""
        assert CardType.CREATURE not in GreatHallOfTheBiblioplex(owner=None).card_types

    def test_land_cannot_be_cast(self) -> None:
        game = create_game()
        assert GreatHallOfTheBiblioplex(owner=None).can_cast(game) is False


class TestGreatHallManaAbilities:
    """get_mana_abilities() advertises both mana abilities."""

    def test_returns_two_mana_abilities(self) -> None:
        abilities = GreatHallOfTheBiblioplex(owner=None).get_mana_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) == 2

    def test_all_are_mana_ability_instances(self) -> None:
        for ab in GreatHallOfTheBiblioplex(owner=None).get_mana_abilities():
            assert isinstance(ab, ManaAbility)


class TestColorlessManaAbility:
    """{T}: Add {C}."""

    def test_taps_and_adds_colorless(self) -> None:
        game = create_game()
        card = _hall(game, 0)
        ability = card.get_mana_abilities()[0]
        assert ability.cost(game, card) is True
        assert card.is_tapped is True
        ability.mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) == 1

    def test_colorless_ability_cannot_be_used_while_tapped(self) -> None:
        game = create_game()
        card = _hall(game, 0)
        card.is_tapped = True
        ability = card.get_mana_abilities()[0]
        assert ability.cost(game, card) is False

    def test_colorless_ability_does_not_cost_life(self) -> None:
        game = create_game()
        card = _hall(game, 0)
        before = game.players[0].life
        ability = card.get_mana_abilities()[0]
        ability.cost(game, card)
        assert game.players[0].life == before


class TestAnyColorManaAbility:
    """{T}, Pay 1 life: Add one mana of any color (instant/sorcery only)."""

    def test_taps_and_pays_one_life(self) -> None:
        game = create_game()
        card = _hall(game, 0)
        before = game.players[0].life
        ability = card.get_mana_abilities()[1]
        assert ability.cost(game, card) is True
        assert card.is_tapped is True
        assert game.players[0].life == before - 1

    def test_produces_one_mana(self) -> None:
        """Resolving the any-color ability adds exactly one mana to the pool."""
        game = create_game()
        card = _hall(game, 0)
        ability = card.get_mana_abilities()[1]
        ability.cost(game, card)
        before_total = game.players[0].mana_pool.total()
        ability.mana_produced(game)
        assert game.players[0].mana_pool.total() == before_total + 1

    def test_can_produce_a_colored_mana(self) -> None:
        """The ability can produce a colored mana (any of the five colors)."""
        game = create_game()
        card = _hall(game, 0)
        ability = card.get_mana_abilities()[1]
        ability.cost(game, card)
        ability.mana_produced(game)
        pool = game.players[0].mana_pool
        colored = sum(
            pool.get(mt)
            for mt in (
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            )
        )
        assert colored == 1

    def test_any_color_ability_cannot_be_used_while_tapped(self) -> None:
        game = create_game()
        card = _hall(game, 0)
        card.is_tapped = True
        before = game.players[0].life
        ability = card.get_mana_abilities()[1]
        assert ability.cost(game, card) is False
        # A failed cost must not drain life.
        assert game.players[0].life == before


class TestAnimateAbility:
    """{5}: become a 2/4 Wizard creature."""

    def test_returns_one_activated_ability(self) -> None:
        abilities = GreatHallOfTheBiblioplex(owner=None).get_activated_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_cost_requires_five_generic_mana(self) -> None:
        """With fewer than 5 mana available the cost cannot be paid."""
        game = create_game()
        card = _hall(game, 0)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 4})
        ability = card.get_activated_abilities()[0]
        assert ability.cost(game, card) is False

    def test_cost_pays_five_generic_mana(self) -> None:
        game = create_game()
        card = _hall(game, 0)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        ability = card.get_activated_abilities()[0]
        assert ability.cost(game, card) is True
        assert game.players[0].mana_pool.total() == 0

    def test_effect_makes_it_a_creature(self) -> None:
        game = create_game()
        card = _hall(game, 0)
        ability = card.get_activated_abilities()[0]
        ability.effect(game)
        assert CardType.CREATURE in card.card_types

    def test_effect_sets_two_four_power_toughness(self) -> None:
        game = create_game()
        card = _hall(game, 0)
        ability = card.get_activated_abilities()[0]
        ability.effect(game)
        assert card.power == 2
        assert card.toughness == 4

    def test_effect_adds_wizard_subtype(self) -> None:
        game = create_game()
        card = _hall(game, 0)
        ability = card.get_activated_abilities()[0]
        ability.effect(game)
        assert "Wizard" in card.subtypes

    def test_remains_a_land_after_animation(self) -> None:
        """"It's still a land." — LAND type is retained."""
        game = create_game()
        card = _hall(game, 0)
        ability = card.get_activated_abilities()[0]
        ability.effect(game)
        assert CardType.LAND in card.card_types

    def test_animation_is_noop_when_already_a_creature(self) -> None:
        """"If this land isn't a creature" — second activation must not
        stack a second animation (it stays 2/4, not 4/8)."""
        game = create_game()
        card = _hall(game, 0)
        ability = card.get_activated_abilities()[0]
        ability.effect(game)
        # Already a creature now; activating again should be a no-op.
        ability.effect(game)
        assert card.power == 2
        assert card.toughness == 4


class TestAnimatedProwessTrigger:
    """The animated creature gets +1/+0 whenever its controller casts an
    instant or sorcery spell."""

    @staticmethod
    def _fire_spell_cast(game, controller) -> None:
        """Fire a SpellCastTriggeredEvent for an instant the controller casts
        and resolve every triggered ability it puts on the stack."""
        from engine.card import Instant
        from engine.events import SpellCastTriggeredEvent

        spell = Instant(name="Test Bolt", owner=controller, controller=controller)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell,
                card=spell,
                player=controller,
                controller=controller,
            ),
        )
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        if hasattr(game, "effect_manager") and hasattr(game.effect_manager, "apply_all"):
            game.effect_manager.apply_all(game)

    def test_casting_instant_pumps_animated_creature(self) -> None:
        game = create_game()
        card = _hall(game, 0)
        ability = card.get_activated_abilities()[0]
        ability.effect(game)
        card.register_triggers(game)

        base_power = card.power
        base_toughness = card.toughness
        self._fire_spell_cast(game, game.players[0])
        # +1/+0 until end of turn.
        assert card.power == base_power + 1
        assert card.toughness == base_toughness

    def test_animated_creature_pumps_once_per_spell(self) -> None:
        """Two instants cast in a turn give +2/+0 cumulatively (one trigger
        each)."""
        game = create_game()
        card = _hall(game, 0)
        ability = card.get_activated_abilities()[0]
        ability.effect(game)
        card.register_triggers(game)

        base_power = card.power
        self._fire_spell_cast(game, game.players[0])
        self._fire_spell_cast(game, game.players[0])
        assert card.power == base_power + 2

    def test_no_pump_before_animation(self) -> None:
        """Before becoming a creature, the land's prowess-style trigger must
        not fire / must leave it a non-creature with no power bonus."""
        game = create_game()
        card = _hall(game, 0)
        # Do NOT animate. Register triggers as a battlefield permanent.
        card.register_triggers(game)
        self._fire_spell_cast(game, game.players[0])
        # Still a non-creature land.
        assert CardType.CREATURE not in card.card_types
