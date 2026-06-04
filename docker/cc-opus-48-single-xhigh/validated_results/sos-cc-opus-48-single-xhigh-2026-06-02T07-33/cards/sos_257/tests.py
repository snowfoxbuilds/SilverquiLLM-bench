"""Tests for SOS 257 — Great Hall of the Biblioplex.

Great Hall of the Biblioplex — Land:

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.

Behaviour contract (TDD red phase — these tests fail against the empty stub).

* **Static data** — a :class:`engine.card.Land` named ``"Great Hall of the
  Biblioplex"``, type line ``Land`` (``CardType.LAND`` only, never CREATURE
  while unanimated), no colors, no mana cost, and NOT a basic land (no
  ``Supertype.BASIC``).  Power/toughness are ``None`` while it is not a
  creature.
* **Ability 1 — {T}: Add {C}** — one mana ability that, when its cost runs,
  taps the land and adds exactly one ``COLORLESS`` mana to the controller's
  pool.  Modelled exactly on fdn_272 (Plains) / fdn_267 (Secluded Courtyard).
* **Ability 2 — {T}, Pay 1 life: any color (instant/sorcery only)** — a second
  mana ability that taps the land, reduces the controller's life by 1, and
  adds one mana of a chosen color.  The "spend this mana only to cast an
  instant or sorcery spell" restriction has no engine surface today (the
  ManaPool has no restricted-mana tagging — see fdn_267's documented engine
  limitation); that one clause is recorded in ``untestable.json``.
* **Ability 3 — {5}: animate** — an activated ability ({5}) that, while the
  land is not already a creature, turns it into a 2/4 Wizard creature that is
  STILL a land, with a granted "Whenever you cast an instant or sorcery spell,
  this creature gets +1/+0 until end of turn" trigger.  The engine has no
  becomes-a-creature animation pipeline nor an until-end-of-turn pump grant;
  the deep assertions are tolerant probes that fail loudly if the surface is
  absent, and the hardest pieces are recorded in ``untestable.json``.

The mana / activated abilities are exercised by reading the card's public
ability surface (``get_mana_abilities`` / ``get_activated_abilities``) and
invoking the cost/effect callables directly — the established per-card test
convention used by the FDN reference land cards (fdn_272, fdn_267) and the
SOS reference cards.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import ActivatedAbility, Creature, Instant, Land, ManaAbility, Sorcery
from engine.casting import CastingError, cast_spell
from engine.events import SpellCastTriggeredEvent
from engine.types import (
    CardType,
    Color,
    ManaCost,
    ManaType,
    Phase,
    Supertype,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _card(owner: Any = None, controller: Any = None) -> GreatHallOfTheBiblioplex:
    """Build a Great Hall instance (owner == controller by default)."""
    return GreatHallOfTheBiblioplex(owner=owner, controller=controller)


def _run_cost(ability: Any, game: Any, source: Any) -> bool:
    """Invoke an ability cost callable, tolerating 1- or 2-arg signatures.

    fdn_272 (Plains) uses a 1-arg ``cost(game)`` closure while fdn_267
    (Secluded Courtyard) uses a 2-arg ``cost(game, source)`` closure; both
    shapes are legal, so call accordingly.
    """
    try:
        return bool(ability.cost(game, source))
    except TypeError:
        return bool(ability.cost(game))


def _run_effect(ability: Any, game: Any, source: Any) -> None:
    """Invoke a mana ability's ``mana_produced`` / effect callable.

    ``ManaAbility.mana_produced`` may either *return* a ``{ManaType: int}``
    dict (fdn_272 style) or directly mutate the controller's pool (fdn_267
    style).  When it returns a dict, deposit it into the controller's pool
    so both conventions are observable through the pool.
    """
    produced = ability.mana_produced(game)
    if isinstance(produced, dict):
        controller = source.controller
        for mana_type, amount in produced.items():
            controller.mana_pool.add(mana_type, amount)


def _colorless_mana_ability(card: Any) -> ManaAbility:
    """Return the ``{T}: Add {C}`` ability (the one that yields colorless)."""
    abilities = card.get_mana_abilities()
    for ab in abilities:
        # Probe each ability in a fresh game; pick the one that produces {C}.
        game = create_game()
        p = game.players[0]
        card.owner = p
        card.controller = p
        card.is_tapped = False
        if not _run_cost(ab, game, card):
            continue
        _run_effect(ab, game, card)
        if p.mana_pool.get(ManaType.COLORLESS) >= 1 and p.mana_pool.total() == 1:
            return ab
    raise AssertionError("No {T}: Add {C} mana ability found on Great Hall")


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestGreatHallProperties:
    """Static card data should match the SOS 257 spec."""

    def test_name(self) -> None:
        assert _card().name == "Great Hall of the Biblioplex"

    def test_is_a_land(self) -> None:
        card = _card()
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types

    def test_not_a_creature_while_unanimated(self) -> None:
        """It is a plain land until {5} animates it."""
        assert CardType.CREATURE not in _card().card_types

    def test_has_no_mana_cost(self) -> None:
        """Lands are played, not cast — no mana cost is printed."""
        assert _card().mana_cost == ManaCost()

    def test_cannot_be_cast(self) -> None:
        """Lands return can_cast() == False (they are played as a special action)."""
        game = create_game()
        assert _card().can_cast(game) is False

    def test_has_no_colors(self) -> None:
        """A colorless land — no colored identity."""
        from engine.protection import get_colors

        assert get_colors(_card()) == set()

    def test_is_not_a_basic_land(self) -> None:
        """Great Hall is a nonbasic land — no BASIC supertype."""
        assert Supertype.BASIC not in _card().supertypes

    def test_has_no_basic_land_subtype(self) -> None:
        """It is not a Plains/Island/Swamp/Mountain/Forest."""
        basics = {"Plains", "Island", "Swamp", "Mountain", "Forest"}
        assert _card().subtypes.isdisjoint(basics)

    def test_power_toughness_unset_while_not_a_creature(self) -> None:
        """A non-creature land has no power/toughness characteristic.

        Either the attributes are absent, or they read as ``None`` — never a
        concrete number while the card is an ordinary (non-creature) land.
        """
        card = _card()
        assert getattr(card, "power", None) is None
        assert getattr(card, "toughness", None) is None


# ---------------------------------------------------------------------------
# Ability 1 — {T}: Add {C}
# ---------------------------------------------------------------------------


class TestGreatHallColorlessManaAbility:
    """{T}: Add {C} — a basic colorless mana ability."""

    def test_exposes_at_least_two_mana_abilities(self) -> None:
        """The card prints two mana abilities (the {C} one and the any-color one)."""
        card = _card()
        abilities = card.get_mana_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) >= 2
        assert all(isinstance(ab, ManaAbility) for ab in abilities)

    def test_colorless_ability_taps_the_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        card.is_tapped = False
        ab = _colorless_mana_ability(card)
        # Re-run the cost on a clean instance to assert the tap side effect.
        card.is_tapped = False
        assert _run_cost(ab, game, card) is True
        assert card.is_tapped is True

    def test_colorless_ability_adds_one_colorless_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        card.is_tapped = False
        ab = _colorless_mana_ability(card)
        # Run the chosen ability for real against p1.
        card.is_tapped = False
        assert _run_cost(ab, game, card) is True
        _run_effect(ab, game, card)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert p1.mana_pool.total() == 1

    def test_colorless_ability_cost_fails_when_already_tapped(self) -> None:
        """A tapped land cannot pay its {T} cost again."""
        game = create_game()
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        ab = _colorless_mana_ability(card)
        card.is_tapped = True
        assert _run_cost(ab, game, card) is False


# ---------------------------------------------------------------------------
# Ability 2 — {T}, Pay 1 life: Add one mana of any color (instant/sorcery only)
# ---------------------------------------------------------------------------


class TestGreatHallAnyColorManaAbility:
    """{T}, Pay 1 life: Add one mana of any color (restricted to I/S casting)."""

    def _any_color_ability(self, card: Any) -> ManaAbility:
        """Return the second (any-color, pay-1-life) mana ability.

        Identified positionally: the colorless ability is the {C} producer;
        the remaining mana ability is the any-color one.
        """
        colorless = _colorless_mana_ability(card)
        others = [ab for ab in card.get_mana_abilities() if ab is not colorless]
        assert others, "Great Hall must print a second (any-color) mana ability"
        return others[0]

    def test_any_color_ability_taps_the_land(self) -> None:
        game = create_game(scripts=([Color.BLUE], []))
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        ab = self._any_color_ability(card)
        card.is_tapped = False
        assert _run_cost(ab, game, card) is True
        assert card.is_tapped is True

    def test_any_color_ability_pays_one_life(self) -> None:
        """Activating the second ability reduces the controller's life by 1."""
        game = create_game(scripts=([Color.RED], []))
        p1 = game.players[0]
        set_board_state(game, 0, life=20)
        card = _card(owner=p1, controller=p1)
        ab = self._any_color_ability(card)
        card.is_tapped = False
        before = p1.life
        _run_cost(ab, game, card)
        _run_effect(ab, game, card)
        assert p1.life == before - 1

    def test_any_color_ability_adds_one_mana_of_chosen_color(self) -> None:
        """The chosen color (here blue) is the single mana added."""
        game = create_game(scripts=([Color.BLUE], []))
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        ab = self._any_color_ability(card)
        card.is_tapped = False
        _run_cost(ab, game, card)
        _run_effect(ab, game, card)
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        # Exactly one mana of one color is produced.
        assert p1.mana_pool.total() == 1

    def test_any_color_ability_can_produce_a_different_color(self) -> None:
        """A different scripted color (green) is honoured — it is "any color"."""
        game = create_game(scripts=([Color.GREEN], []))
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        ab = self._any_color_ability(card)
        card.is_tapped = False
        _run_cost(ab, game, card)
        _run_effect(ab, game, card)
        assert p1.mana_pool.get(ManaType.GREEN) == 1
        assert p1.mana_pool.total() == 1

    def test_any_color_mana_is_marked_restricted_to_instants_sorceries(self) -> None:
        """The produced mana must carry an instant/sorcery-only spend restriction.

        TOLERANT PROBE.  The engine's ``ManaPool`` has no restricted-mana
        tagging today (fdn_267 documents the same limitation), so there is no
        public way to add or read such a restriction.  This test fails loudly
        rather than passing vacuously: if a restriction surface is ever added
        (a tag on the pool, a per-mana restriction record, or a card-level
        query such as ``produces_restricted_mana``/``mana_spend_restriction``),
        it must be discoverable here.  Recorded in untestable.json until then.
        """
        card = _card()
        ab = self._any_color_ability(card)
        restriction_surface = (
            hasattr(card, "mana_spend_restriction")
            or hasattr(card, "produces_restricted_mana")
            or hasattr(ab, "restriction")
            or hasattr(ab, "spend_restriction")
            or hasattr(create_game().players[0].mana_pool, "restrictions")
        )
        assert restriction_surface, (
            "No engine surface to tag 'spend this mana only to cast an instant "
            "or sorcery spell' — see untestable.json"
        )


