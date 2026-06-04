"""Tests for SOS 257 — Great Hall of the Biblioplex.

Great Hall of the Biblioplex — Land:

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
        cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
        with "Whenever you cast an instant or sorcery spell, this creature
        gets +1/+0 until end of turn." It's still a land.

The card has four distinct behavioural clauses:

1. **Static land identity** — a colorless Land with no mana cost; not a
   creature (no power/toughness) until animated.
2. **{T}: Add {C}** — a mana ability that taps the land and adds one
   colorless mana to the controller's pool.
3. **{T}, Pay 1 life: Add one mana of any color** — a mana ability that
   taps the land, pays 1 life, and adds one mana of a chosen color.
4. **{5}: becomes a 2/4 Wizard creature** — an activated ability gated on
   "If this land isn't a creature": it turns the land into a 2/4 Wizard
   creature that is still a land and gains the prowess-like cast trigger.

These tests follow the FDN reference-test style: static-property checks plus
behavioural checks that drive the card's public hooks (``get_mana_abilities``
/ ``get_activated_abilities`` / ``register_triggers``) through the real
engine ability/trigger surfaces.

CONTRACT NOTES for the Implementer (asserted below):
- Class name: ``GreatHallOfTheBiblioplex`` subclassing ``engine.card.Land``.
- ``mana_cost`` is empty (``ManaCost()``); ``colors == []``.
- ``get_mana_abilities()`` returns exactly two ``ManaAbility`` objects:
  index 0 is the ``{T}: Add {C}`` ability; index 1 is the
  ``{T}, Pay 1 life: Add one mana of any color`` ability. Each
  ``ManaAbility.cost`` is invoked as ``cost(game, source)`` and taps the
  land (the life-payment ability also pays 1 life); ``mana_produced`` is
  invoked as ``mana_produced(game)`` and adds one mana to the controller's
  pool. The any-color ability reads the chosen color via the controller's
  ``choose`` method (scripted as a ``ManaType`` in these tests).
- ``get_activated_abilities()`` returns the ``{5}`` animation ability
  (an ``ActivatedAbility`` invoked through ``engine.abilities.activate_ability``).
  After it resolves, the land is also a 2/4 creature with subtype "Wizard",
  ``power == 2`` and ``toughness == 4``, and is still a land. The gate
  "if this land isn't a creature" makes a second activation a no-op for the
  type/P/T change.
- The animated land registers a ``SpellCastTriggeredEvent`` trigger
  (via ``register_triggers``) whose effect pumps the land +1/+0 when its
  controller casts an instant or sorcery spell.
"""

from __future__ import annotations

import pytest

from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Land, ManaAbility, ActivatedAbility, Instant, Sorcery, Creature
from engine.casting import CastingError, cast_spell
from engine.events import SpellCastTriggeredEvent
from engine.mana import RESTRICTION_INSTANT_SORCERY
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hall_on_battlefield(game, player_index=0):
    """Put a Great Hall on *player_index*'s battlefield and return it."""
    hall = GreatHallOfTheBiblioplex(owner=None)
    set_board_state(game, player_index, battlefield=[hall])
    return hall


def _mana_ability_for(hall, *, description_contains):
    """Return the ManaAbility whose description contains *description_contains*.

    Falls back to None when no matching ability is found.
    """
    for ability in hall.get_mana_abilities():
        desc = getattr(ability, "description", "") or ""
        if description_contains in desc:
            return ability
    return None


