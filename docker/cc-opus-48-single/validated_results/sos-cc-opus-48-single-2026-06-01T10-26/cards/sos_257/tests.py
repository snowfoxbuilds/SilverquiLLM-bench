"""Tests for SOS 257 — Great Hall of the Biblioplex.

Great Hall of the Biblioplex is a Land with three abilities:

  {T}: Add {C}.
  {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
      an instant or sorcery spell.
  {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
      "Whenever you cast an instant or sorcery spell, this creature gets
      +1/+0 until end of turn." It's still a land.

These TDD-red tests describe the observable contract:

  * static card data (Land, no mana cost, no P/T, colorless),
  * the two mana abilities ({C}, and any-color for 1 life),
  * the {5} animation ability (becomes a 2/4 Wizard creature that is
    still a Land), and
  * the "isn't a creature" guard on the animation.

The engine has no surface for enforcing the "spend this mana only to cast an
instant or sorcery spell" restriction (see Secluded Courtyard / FDN 267, which
documents the same limitation); that requirement is recorded in
``untestable.json`` rather than asserted here.
"""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Instant, Land, ManaAbility, ActivatedAbility, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.state_based_actions import resolve_state_based_actions
from engine.turn import _do_cleanup_step
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------

class TestGreatHallProperties:
    """Static characteristics must match the SOS 257 spec."""

    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).name == "Great Hall of the Biblioplex"

    def test_is_land(self) -> None:
        assert isinstance(GreatHallOfTheBiblioplex(owner=None), Land)

    def test_has_land_card_type(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_is_not_a_creature_by_default(self) -> None:
        """Before activating the {5} ability it is a plain (non-creature) land."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.CREATURE not in card.card_types

    def test_has_no_mana_cost(self) -> None:
        """Lands have no mana cost."""
        assert GreatHallOfTheBiblioplex(owner=None).mana_cost == ManaCost()

    def test_is_colorless(self) -> None:
        """No colored pips anywhere -> colorless."""
        assert GreatHallOfTheBiblioplex(owner=None).colors == set()

    def test_cannot_be_cast(self) -> None:
        """Lands are played, not cast."""
        game = create_game()
        card = GreatHallOfTheBiblioplex(owner=game.players[0])
        assert card.can_cast(game) is False


# ---------------------------------------------------------------------------
# Mana abilities
# ---------------------------------------------------------------------------

class TestGreatHallManaAbilities:
    """The land exposes two mana abilities: {C}, and any-color for 1 life."""

    def test_exposes_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 2
        for a in abilities:
            assert isinstance(a, ManaAbility)

    def test_colorless_ability_adds_one_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[0]
        assert ability.cost(game, card) is True
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_colorless_ability_taps_the_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[0]
        assert card.is_tapped is False
        ability.cost(game, card)
        assert card.is_tapped is True

    def test_colorless_ability_cost_fails_when_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[0]
        assert ability.cost(game, card) is False

    def test_any_color_ability_pays_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], life=20)
        # Second ability: {T}, Pay 1 life: Add one mana of any color.
        ability = card.get_mana_abilities()[1]
        # Script the color choice (engine asks controller.choose).
        p1._script.appendleft(ManaType.BLUE)
        assert ability.cost(game, card) is True
        assert p1.life == 19

    def test_any_color_ability_adds_chosen_color(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], life=20)
        ability = card.get_mana_abilities()[1]
        p1._script.appendleft(ManaType.RED)
        ability.cost(game, card)
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.RED) == 1

    def test_any_color_ability_taps_the_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], life=20)
        ability = card.get_mana_abilities()[1]
        p1._script.appendleft(ManaType.GREEN)
        ability.cost(game, card)
        assert card.is_tapped is True

    def test_any_color_ability_cost_fails_when_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True
        set_board_state(game, 0, battlefield=[card], life=20)
        ability = card.get_mana_abilities()[1]
        assert ability.cost(game, card) is False
        # A failed activation must not drain life.
        assert p1.life == 20


# ---------------------------------------------------------------------------
# {5}: animation ability
# ---------------------------------------------------------------------------

class TestGreatHallAnimation:
    """{5}: becomes a 2/4 Wizard creature, still a land."""

    def _animate(self, game, card):
        """Pay {5} and apply the animation activated ability's effect."""
        ability = card.get_activated_abilities()[0]
        # Cost callable should consume 5 generic mana from the controller.
        assert ability.cost(game, card) is True
        ability.effect(game)

    def test_exposes_one_activated_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_animation_cost_consumes_five_generic_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        ability = card.get_activated_abilities()[0]
        assert ability.cost(game, card) is True
        assert p1.mana_pool.total() == 0

    def test_animation_cost_fails_without_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 4})
        ability = card.get_activated_abilities()[0]
        assert ability.cost(game, card) is False

    def test_becomes_a_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        self._animate(game, card)
        game.effect_manager.apply_all(game)
        assert CardType.CREATURE in card.card_types

    def test_is_still_a_land_after_animation(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        self._animate(game, card)
        game.effect_manager.apply_all(game)
        assert CardType.LAND in card.card_types

    def test_becomes_two_four(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        self._animate(game, card)
        game.effect_manager.apply_all(game)
        assert card.power == 2
        assert card.toughness == 4

    def test_becomes_a_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        self._animate(game, card)
        game.effect_manager.apply_all(game)
        assert "Wizard" in card.subtypes

    def test_animation_guarded_when_already_a_creature(self) -> None:
        """The {5} ability does nothing extra if the land is already a creature.

        Applying the animation twice must not double the P/T or otherwise
        stack ("If this land isn't a creature, it becomes...").
        """
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 10})
        self._animate(game, card)
        game.effect_manager.apply_all(game)
        # Second activation while it is already a creature.
        self._animate(game, card)
        game.effect_manager.apply_all(game)
        assert card.power == 2
        assert card.toughness == 4