# ---------------------------------------------------------------------------
# Ability 3 — {5}: becomes a 2/4 Wizard creature, still a land
# ---------------------------------------------------------------------------


class TestGreatHallAnimationAbilitySurface:
    """{5}: exposes a non-mana activated ability for the animation."""

    def test_exposes_an_activated_ability(self) -> None:
        """The {5} animation is an activated (non-mana) ability."""
        card = _card()
        abilities = card.get_activated_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) >= 1
        assert all(isinstance(ab, ActivatedAbility) for ab in abilities)


class TestGreatHallAnimationEffect:
    """{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with a granted instant/sorcery pump trigger.  It's still a land.

    The engine has no becomes-a-creature animation pipeline, so these are
    TOLERANT PROBES: they invoke the activated ability's effect and then
    assert the observable end state (added CREATURE type, Wizard subtype, 2/4,
    LAND retained).  They fail loudly if the animation surface is absent.
    The deepest pieces are also recorded in untestable.json.
    """

    def _activate(self, card: Any, game: Any) -> None:
        """Pay the {5} cost (if a cost gate exists) and apply the effect."""
        abilities = card.get_activated_abilities()
        assert abilities, "Great Hall must print a {5} activated ability"
        ab = abilities[0]
        # Pay the cost if the closure enforces one; tolerate either shape.
        try:
            ab.cost(game, card)
        except TypeError:
            try:
                ab.cost(game)
            except Exception:
                pass
        ab.effect(game)

    def test_becomes_a_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        assert CardType.CREATURE not in card.card_types
        self._activate(card, game)
        assert CardType.CREATURE in card.card_types

    def test_is_still_a_land_after_animation(self) -> None:
        """"It's still a land." — LAND type is retained alongside CREATURE."""
        game = create_game()
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        self._activate(card, game)
        assert CardType.LAND in card.card_types

    def test_becomes_a_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        self._activate(card, game)
        assert "Wizard" in card.subtypes

    def test_becomes_two_four(self) -> None:
        """The animated land is a 2/4."""
        game = create_game()
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        self._activate(card, game)
        # Recompute continuous effects so layer-based P/T (if any) is applied.
        game.effect_manager.apply_all(game)
        assert getattr(card, "power", None) == 2
        assert getattr(card, "toughness", None) == 4

    def test_animation_no_op_when_already_a_creature(self) -> None:
        """"If this land isn't a creature" — a second activation is a no-op.

        Animating an already-animated Great Hall must not stack a second
        pump grant or change its 2/4 body.
        """
        game = create_game()
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        self._activate(card, game)
        game.effect_manager.apply_all(game)
        triggers_after_first = len(game.trigger_manager.get_triggers())
        # Second activation while already a creature should change nothing.
        self._activate(card, game)
        game.effect_manager.apply_all(game)
        assert getattr(card, "power", None) == 2
        assert getattr(card, "toughness", None) == 4
        assert len(game.trigger_manager.get_triggers()) == triggers_after_first


