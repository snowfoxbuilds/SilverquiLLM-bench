"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.casting import counter_stack_object, get_cost_reduction
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class _TrackingInstant(Instant):
    """Simple instant used to observe free-cast + exile-on-resolution behavior."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Tracking Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        super().__init__(**kwargs)
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True


def _resolve_attack_trigger(game, archaic: TheDawningArchaic) -> None:
    game.trigger_manager.fire_event(
        game,
        AttacksTriggeredEvent(creature=archaic, attacker=archaic),
    )
    assert len(game.stack) == 1
    trigger = game.stack.pop()
    assert trigger.source is archaic
    trigger.on_resolve(game)


class TestTheDawningArchaicProperties:
    """Static characteristics should match the card spec."""

    def test_is_legendary_avatar_creature_with_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes
        assert Keyword.REACH in card.keywords

    def test_mana_cost_and_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7
        assert card.base_toughness == 7


class TestTheDawningArchaicCostReduction:
    """Casting cost reduction should only count your graveyard's instants/sorceries."""

    def test_counts_only_your_instants_and_sorceries_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)

        your_instant = Instant(name="Shock")
        your_sorcery = Sorcery(name="Divination")
        your_creature = Creature(name="Bear", base_power=2, base_toughness=2)
        opponent_instant = Instant(name="Opt")

        set_board_state(
            game,
            0,
            graveyard=[your_instant, your_sorcery, your_creature],
        )
        set_board_state(game, 1, graveyard=[opponent_instant])

        assert get_cost_reduction(game, card, p1) == 2
        assert get_cost_reduction(game, card, p2) == 1

    def test_cost_reduction_is_clamped_by_generic_mana_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_spells = [Instant(name=f"Spell {i}") for i in range(12)]

        set_board_state(game, 0, graveyard=graveyard_spells)

        assert get_cost_reduction(game, card, p1) == 10


class TestTheDawningArchaicAttackTrigger:
    """Attack trigger should let you free-cast a graveyard instant/sorcery."""

    def test_registers_an_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent
        assert triggers[0].controller is p1

    def test_attack_trigger_does_nothing_without_instant_or_sorcery_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        creature_card = Creature(name="Bear", base_power=2, base_toughness=2)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[creature_card])
        archaic.register_triggers(game)

        p1.choose_target = lambda options, requirement: (_ for _ in ()).throw(
            AssertionError("target choice should not be requested without legal graveyard spell targets")
        )
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        assert game.get_graveyard(p1).contains(creature_card)
        assert len(game.stack) == 0

    def test_attack_trigger_declares_graveyard_spell_target_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        archaic = TheDawningArchaic(owner=p1, controller=p1)

        your_instant = Instant(name="Shock", owner=p1, controller=p1)
        your_sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        your_creature = Creature(
            name="Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opponent_instant = Instant(name="Opt", owner=p2, controller=p2)

        archaic.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(archaic)[0]
        requirements = trigger.target_requirements(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        assert len(requirements) == 1
        requirement = requirements[0]
        assert requirement.zone == Zone.GRAVEYARD
        assert "target instant or sorcery card in your graveyard" in requirement.description
        assert requirement.filter_fn(your_instant) is True
        assert requirement.filter_fn(your_sorcery) is True
        assert requirement.filter_fn(your_creature) is False
        assert requirement.filter_fn(opponent_instant) is False

    def test_attack_trigger_stack_object_stores_the_selected_graveyard_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        your_instant = Instant(name="Shock", owner=p1, controller=p1)
        your_sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        your_creature = Creature(
            name="Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opponent_instant = Instant(name="Opt", owner=p2, controller=p2)

        set_board_state(
            game,
            0,
            battlefield=[archaic],
            graveyard=[your_instant, your_sorcery, your_creature],
        )
        set_board_state(game, 1, graveyard=[opponent_instant])
        archaic.register_triggers(game)

        seen: dict[str, object] = {}

        def _choose_target(options, requirement):
            seen["options"] = list(options)
            seen["requirement"] = requirement
            return your_sorcery

        p1.choose_target = _choose_target

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        assert seen["options"] == [your_instant, your_sorcery]
        trigger_obj = game.stack.peek()
        assert trigger_obj is not None
        assert trigger_obj.source is archaic
        assert trigger_obj.is_spell is False
        assert trigger_obj.target_requirements == [seen["requirement"]]
        assert trigger_obj.chosen_targets == [your_sorcery]

    def test_attack_trigger_is_optional(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = _TrackingInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        archaic.register_triggers(game)

        p1.choose_yes_no = lambda prompt: False
        p1.choose_card = lambda cards, description: spell
        p1.choose_target = lambda options, requirement: spell

        _resolve_attack_trigger(game, archaic)

        assert game.get_graveyard(p1).contains(spell)
        assert len(game.stack) == 0

    def test_attack_trigger_casts_target_spell_for_free_and_exiles_it_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = _TrackingInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        archaic.register_triggers(game)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: spell
        p1.choose_target = lambda options, requirement: spell

        assert p1.mana_pool.total() == 0

        _resolve_attack_trigger(game, archaic)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert p1.mana_pool.total() == 0

        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)

        assert spell.was_resolved is True
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)

    def test_attack_trigger_exiles_the_free_cast_spell_if_it_is_countered(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = _TrackingInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        archaic.register_triggers(game)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_target = lambda options, requirement: spell

        _resolve_attack_trigger(game, archaic)

        stack_obj = game.stack.peek()
        assert stack_obj is not None
        assert stack_obj.source is spell

        assert counter_stack_object(game, stack_obj) is True

        assert spell.was_resolved is False
        assert len(game.stack) == 0
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
