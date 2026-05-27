"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.casting import cast_spell
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.game import deal_damage
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TrackingSorcery(Sorcery):
    """Simple no-target sorcery used to verify casualty-created copies."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Tracking Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        super().__init__(**kwargs)
        self.resolution_count = 0

    def on_resolve(self, game) -> None:
        self.resolution_count += 1


class TrainingBolt(Instant):
    """Simple targeted instant used to verify copy retargeting."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        chosen = getattr(self, "chosen_targets", []) or []
        if not chosen:
            return

        target = chosen[0]
        if any(game.get_battlefield(player).contains(target) for player in game.players):
            deal_damage(game, self, target, 2)


def _set_main_phase(game) -> None:
    """Put player 1 into a clean precombat main phase with priority."""
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


class TestSilverquillTheDisputantProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_a_legendary_elder_dragon_creature_named_silverquill_the_disputant(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Silverquill, the Disputant"
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_has_expected_mana_cost_keywords_stats_and_rules_text(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4
        assert card.base_toughness == 4
        assert card.rules_text == (
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power "
            "1 or greater. When you do, copy the spell and you may choose new "
            "targets for the copy.)"
        )


class TestSilverquillTheDisputantCasualty:
    """Silverquill should grant casualty 1 to your instants and sorceries."""

    def test_registers_one_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)

        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent
        assert triggers[0].controller is p1

    def test_only_your_instants_and_sorceries_trigger_the_granted_casualty_ability(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        your_instant = Instant(name="Your Instant", owner=p1, controller=p1)
        your_sorcery = Sorcery(name="Your Sorcery", owner=p1, controller=p1)
        your_creature_spell = Creature(
            name="Your Creature Spell",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_instant = Instant(name="Opposing Instant", owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=your_instant,
                player=p1,
                card=your_instant,
                controller=p1,
            ),
        )
        assert len(game.stack) == 1
        assert game.stack.pop().source is card

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=your_sorcery,
                player=p1,
                card=your_sorcery,
                controller=p1,
            ),
        )
        assert len(game.stack) == 1
        assert game.stack.pop().source is card

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=your_creature_spell,
                player=p1,
                card=your_creature_spell,
                controller=p1,
            ),
        )
        assert game.stack.is_empty()

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=opposing_instant,
                player=p2,
                card=opposing_instant,
                controller=p2,
            ),
        )
        assert game.stack.is_empty()

    def test_declining_casualty_does_not_sacrifice_a_creature_or_create_a_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Inkling",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = TrackingSorcery(owner=p1, controller=p1)

        p1.choose_yes_no = lambda _prompt: False  # type: ignore[method-assign]
        p1.choose_card = lambda cards, _description="": fodder  # type: ignore[method-assign]
        p1.choose_target = lambda _options, _requirement: fodder  # type: ignore[method-assign]

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[card, fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, p1, spell)

        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)
        assert len(game.stack) == 1
        assert game.stack.peek() is not None
        assert game.stack.peek().source is spell

    def test_paying_casualty_sacrifices_an_eligible_creature_during_cast_and_creates_a_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Inkling",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = TrackingSorcery(owner=p1, controller=p1)

        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]
        p1.choose_card = lambda cards, _description="": fodder  # type: ignore[method-assign]
        p1.choose = lambda options, _description="": fodder  # type: ignore[method-assign]
        p1.choose_target = lambda _options, _requirement: fodder  # type: ignore[method-assign]

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[card, fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, p1, spell)

        assert not game.get_battlefield(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(fodder)
        assert len(game.stack) == 2
        assert game.stack.peek() is not None
        assert game.stack.peek().source is card

        casualty_trigger = game.stack.pop()
        casualty_trigger.on_resolve(game)

        assert len(game.stack) == 2
        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.source is not spell
        assert copy_obj.source.name == "Tracking Sorcery"

        game.stack.pop().on_resolve(game)
        assert copy_obj.source.resolution_count == 1

        original_obj = game.stack.pop()
        assert original_obj.source is spell
        original_obj.on_resolve(game)
        assert spell.resolution_count == 1

    def test_creatures_with_power_zero_cannot_pay_casualty_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        ineligible = Creature(
            name="Harmless Assistant",
            owner=p1,
            controller=p1,
            base_power=0,
            base_toughness=2,
        )
        spell = TrackingSorcery(owner=p1, controller=p1)

        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]
        p1.choose_card = lambda cards, _description="": ineligible  # type: ignore[method-assign]
        p1.choose = lambda options, _description="": ineligible  # type: ignore[method-assign]
        p1.choose_target = lambda _options, _requirement: ineligible  # type: ignore[method-assign]

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[card, ineligible],
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, p1, spell)

        assert game.get_battlefield(p1).contains(ineligible)
        assert not game.get_graveyard(p1).contains(ineligible)
        assert len(game.stack) == 1
        assert game.stack.peek() is not None
        assert game.stack.peek().source is spell

    def test_copied_spell_may_take_new_targets_without_changing_the_original_spell_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Inkling",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        original_target = Creature(
            name="First Target",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        new_target = Creature(
            name="Second Target",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        spell = TrainingBolt(owner=p1, controller=p1)
        target_choices = [original_target, new_target]

        p1.choose_yes_no = (
            lambda _prompt, answers=[True, True]: answers.pop(0) if answers else True
        )  # type: ignore[method-assign]
        p1.choose_card = lambda cards, _description="": fodder  # type: ignore[method-assign]
        p1.choose = lambda options, _description="": fodder  # type: ignore[method-assign]

        def _choose_target(options, requirement):
            if options and isinstance(options[0], TargetRequirement):
                return target_choices.pop(0)
            if fodder in options and original_target not in options and new_target not in options:
                return fodder
            if new_target in options:
                return target_choices.pop(0)
            return fodder

        p1.choose_target = _choose_target  # type: ignore[method-assign]

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[card, fodder],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[original_target, new_target])
        card.register_triggers(game)

        cast_spell(game, p1, spell)

        assert not game.get_battlefield(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(fodder)
        assert len(game.stack) == 2
        original_stack_obj = game.stack.objects()[1]
        assert original_stack_obj.source is spell
        assert original_stack_obj.targets == [original_target]

        casualty_trigger = game.stack.pop()
        casualty_trigger.on_resolve(game)

        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.source is not spell
        assert copy_obj.targets == [new_target]
        assert original_stack_obj.targets == [original_target]

        game.stack.pop().on_resolve(game)
        assert new_target.damage_marked == 2
        assert original_target.damage_marked == 0

        original_stack_obj = game.stack.pop()
        original_stack_obj.on_resolve(game)
        assert original_target.damage_marked == 2