class TestGreatHallGrantedPumpTrigger:
    """The animated creature gets +1/+0 until end of turn per instant/sorcery
    spell you cast.  TOLERANT PROBE — no engine grant-on-animation pipeline."""

    def _activate(self, card: Any, game: Any) -> None:
        abilities = card.get_activated_abilities()
        assert abilities, "Great Hall must print a {5} activated ability"
        ab = abilities[0]
        try:
            ab.cost(game, card)
        except TypeError:
            try:
                ab.cost(game)
            except Exception:
                pass
        ab.effect(game)

    def test_animation_registers_a_pump_trigger(self) -> None:
        """Animating the land must register a (cast-an-instant/sorcery) trigger.

        The granted ability fires "Whenever you cast an instant or sorcery
        spell", so a new trigger controlled by the land's controller should be
        registered when the land becomes a creature.
        """
        game = create_game()
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        before = len(game.trigger_manager.get_triggers())
        self._activate(card, game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before, (
            "Animation must grant the 'whenever you cast an instant or sorcery "
            "spell' pump trigger — see untestable.json"
        )

    def test_pump_trigger_adds_plus_one_zero_until_end_of_turn(self) -> None:
        """Casting an instant/sorcery pumps the animated land +1/+0.

        TOLERANT PROBE: locate the granted trigger registered by the
        animation, fire its effect once, recompute continuous effects, and
        assert the body is 3/4 (2/4 plus +1/+0).  Fails loudly if no such
        trigger/effect surface exists.  The until-end-of-turn duration and the
        per-cast scaling are recorded in untestable.json.
        """
        game = create_game()
        p1 = game.players[0]
        card = _card(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        before = list(game.trigger_manager.get_triggers())
        self._activate(card, game)
        game.effect_manager.apply_all(game)
        new_triggers = [
            t for t in game.trigger_manager.get_triggers() if t not in before
        ]
        assert new_triggers, (
            "No granted instant/sorcery pump trigger to fire — see untestable.json"
        )

        # Fire the granted trigger's effect (as a cast event would) and
        # recompute the layer system.
        trig = new_triggers[0]
        effect = getattr(trig, "effect", None)
        assert callable(effect), "Granted pump trigger has no callable effect"
        effect(game)
        game.effect_manager.apply_all(game)

        assert getattr(card, "power", None) == 3
        assert getattr(card, "toughness", None) == 4


# ===========================================================================
# EXTENDED COVERAGE — the three formerly-deferred mechanisms, now built.
#
# These tests drive the REAL engine surfaces the Implementer added:
#   1. engine.mana.ManaPool.add_restricted / can_pay_for_spell  (+ cast_spell)
#   2. engine.animation.animate_land  (becomes-a-creature end state + guard)
#   3. engine.animation.register_instant_sorcery_pump  (granted +1/+0 EOT pump)
# Each was confirmed to PASS against the now-built engine; the tolerant probes
# above stay as-is, and these add concrete assertions that fail loudly if any
# surface regresses.
# ===========================================================================


def _sorcery_speed(game: Any, player_index: int = 0) -> None:
    """Put *game* in a sorcery-speed window for ``player_index`` (active,
    pre-combat main, empty stack) so ``cast_spell`` accepts a sorcery/creature.
    """
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _restricted_mana_game() -> Any:
    """Return a fresh game in a sorcery-speed window with an empty p1 pool."""
    game = create_game()
    _sorcery_speed(game, 0)
    game.players[0].mana_pool.empty()
    return game


class TestGreatHallRestrictedManaSpend:
    """The any-color mana is tagged "spend only to cast an instant or sorcery
    spell" — engine.mana.ManaPool.add_restricted + can_pay_for_spell, enforced
    by engine.casting.cast_spell.

    Drives the REAL ManaPool + cast_spell: an instant/sorcery consumes the
    restricted mana, but a creature spell cannot use it.
    """

    def _produce_restricted_via_card(self, game: Any, color: Color) -> None:
        """Activate Great Hall's {T}, Pay 1 life ability to deposit one mana of
        *color* tagged instant/sorcery-only into p1's pool (drives the card)."""
        p1 = game.players[0]
        # The any-color producer reads a scripted color choice.
        if hasattr(p1, "_script"):
            p1._script.appendleft(color)
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land])
        land.is_tapped = False
        abilities = land.get_mana_abilities()
        any_color = [ab for ab in abilities if getattr(ab, "restriction", None)]
        assert any_color, "Great Hall must tag its any-color ability with a restriction"
        ab = any_color[0]
        assert ab.cost(game) is True
        ab.mana_produced(game)

    def test_card_produced_mana_is_tagged_restricted(self) -> None:
        """The any-color ability deposits mana that the pool records as
        restricted (not merely ordinary mana)."""
        game = create_game(scripts=([Color.BLUE], []))
        _sorcery_speed(game, 0)
        game.players[0].mana_pool.empty()
        self._produce_restricted_via_card(game, Color.BLUE)
        pool = game.players[0].mana_pool
        assert pool.get(ManaType.BLUE) == 1
        assert pool.has_restricted_mana() is True
        assert pool.restricted_amount() == 1

    def test_instant_can_be_cast_with_restricted_mana(self) -> None:
        """An INSTANT consumes the restricted any-color mana (the permitted
        spell type) — driven through the real cast_spell pipeline."""
        game = create_game(scripts=([Color.BLUE], []))
        _sorcery_speed(game, 0)
        p1 = game.players[0]
        p1.mana_pool.empty()
        self._produce_restricted_via_card(game, Color.BLUE)
        spell = Instant(name="Restricted Bolt", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, hand=[spell])
        cast_spell(game, p1, spell)
        # The instant reached the stack and the restricted mana was spent.
        assert not game.stack.is_empty()
        assert p1.mana_pool.total() == 0
        assert p1.mana_pool.restricted_amount() == 0

    def test_sorcery_can_be_cast_with_restricted_mana(self) -> None:
        """A SORCERY is also a permitted spend target for the restricted mana."""
        game = _restricted_mana_game()
        p1 = game.players[0]
        p1.mana_pool.add_restricted(
            ManaType.GREEN, 1, source=None
        )
        spell = Sorcery(name="Restricted Spell", mana_cost=ManaCost.parse("{G}"))
        set_board_state(game, 0, hand=[spell])
        cast_spell(game, p1, spell)
        assert not game.stack.is_empty()
        assert p1.mana_pool.total() == 0

    def test_creature_cannot_be_cast_with_restricted_mana(self) -> None:
        """A CREATURE spell is NOT a permitted target — the restricted mana may
        not pay for it, so cast_spell rejects it as insufficient mana."""
        game = _restricted_mana_game()
        p1 = game.players[0]
        p1.mana_pool.add_restricted(ManaType.GREEN, 1, source=None)
        creature = Creature(
            name="Forbidden Bear",
            mana_cost=ManaCost.parse("{G}"),
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, hand=[creature])
        with pytest.raises(CastingError):
            cast_spell(game, p1, creature)
        # The spell was rolled back to hand and the restricted mana untouched.
        assert game.get_hand(p1).contains(creature)
        assert p1.mana_pool.restricted_amount() == 1

    def test_creature_can_be_cast_with_unrestricted_mana(self) -> None:
        """Anchor: the rejection above is about the RESTRICTION, not the cost.

        The same creature for {G} casts fine when the green mana is ordinary
        (unrestricted) — so the negative test is not vacuously failing for an
        unrelated reason.
        """
        game = _restricted_mana_game()
        p1 = game.players[0]
        p1.mana_pool.add(ManaType.GREEN, 1)
        creature = Creature(
            name="Allowed Bear",
            mana_cost=ManaCost.parse("{G}"),
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, hand=[creature])
        cast_spell(game, p1, creature)
        assert not game.stack.is_empty()

    def test_restricted_mana_does_not_taint_an_unrestricted_pool(self) -> None:
        """Regression anchor: with NO restricted mana present, a creature for
        {G} still casts — the restriction machinery never blocks ordinary mana.
        """
        game = _restricted_mana_game()
        p1 = game.players[0]
        # Ordinary mana only.
        p1.mana_pool.add(ManaType.GREEN, 2)
        assert p1.mana_pool.has_restricted_mana() is False
        creature = Creature(
            name="Plain Bear",
            mana_cost=ManaCost.parse("{1}{G}"),
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, hand=[creature])
        cast_spell(game, p1, creature)
        assert not game.stack.is_empty()