def _animation_ability(hall):
    """Return the single ``{5}`` animation ActivatedAbility."""
    abilities = hall.get_activated_abilities()
    assert abilities, "Great Hall should expose at least one activated ability"
    return abilities[0]


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestGreatHallProperties:
    """Static card data should match the SOS 257 spec."""

    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).name == "Great Hall of the Biblioplex"

    def test_is_a_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types

    def test_has_no_mana_cost(self) -> None:
        """Lands have no mana cost."""
        assert GreatHallOfTheBiblioplex(owner=None).mana_cost == ManaCost()

    def test_is_not_a_creature_initially(self) -> None:
        """Until the {5} ability resolves, it is a plain land, not a creature."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.CREATURE not in card.card_types

    def test_colorless(self) -> None:
        """The card's colors are empty (it is colorless)."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert list(getattr(card, "colors", [])) == []

    def test_cannot_be_cast(self) -> None:
        """Lands are played, not cast — ``can_cast`` is False."""
        game = create_game()
        card = GreatHallOfTheBiblioplex(owner=game.players[0])
        assert card.can_cast(game) is False

    def test_starts_untapped(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).is_tapped is False


# ---------------------------------------------------------------------------
# {T}: Add {C}
# ---------------------------------------------------------------------------

class TestColorlessManaAbility:
    """{T}: Add {C} — taps the land and adds one colorless mana."""

    def test_exposes_two_mana_abilities(self) -> None:
        """The land has two distinct mana abilities ({C} and any-color)."""
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert len(hall.get_mana_abilities()) == 2

    def test_mana_abilities_are_mana_ability_instances(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        for ability in hall.get_mana_abilities():
            assert isinstance(ability, ManaAbility)

    def test_colorless_ability_adds_one_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        ability = _mana_ability_for(hall, description_contains="{C}")
        assert ability is not None, "Expected a {T}: Add {C} mana ability"

        before = p1.mana_pool.get(ManaType.COLORLESS)
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == before + 1

    def test_colorless_ability_taps_the_land(self) -> None:
        game = create_game()
        hall = _hall_on_battlefield(game, 0)
        ability = _mana_ability_for(hall, description_contains="{C}")
        assert ability.cost(game, hall) is True
        assert hall.is_tapped is True

    def test_colorless_ability_cost_fails_when_tapped(self) -> None:
        """A tapped land cannot pay the {T} cost again."""
        game = create_game()
        hall = _hall_on_battlefield(game, 0)
        hall.is_tapped = True
        ability = _mana_ability_for(hall, description_contains="{C}")
        assert ability.cost(game, hall) is False

    def test_colorless_ability_only_adds_colorless(self) -> None:
        """The {C} ability must not add any colored mana."""
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        ability = _mana_ability_for(hall, description_contains="{C}")
        ability.cost(game, hall)
        ability.mana_produced(game)
        for mt in (ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                   ManaType.RED, ManaType.GREEN):
            assert p1.mana_pool.get(mt) == 0


# ---------------------------------------------------------------------------
# {T}, Pay 1 life: Add one mana of any color
# ---------------------------------------------------------------------------

class TestAnyColorManaAbility:
    """{T}, Pay 1 life: Add one mana of any color."""

    def test_any_color_ability_exists(self) -> None:
        """There is a mana ability that pays life for any color."""
        hall = GreatHallOfTheBiblioplex(owner=None)
        # The any-color ability is the one that is NOT the plain {C} ability.
        abilities = hall.get_mana_abilities()
        descs = [getattr(a, "description", "") or "" for a in abilities]
        assert any("life" in d.lower() or "any color" in d.lower() for d in descs)

    def test_any_color_pays_one_life(self) -> None:
        """Activating the ability deducts exactly 1 life from the controller."""
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        p1.life = 20
        hall = _hall_on_battlefield(game, 0)
        ability = _mana_ability_for(hall, description_contains="life")
        if ability is None:  # tolerate a description that says "any color"
            ability = _mana_ability_for(hall, description_contains="any color")
        assert ability is not None

        assert ability.cost(game, hall) is True
        assert p1.life == 19

    def test_any_color_taps_the_land(self) -> None:
        game = create_game(scripts=([ManaType.RED], []))
        hall = _hall_on_battlefield(game, 0)
        ability = _mana_ability_for(hall, description_contains="life") \
            or _mana_ability_for(hall, description_contains="any color")
        assert ability is not None
        assert ability.cost(game, hall) is True
        assert hall.is_tapped is True

    def test_any_color_adds_chosen_color(self) -> None:
        """The mana added matches the controller's chosen color."""
        game = create_game(scripts=([ManaType.GREEN], []))
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        ability = _mana_ability_for(hall, description_contains="life") \
            or _mana_ability_for(hall, description_contains="any color")
        assert ability is not None

        before = p1.mana_pool.get(ManaType.GREEN)
        ability.cost(game, hall)
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.GREEN) == before + 1

    def test_any_color_adds_exactly_one_mana(self) -> None:
        """Only a single mana is produced regardless of color chosen."""
        game = create_game(scripts=([ManaType.WHITE], []))
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        ability = _mana_ability_for(hall, description_contains="life") \
            or _mana_ability_for(hall, description_contains="any color")
        assert ability is not None
        ability.cost(game, hall)
        ability.mana_produced(game)
        assert p1.mana_pool.total() == 1

    def test_any_color_cost_fails_when_tapped(self) -> None:
        """A tapped land cannot pay the {T} portion of the cost."""
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        p1.life = 20
        hall = _hall_on_battlefield(game, 0)
        hall.is_tapped = True
        ability = _mana_ability_for(hall, description_contains="life") \
            or _mana_ability_for(hall, description_contains="any color")
        assert ability is not None
        assert ability.cost(game, hall) is False
        # Life should not have been paid if the tap could not happen.
        assert p1.life == 20