# ---------------------------------------------------------------------------
# Granted "Whenever you cast an instant or sorcery spell" cast trigger
# (only while animated) — directive item 2.
# ---------------------------------------------------------------------------

def _resolve_full_stack(game) -> None:
    """Pop and resolve every object currently on the stack.

    Casting a spell fires ``SpellCastTriggeredEvent`` which pushes the granted
    +1/+0 trigger as a StackObject above the spell.  Resolving the whole stack
    runs the trigger's ``effect`` (the pump) and then the spell itself.
    """
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _p2_of(game):
    """Return the second (opponent) player."""
    return game.players[1]


class TestGreatHallGrantedCastTrigger:
    """While animated, the creature gets +1/+0 per instant/sorcery YOU cast.

    The granted ability ("Whenever you cast an instant or sorcery spell, this
    creature gets +1/+0 until end of turn") is registered up-front by
    ``register_triggers`` and is inert until the land is animated.  Each
    qualifying cast pumps power by exactly 1 (toughness stays 4); the pumps are
    swept at the cleanup step.
    """

    def _animate(self, game, card) -> None:
        ability = card.get_activated_abilities()[0]
        assert ability.cost(game, card) is True
        ability.effect(game)
        game.effect_manager.apply_all(game)

    def _setup(self):
        """Game with the animated Great Hall on p1's battlefield.

        Returns ``(game, p1, p2, card)``.  The granted cast trigger is
        registered via ``register_triggers`` (as it would be on ETB), then the
        land is animated to a 2/4 creature.
        """
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})
        # Register the granted trigger the way move_to_zone would on ETB.
        card.register_triggers(game)
        self._animate(game, card)
        assert card.power == 2
        assert card.toughness == 4
        return game, p1, _p2_of(game), card

    def _cast_from_hand(self, game, player, spell) -> None:
        """Place *spell* in *player*'s hand and cast it through the engine.

        Casting fires the SpellCastTriggeredEvent; the whole stack is then
        resolved so any granted pump trigger applies.
        """
        player.zones[Zone.HAND].add(spell)
        spell.owner = player
        spell.controller = player
        # Set up sorcery-speed timing (active player, main phase, empty stack)
        # so non-instant spells can be cast through the engine pipeline.
        idx = game.players.index(player)
        game.active_player_index = idx
        game.priority_player_index = idx
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        engine_cast_spell(game, player, spell)
        _resolve_full_stack(game)

    def test_one_instant_cast_pumps_power_by_one(self) -> None:
        game, p1, p2, card = self._setup()
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        self._cast_from_hand(game, p1, bolt)
        # +1/+0: power 2 -> 3, toughness unchanged at 4.
        assert card.power == 3
        assert card.toughness == 4

    def test_one_sorcery_cast_pumps_power_by_one(self) -> None:
        game, p1, p2, card = self._setup()
        sorc = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        self._cast_from_hand(game, p1, sorc)
        assert card.power == 3
        assert card.toughness == 4

    def test_multiple_casts_stack(self) -> None:
        game, p1, p2, card = self._setup()
        self._cast_from_hand(game, p1, Instant(name="Bolt 1", owner=p1, controller=p1))
        assert card.power == 3
        self._cast_from_hand(game, p1, Sorcery(name="Sorc 2", owner=p1, controller=p1))
        assert card.power == 4
        self._cast_from_hand(game, p1, Instant(name="Bolt 3", owner=p1, controller=p1))
        assert card.power == 5
        # Toughness never changes.
        assert card.toughness == 4

    def test_pumps_expire_at_cleanup(self) -> None:
        game, p1, p2, card = self._setup()
        self._cast_from_hand(game, p1, Instant(name="Bolt 1", owner=p1, controller=p1))
        self._cast_from_hand(game, p1, Instant(name="Bolt 2", owner=p1, controller=p1))
        assert card.power == 4
        # Cleanup sweeps the until-end-of-turn pumps; the permanent animation
        # SET_PT effect remains so power resets to the base 2/4.
        _do_cleanup_step(game)
        assert card.power == 2
        assert card.toughness == 4

    def test_no_pump_while_not_animated(self) -> None:
        """A non-creature (un-animated) Great Hall gets no +1/+0 on a cast."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        # Not animated: it is a plain land with no creature type and 0 power.
        assert CardType.CREATURE not in card.card_types
        self._cast_from_hand(game, p1, Instant(name="Bolt", owner=p1, controller=p1))
        # The trigger condition gates on being a creature, so nothing pumps.
        assert CardType.CREATURE not in card.card_types
        assert card.power == 0

    def test_no_pump_for_opponent_spell(self) -> None:
        """Only YOUR instant/sorcery spells trigger the +1/+0."""
        game, p1, p2, card = self._setup()
        opp_bolt = Instant(name="Opp Bolt", owner=p2, controller=p2)
        # p2 casts at instant speed (no timing/zone issues for an instant).
        self._cast_from_hand(game, p2, opp_bolt)
        # The animated creature belongs to p1, so the opponent's spell must not
        # pump it.
        assert card.power == 2
        assert card.toughness == 4

    def test_no_pump_for_noncreature_nonspell_type(self) -> None:
        """A non-instant/sorcery spell (here a creature spell) does not trigger."""
        from engine.card import Creature

        game, p1, p2, card = self._setup()
        bear = Creature(
            name="Test Bear",
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )
        self._cast_from_hand(game, p1, bear)
        # A creature spell is neither instant nor sorcery -> no pump.
        assert card.power == 2
        assert card.toughness == 4
