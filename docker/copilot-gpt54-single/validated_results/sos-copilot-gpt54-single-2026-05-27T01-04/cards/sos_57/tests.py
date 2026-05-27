"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import CardImpl, Creature, Instant
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import advance_to_phase, create_game, set_board_state


class TrackingSpell(Instant):
    """Simple stack spell that exposes how much mana was spent to cast it."""

    def __init__(self, mana_spent_to_cast: int = 0, **kwargs) -> None:
        kwargs.setdefault("name", "Tracking Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)
        self.mana_spent_to_cast = mana_spent_to_cast


def _put_spell_on_stack(game, player, spell: Instant) -> StackObject:
    """Place *spell* onto the stack and into the player's stack zone."""
    spell.owner = player
    spell.controller = player
    player.zones[Zone.STACK].add(spell)
    stack_obj = StackObject(source=spell, controller=player)
    game.stack.push(stack_obj)
    return stack_obj


def _wizard_for(player) -> Creature:
    """Create a simple Wizard permanent for controller checks."""
    wizard = Creature(
        name="Apprentice Wizard",
        owner=player,
        controller=player,
        base_power=1,
        base_toughness=1,
    )
    wizard.subtypes = {"Human", "Wizard"}
    return wizard


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_an_instant_named_mana_sculpt(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert card.name == "Mana Sculpt"
        assert CardType.INSTANT in card.card_types

    def test_has_the_expected_mana_cost_and_rules_text(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert card.rules_text == (
            "Counter target spell. If you control a Wizard, add an amount of "
            "{C} equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase."
        )


class TestManaSculptTargeting:
    """Mana Sculpt must target a spell on the stack."""

    def test_cannot_be_cast_when_no_spell_is_on_the_stack(self) -> None:
        game = create_game()
        assert ManaSculpt(owner=game.players[0], controller=game.players[0]).can_cast(game) is False

    def test_can_be_cast_when_a_spell_is_on_the_stack(self) -> None:
        game = create_game()
        _put_spell_on_stack(game, game.players[1], TrackingSpell(owner=game.players[1], controller=game.players[1]))

        assert ManaSculpt(owner=game.players[0], controller=game.players[0]).can_cast(game) is True

    def test_get_targets_returns_one_stack_spell_requirement(self) -> None:
        game = create_game()
        _put_spell_on_stack(game, game.players[1], TrackingSpell(owner=game.players[1], controller=game.players[1]))
        reqs = ManaSculpt(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].description == "target spell"
        assert reqs[0].zone == Zone.STACK

    def test_target_filter_accepts_spells_and_rejects_nonspell_stack_objects(self) -> None:
        game = create_game()
        _put_spell_on_stack(game, game.players[1], TrackingSpell(owner=game.players[1], controller=game.players[1]))
        req = ManaSculpt(owner=None).get_targets(game)[0]

        spell_obj = StackObject(source=Instant(name="Target Spell"), controller=game.players[0])
        ability_obj = StackObject(source=CardImpl(name="Activated Ability"), controller=game.players[0])
        ability_obj.is_spell = False

        assert req.filter_fn(spell_obj) is True
        assert req.filter_fn(ability_obj) is False


class TestManaSculptResolution:
    """Resolution should counter the chosen target spell and apply its rider correctly."""

    def test_no_chosen_target_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = TrackingSpell(owner=p2, controller=p2, mana_spent_to_cast=3)
        target_obj = _put_spell_on_stack(game, p2, target_spell)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert game.stack.peek() is target_obj
        assert p2.zones[Zone.STACK].contains(target_spell)
        assert not p2.zones[Zone.GRAVEYARD].contains(target_spell)

    def test_chosen_target_spell_is_countered_and_put_into_its_owners_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = TrackingSpell(owner=p2, controller=p2, mana_spent_to_cast=3)
        target_obj = _put_spell_on_stack(game, p2, target_spell)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_obj]
        spell.on_resolve(game)

        assert game.stack.is_empty()
        assert not p2.zones[Zone.STACK].contains(target_spell)
        assert p2.zones[Zone.GRAVEYARD].contains(target_spell)

    def test_wizard_rider_adds_no_mana_immediately_but_adds_colorless_at_your_next_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = _wizard_for(p1)
        target_spell = TrackingSpell(owner=p2, controller=p2, mana_spent_to_cast=5)
        target_obj = _put_spell_on_stack(game, p2, target_spell)

        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(game, 0, battlefield=[wizard])

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_obj]
        spell.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 5

    def test_without_a_wizard_you_do_not_get_the_delayed_colorless_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = TrackingSpell(owner=p2, controller=p2, mana_spent_to_cast=4)
        target_obj = _put_spell_on_stack(game, p2, target_spell)

        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_obj]
        spell.on_resolve(game)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_wizard_check_is_locked_in_when_mana_sculpt_resolves(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = _wizard_for(p1)
        target_spell = TrackingSpell(owner=p2, controller=p2, mana_spent_to_cast=6)
        target_obj = _put_spell_on_stack(game, p2, target_spell)

        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(game, 0, battlefield=[wizard])

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_obj]
        spell.on_resolve(game)

        game.get_battlefield(p1).remove(wizard)
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 6