# ---------------------------------------------------------------------------
# {5}: becomes a 2/4 Wizard creature
# ---------------------------------------------------------------------------

class TestAnimationAbility:
    """{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    that's still a land."""

    def test_exposes_one_activated_ability(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        abilities = hall.get_activated_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_animation_requires_five_mana(self) -> None:
        """With only 4 mana the {5} cost cannot be paid."""
        game = create_game()
        hall = _hall_on_battlefield(game, 0)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 4})
        ability = _animation_ability(hall)
        assert ability.cost(game, hall) is False

    def test_animation_pays_five_mana(self) -> None:
        """Paying {5} deducts five mana from the controller's pool."""
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        ability = _animation_ability(hall)
        assert ability.cost(game, hall) is True
        assert p1.mana_pool.total() == 0

    def test_becomes_creature(self) -> None:
        """After the effect, the land has the CREATURE card type."""
        game = create_game()
        hall = _hall_on_battlefield(game, 0)
        ability = _animation_ability(hall)
        ability.effect(game)
        assert CardType.CREATURE in hall.card_types

    def test_stays_a_land(self) -> None:
        """It's still a land after animating."""
        game = create_game()
        hall = _hall_on_battlefield(game, 0)
        ability = _animation_ability(hall)
        ability.effect(game)
        assert CardType.LAND in hall.card_types

    def test_becomes_wizard_subtype(self) -> None:
        game = create_game()
        hall = _hall_on_battlefield(game, 0)
        ability = _animation_ability(hall)
        ability.effect(game)
        assert "Wizard" in hall.subtypes

    def test_power_and_toughness_are_two_four(self) -> None:
        """The animated creature is 2/4."""
        game = create_game()
        hall = _hall_on_battlefield(game, 0)
        ability = _animation_ability(hall)
        ability.effect(game)
        assert hall.power == 2
        assert hall.toughness == 4

    def test_animation_via_engine_activate_ability(self) -> None:
        """End-to-end: activating through engine.abilities.activate_ability
        animates the land (non-mana ability resolves off the stack)."""
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        ability = _animation_ability(hall)
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p1,
            cost=ability.cost,
            effect=ability.effect,
            is_mana_ability=False,
            description=getattr(ability, "description", ""),
        )
        activate_ability(game, p1, instance)
        # Non-mana ability pushes a StackObject; resolve it.
        assert not game.stack.is_empty()
        obj = game.stack.pop()
        obj.on_resolve(game)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types

    def test_gate_no_double_animation(self) -> None:
        """'If this land isn't a creature' — re-running the effect while it is
        already a creature must not stack additional power/toughness."""
        game = create_game()
        hall = _hall_on_battlefield(game, 0)
        ability = _animation_ability(hall)
        ability.effect(game)
        assert (hall.power, hall.toughness) == (2, 4)
        # Second resolution is a no-op for the becomes-creature change.
        ability.effect(game)
        assert (hall.power, hall.toughness) == (2, 4)


