"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.casting import resolve_top
from engine.events import AttacksTriggeredEvent
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


def _make_test_instant(name: str = "Test Spell", cost: str = "{1}") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _make_test_creature(name: str = "Test Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_legendary_avatar_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_power_and_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords


class TestTheDawningArchaicCostReduction:
    """Casting cost reduction depends on spells in your graveyard."""

    def test_cost_reduction_counts_only_instants_and_sorceries_in_your_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players

        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            graveyard=[
                _make_test_instant("P1 Instant"),
                Instant(name="P1 Second Instant", mana_cost=ManaCost.parse("{2}")),
                _make_test_creature("P1 Creature"),
            ],
        )
        set_board_state(
            game,
            1,
            graveyard=[_make_test_instant("P2 Instant")],
        )

        assert card.cost_reduction(game) == 2

    def test_one_spell_in_graveyard_allows_casting_with_nine_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            graveyard=[_make_test_instant()],
            mana={ManaType.COLORLESS: 9},
        )

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(card)

    def test_cost_reduction_is_capped_at_full_generic_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        graveyard = [_make_test_instant(f"Spell {idx}") for idx in range(11)]
        set_board_state(game, 0, hand=[card], graveyard=graveyard, mana={})

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(card)


class TestTheDawningArchaicAttackTrigger:
    """Attack trigger should offer a free cast from the graveyard."""

    def test_registers_attack_trigger_on_typed_attack_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_attack_trigger_noops_when_graveyard_has_no_instant_or_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        non_spell = _make_test_creature()
        set_board_state(game, 0, battlefield=[card], graveyard=[non_spell])

        def _unexpected_yes_no(_prompt: str) -> bool:
            raise AssertionError("should not ask to cast when no legal graveyard spell exists")

        def _unexpected_choose_card(_cards: object, _description: str) -> object:
            raise AssertionError("should not ask for a graveyard target when none is legal")

        p1.choose_yes_no = _unexpected_yes_no  # type: ignore[method-assign]
        p1.choose_card = _unexpected_choose_card  # type: ignore[method-assign]

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        if not game.stack.is_empty():
            resolve_top(game)

        assert game.stack.is_empty()
        assert p1.zones[Zone.GRAVEYARD].contains(non_spell)

    def test_attack_trigger_may_decline_to_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = _make_test_instant()
        set_board_state(game, 0, battlefield=[card], graveyard=[spell])

        p1.choose_yes_no = lambda _prompt: False  # type: ignore[method-assign]
        p1.choose_card = lambda cards, _description: cards[0]  # type: ignore[method-assign]

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        resolve_top(game)

        assert game.stack.is_empty()
        assert p1.zones[Zone.GRAVEYARD].contains(spell)
        assert not p1.zones[Zone.EXILE].contains(spell)

    def test_attack_trigger_casts_spell_for_free_and_exiles_it_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = _make_test_instant(cost="{9}")
        set_board_state(game, 0, battlefield=[card], graveyard=[spell], mana={})

        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]
        p1.choose_card = lambda cards, _description: cards[0]  # type: ignore[method-assign]

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        resolve_top(game)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

        resolve_top(game)

        assert p1.zones[Zone.EXILE].contains(spell)
        assert not p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_attack_trigger_locks_in_the_chosen_graveyard_target_on_the_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        first_spell = _make_test_instant("First Spell")
        chosen_spell = _make_test_instant("Chosen Spell", cost="{8}")
        set_board_state(
            game,
            0,
            battlefield=[card],
            graveyard=[first_spell, chosen_spell],
            mana={},
        )

        choose_calls: list[list[Instant]] = []

        def _choose_card(cards: list[Instant], _description: str) -> Instant:
            choose_calls.append(list(cards))
            return chosen_spell

        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]
        p1.choose_card = _choose_card  # type: ignore[method-assign]

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        assert len(choose_calls) == 1
        assert len(game.stack) == 1
        trigger_on_stack = game.stack.peek()
        assert trigger_on_stack is not None
        assert trigger_on_stack.source is card
        assert trigger_on_stack.targets == [chosen_spell]

        resolve_top(game)

        assert len(choose_calls) == 1
        assert len(game.stack) == 1
        assert game.stack.peek().source is chosen_spell
        assert not p1.zones[Zone.GRAVEYARD].contains(chosen_spell)
        assert p1.zones[Zone.GRAVEYARD].contains(first_spell)

        resolve_top(game)

        assert p1.zones[Zone.EXILE].contains(chosen_spell)
        assert p1.zones[Zone.GRAVEYARD].contains(first_spell)

    def test_attack_trigger_does_not_cast_if_target_left_graveyard_before_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = _make_test_instant("Escaped Spell")
        set_board_state(game, 0, battlefield=[card], graveyard=[spell], mana={})

        def _unexpected_yes_no(_prompt: str) -> bool:
            raise AssertionError("should not offer the optional cast after the target becomes illegal")

        p1.choose_yes_no = _unexpected_yes_no  # type: ignore[method-assign]
        p1.choose_card = lambda cards, _description: cards[0]  # type: ignore[method-assign]

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        trigger_on_stack = game.stack.peek()
        assert trigger_on_stack is not None
        assert trigger_on_stack.targets == [spell]

        p1.zones[Zone.GRAVEYARD].remove(spell)
        p1.zones[Zone.EXILE].add(spell)

        resolve_top(game)

        assert game.stack.is_empty()
        assert p1.zones[Zone.EXILE].contains(spell)
        assert not p1.zones[Zone.GRAVEYARD].contains(spell)