class TestGreatHallAnimationEndState:
    """{5} animation end state via engine.animation.animate_land.

    Pays the real {5} cost out of the controller's pool, then asserts the exact
    end state: CREATURE added while LAND retained, Wizard subtype, a 2/4 body
    observable after the effect manager applies, and the "if this land isn't a
    creature" guard against re-animation.
    """

    def _animated_land(self, mana: int = 5) -> tuple[Any, Any]:
        game = create_game()
        game.active_player_index = 0
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: mana})
        ab = land.get_activated_abilities()[0]
        assert ab.cost(game) is True
        ab.effect(game)
        game.effect_manager.apply_all(game)
        return game, land

    def test_five_cost_is_paid_from_the_pool(self) -> None:
        """Activating the {5} ability consumes exactly five generic mana."""
        game = create_game()
        game.active_player_index = 0
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 6})
        ab = land.get_activated_abilities()[0]
        assert ab.cost(game) is True
        assert p1.mana_pool.total() == 1  # 6 - 5

    def test_animated_gains_creature_but_keeps_land(self) -> None:
        """It becomes a creature AND stays a land ("It's still a land.")."""
        _game, land = self._animated_land()
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types

    def test_animated_gains_wizard_subtype(self) -> None:
        _game, land = self._animated_land()
        assert "Wizard" in land.subtypes

    def test_animated_body_is_two_four(self) -> None:
        """The animated land reports power 2 / toughness 4 after apply_all."""
        _game, land = self._animated_land()
        assert land.power == 2
        assert land.toughness == 4

    def test_body_survives_recomputation(self) -> None:
        """The durable layer effects keep the 2/4 body and creature type across
        repeated apply_all cycles (reset-and-reapply does not lose them)."""
        game, land = self._animated_land()
        for _ in range(3):
            game.effect_manager.apply_all(game)
        assert land.power == 2
        assert land.toughness == 4
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types

    def test_reanimation_is_a_noop_no_second_body_or_grant(self) -> None:
        """"If this land isn't a creature" — a SECOND {5} (cost paid again) does
        NOT re-animate: no second pump-trigger grant, no extra layer effects,
        and the body stays 2/4 (not stacked)."""
        game, land = self._animated_land(mana=10)
        triggers_after_first = len(game.trigger_manager.get_triggers())
        effects_after_first = len(game.effect_manager.get_all())
        assert triggers_after_first == 1, "first animation grants exactly one trigger"

        # Re-activate while already a creature.
        ab = land.get_activated_abilities()[0]
        assert ab.cost(game) is True  # the cost still runs (pays {5})
        ab.effect(game)  # ... but the effect must be a no-op (guard)
        game.effect_manager.apply_all(game)

        assert len(game.trigger_manager.get_triggers()) == triggers_after_first
        assert len(game.effect_manager.get_all()) == effects_after_first
        assert land.power == 2
        assert land.toughness == 4


