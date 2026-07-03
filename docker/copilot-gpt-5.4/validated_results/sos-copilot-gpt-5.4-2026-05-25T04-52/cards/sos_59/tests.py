"""Tests for SOS 59 — Matterbending Mage."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_59.card_impl import MatterbendingMage
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class XTestSorcery(Sorcery):
    """Simple X-cost sorcery used to exercise the unblockable trigger."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Variable Formula")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{U}"))
        super().__init__(**kwargs)
        self.x_value = 0


class TestMatterbendingMageProperties:
    """Static card data should match the SOS 59 spec."""

    def test_is_human_wizard_creature(self) -> None:
        card = MatterbendingMage(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = MatterbendingMage(owner=None)
        assert card.name == "Matterbending Mage"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestMatterbendingMageTargeting:
    """The ETB effect should target up to one other creature."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = MatterbendingMage(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_other_creatures_and_rejects_self_and_noncreatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = MatterbendingMage(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        friendly_other = Creature(
            name="Friendly Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_other = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        noncreature = CardImpl(name="Lecture Hall")

        assert req.filter_fn(card) is False
        assert req.filter_fn(friendly_other) is True
        assert req.filter_fn(opposing_other) is True
        assert req.filter_fn(noncreature) is False


class TestMatterbendingMageEtb:
    """Matterbending Mage should bounce up to one other creature on entry."""

    def test_on_resolve_with_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MatterbendingMage(owner=p1, controller=p1)

        card.on_resolve(game)

        assert game.get_hand(p1).get_all() == []

    def test_on_resolve_returns_the_chosen_other_creature_to_its_owners_hand(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(target)
        card = MatterbendingMage(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)

        assert game.get_hand(p2).contains(target)
        assert not game.get_battlefield(p2).contains(target)


class TestMatterbendingMageXSpellTrigger:
    """Matterbending Mage should become unblockable after you cast an X spell."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MatterbendingMage(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_a_spell_with_x_in_its_mana_cost_makes_it_unblockable_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = MatterbendingMage(owner=p1, controller=p1)
        spell = XTestSorcery(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert card._cant_be_blocked is True

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert card._cant_be_blocked is False

    def test_casting_a_spell_without_x_in_its_mana_cost_does_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = MatterbendingMage(owner=p1, controller=p1)
        spell = Sorcery(name="Ordinary Lesson", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