# ---------------------------------------------------------------------------
# Animated creature's "Whenever you cast an instant or sorcery" pump
# ---------------------------------------------------------------------------

class TestCastTriggerPump:
    """The animated creature gets +1/+0 until end of turn whenever its
    controller casts an instant or sorcery spell."""

    def _animate(self, game, hall):
        ability = _animation_ability(hall)
        ability.effect(game)
        # Register the source's triggers (engine wires this on ETB; here we
        # invoke it directly so the cast trigger is live).
        hall.register_triggers(game)

    def test_registers_spell_cast_trigger_after_animation(self) -> None:
        """Once animated, the land registers a SpellCastTriggeredEvent trigger."""
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        self._animate(game, hall)
        regs = game.trigger_manager.get_triggers_for_source(hall)
        assert any(
            r.event_type is SpellCastTriggeredEvent
            or issubclass(SpellCastTriggeredEvent, r.event_type)
            for r in regs
        )

    def test_pump_applies_on_controller_instant_cast(self) -> None:
        """Firing a SpellCastTriggeredEvent for an instant the controller cast
        pumps the animated land +1/+0 (to 3/4)."""
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        self._animate(game, hall)
        assert (hall.power, hall.toughness) == (2, 4)

        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}),
                       owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=bolt, card=bolt,
                                    player=p1, controller=p1),
        )
        # Resolve any triggered abilities that were pushed.
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert hall.power == 3
        assert hall.toughness == 4

    def test_pump_applies_on_controller_sorcery_cast(self) -> None:
        """A sorcery also triggers the +1/+0 pump."""
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        self._animate(game, hall)

        sorc = Sorcery(name="Divination",
                       mana_cost=ManaCost(generic=2, pips={ManaType.BLUE: 1}),
                       owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=sorc, card=sorc,
                                    player=p1, controller=p1),
        )
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert hall.power == 3

    def test_pump_does_not_apply_for_creature_spell(self) -> None:
        """Casting a creature spell does NOT pump the animated land."""
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        self._animate(game, hall)

        bear = Creature(name="Bear",
                        mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
                        base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=bear, card=bear,
                                    player=p1, controller=p1),
        )
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert hall.power == 2
        assert hall.toughness == 4

    def test_pump_does_not_apply_for_opponent_spell(self) -> None:
        """'Whenever YOU cast' — an opponent's instant must not pump it."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        hall = _hall_on_battlefield(game, 0)
        self._animate(game, hall)

        bolt = Instant(name="Opp Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}),
                       owner=p2, controller=p2)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=bolt, card=bolt,
                                    player=p2, controller=p2),
        )
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert hall.power == 2

    def test_no_pump_trigger_before_animation(self) -> None:
        """Before animating, casting an instant must not pump it (it is not
        even a creature). No SpellCast trigger should be registered yet."""
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)
        # Register triggers WITHOUT animating first.
        hall.register_triggers(game)

        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}),
                       owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=bolt, card=bolt,
                                    player=p1, controller=p1),
        )
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        # Still not a creature, and no power to speak of.
        assert CardType.CREATURE not in hall.card_types


# ---------------------------------------------------------------------------
# "Spend this mana only to cast an instant or sorcery spell" restriction
# ---------------------------------------------------------------------------

class TestInstantSorceryRestrictedMana:
    """The any-color mana from the {T}, Pay 1 life ability carries the
    'Spend this mana only to cast an instant or sorcery spell' rider
    (CR 106.6). These tests drive the REAL ``engine.casting.cast_spell``
    payment path to prove the restriction is enforced: restricted mana pays
    for an instant/sorcery, but is treated as unavailable for a creature.

    This covers the requirement previously reported as untestable (the engine
    now exposes ``ManaPool.add_restricted`` and ``cast_spell`` consults it).
    """

    def _main_phase_game(self, *, scripts=None):
        """A two-player game in player 0's precombat main with an empty stack,
        so sorcery-speed timing is satisfied for sorceries/creatures."""
        game = create_game(scripts=scripts)
        game.phase = Phase.PRECOMBAT_MAIN
        return game

    def test_restricted_mana_pays_for_instant_via_cast_spell(self) -> None:
        """Mana produced by the pay-1-life ability (tagged instant/sorcery)
        successfully pays for an INSTANT through the real cast_spell, and the
        mana is consumed."""
        # Script the color choice (BLUE) for the any-color ability.
        game = self._main_phase_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        hall = _hall_on_battlefield(game, 0)

        # Produce the restricted any-color mana via the card's own ability.
        ability = _mana_ability_for(hall, description_contains="life") \
            or _mana_ability_for(hall, description_contains="any color")
        assert ability is not None
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.BLUE) == 1

        bolt = Instant(name="Blue Bolt",
                       mana_cost=ManaCost(pips={ManaType.BLUE: 1}),
                       owner=p1, controller=p1)
        game.get_hand(p1).add(bolt)

        # The restricted mana is allowed to pay for an instant.
        cast_spell(game, p1, bolt)

        assert not game.stack.is_empty()
        assert game.stack.peek().source is bolt
        # Mana was consumed by the cast.
        assert p1.mana_pool.get(ManaType.BLUE) == 0

    def test_restricted_mana_pays_for_sorcery_via_cast_spell(self) -> None:
        """Restricted mana added directly via ManaPool.add_restricted pays for
        a SORCERY through cast_spell."""
        game = self._main_phase_game()
        p1 = game.players[0]
        p1.mana_pool.empty()
        p1.mana_pool.add_restricted(
            ManaType.GREEN, 1, restriction=RESTRICTION_INSTANT_SORCERY
        )

        sorc = Sorcery(name="Green Ritual",
                       mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
                       owner=p1, controller=p1)
        game.get_hand(p1).add(sorc)

        cast_spell(game, p1, sorc)

        assert not game.stack.is_empty()
        assert game.stack.peek().source is sorc
        assert p1.mana_pool.get(ManaType.GREEN) == 0

    def test_restricted_mana_cannot_pay_for_creature(self) -> None:
        """With instant/sorcery-restricted mana as the ONLY available mana,
        casting a CREATURE raises CastingError and nothing changes: the spell
        stays in hand, the stack stays empty, and the mana is untouched."""
        game = self._main_phase_game()
        p1 = game.players[0]
        p1.mana_pool.empty()
        p1.mana_pool.add_restricted(
            ManaType.GREEN, 1, restriction=RESTRICTION_INSTANT_SORCERY
        )

        bear = Creature(name="Bear",
                        mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
                        base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        game.get_hand(p1).add(bear)

        with pytest.raises(CastingError):
            cast_spell(game, p1, bear)

        # Restricted mana was NOT spent on the illegal creature spell.
        assert p1.mana_pool.get(ManaType.GREEN) == 1
        # Rolled back: the creature is still in hand and not on the stack.
        assert game.get_hand(p1).contains(bear)
        assert game.stack.is_empty()

    def test_unrestricted_mana_can_pay_for_creature_control(self) -> None:
        """Control: ordinary (unrestricted) GREEN mana DOES pay for the same
        creature spell, proving it is the restriction — not some other gap —
        that blocks the creature cast above."""
        game = self._main_phase_game()
        p1 = game.players[0]
        set_board_state(game, 0, mana={ManaType.GREEN: 1})

        bear = Creature(name="Bear",
                        mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
                        base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        game.get_hand(p1).add(bear)

        cast_spell(game, p1, bear)

        assert not game.stack.is_empty()
        assert game.stack.peek().source is bear
        assert p1.mana_pool.get(ManaType.GREEN) == 0