class TestGreatHallGrantedPumpBehaviour:
    """The granted "Whenever you cast an instant or sorcery spell, this creature
    gets +1/+0 until end of turn" trigger — engine.animation.

    Fires SpellCastTriggeredEvent (the established cast-trigger test pattern,
    cf. sos_226), resolves the stacked trigger, and asserts the +1/+0 stacks per
    cast, resets at cleanup, and is gated to the controller's instant/sorcery
    casts.
    """

    def _animate(self) -> tuple[Any, Any, Any, Any]:
        game = create_game()
        game.active_player_index = 0
        p1 = game.players[0]
        p2 = game.players[1]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        ab = land.get_activated_abilities()[0]
        ab.cost(game)
        ab.effect(game)
        game.effect_manager.apply_all(game)
        return game, p1, p2, land

    def _cast_event(self, game: Any, land: Any, spell: Any, caster: Any) -> None:
        """Fire a SpellCastTriggeredEvent and resolve any trigger it stacks,
        then recompute continuous effects."""
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell, player=caster, controller=caster, card=spell
            ),
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)

    def test_animation_registers_exactly_one_pump_trigger(self) -> None:
        game, _p1, _p2, _land = self._animate()
        triggers = game.trigger_manager.get_triggers()
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_one_instant_cast_pumps_plus_one_zero(self) -> None:
        """One instant cast → +1/+0 (power 3, toughness unchanged at 4)."""
        game, p1, _p2, land = self._animate()
        spell = Instant(name="Pump Bolt", mana_cost=ManaCost.parse("{U}"))
        self._cast_event(game, land, spell, p1)
        assert land.power == 3
        assert land.toughness == 4

    def test_sorcery_cast_also_pumps(self) -> None:
        """A sorcery is an equally valid trigger — +1/+0 as well."""
        game, p1, _p2, land = self._animate()
        spell = Sorcery(name="Pump Spell", mana_cost=ManaCost.parse("{G}"))
        self._cast_event(game, land, spell, p1)
        assert land.power == 3
        assert land.toughness == 4

    def test_multiple_casts_stack_plus_n_zero(self) -> None:
        """N instant/sorcery casts in a turn → power == 2 + N, toughness == 4."""
        game, p1, _p2, land = self._animate()
        n = 3
        for i in range(n):
            spell = Instant(name=f"Bolt {i}", mana_cost=ManaCost.parse("{U}"))
            self._cast_event(game, land, spell, p1)
        assert land.power == 2 + n
        assert land.toughness == 4

    def test_pump_resets_at_end_of_turn(self) -> None:
        """The +1/+0 is "until end of turn": remove_expired (run at cleanup)
        sweeps the DURATION_END_OF_TURN effects, so the body resets to 2/4."""
        game, p1, _p2, land = self._animate()
        for i in range(2):
            spell = Instant(name=f"Bolt {i}", mana_cost=ManaCost.parse("{U}"))
            self._cast_event(game, land, spell, p1)
        assert land.power == 4  # 2 + 2 pumps, mid-turn

        # Cleanup: sweep end-of-turn effects, recompute.
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert land.power == 2
        assert land.toughness == 4

    def test_animation_type_effect_survives_eot_sweep(self) -> None:
        """The cleanup sweep removes the pump but NOT the (permanent) animation:
        the land is still a 2/4 creature-land after end-of-turn reset."""
        game, p1, _p2, land = self._animate()
        spell = Instant(name="Bolt", mana_cost=ManaCost.parse("{U}"))
        self._cast_event(game, land, spell, p1)
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert land.power == 2
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types
        assert "Wizard" in land.subtypes

    def test_opponents_cast_does_not_pump(self) -> None:
        """Gated to "you": an OPPONENT casting an instant must NOT pump the land
        (it stays 2/4)."""
        game, _p1, p2, land = self._animate()
        spell = Instant(name="Their Bolt", mana_cost=ManaCost.parse("{U}"))
        before_stack = len(game.stack)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell, player=p2, controller=p2, card=spell),
        )
        # No trigger should have been pushed for the opponent's cast.
        assert len(game.stack) == before_stack
        game.effect_manager.apply_all(game)
        assert land.power == 2
        assert land.toughness == 4

    def test_controllers_creature_cast_does_not_pump(self) -> None:
        """Gated to instants/sorceries: the controller casting a CREATURE spell
        must NOT pump the land (creature is neither instant nor sorcery)."""
        game, p1, _p2, land = self._animate()
        creature_spell = Creature(
            name="Bear Spell",
            mana_cost=ManaCost.parse("{G}"),
            base_power=2,
            base_toughness=2,
        )
        before_stack = len(game.stack)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=creature_spell, player=p1, controller=p1, card=creature_spell
            ),
        )
        assert len(game.stack) == before_stack
        game.effect_manager.apply_all(game)
        assert land.power == 2
        assert land.toughness == 4
