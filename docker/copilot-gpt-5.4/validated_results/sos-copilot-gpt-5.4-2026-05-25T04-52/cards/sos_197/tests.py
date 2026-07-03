"""Tests for SOS 197 — Killian's Confidence."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_197.card_impl import KilliansConfidence
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.events import DealsDamageTriggeredEvent
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestKilliansConfidenceProperties:
    """Static card data should match the SOS 197 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(KilliansConfidence(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = KilliansConfidence(owner=None)

        assert card.name == "Killian's Confidence"
        assert card.mana_cost == ManaCost.parse("{W}{B}")


class TestKilliansConfidenceTargeting:
    """Killian's Confidence should target a single creature on the battlefield."""

    def test_returns_single_battlefield_creature_target_requirement(self) -> None:
        game = create_game()
        reqs = KilliansConfidence(owner=None).get_targets(game)
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Hall")

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[0].filter_fn(creature) is True
        assert reqs[0].filter_fn(non_creature) is False


class TestKilliansConfidenceResolution:
    """Killian's Confidence should pump a creature and draw a card."""

    def test_on_resolve_gives_target_plus_one_plus_one_until_end_of_turn_and_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Trusted Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        drawn = CardImpl(name="Fresh Lesson", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[target])
        game.get_library(p1).add(drawn)

        spell = KilliansConfidence(owner=p1, controller=p1)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.power == 3
        assert target.toughness == 3
        assert game.get_hand(p1).contains(drawn)

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.power == 2
        assert target.toughness == 2


class TestKilliansConfidenceGraveyardTrigger:
    """Killian's Confidence should return itself from the graveyard after combat damage if paid for."""

    def test_registers_a_damage_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = KilliansConfidence(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is DealsDamageTriggeredEvent

    def test_combat_damage_from_your_creature_to_a_player_may_be_paid_with_black_to_return_this_card_from_your_graveyard_to_your_hand(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = KilliansConfidence(owner=p1, controller=p1)
        attacker = Creature(
            name="Confident Attacker",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[attacker], graveyard=[card])
        card.register_triggers(game)
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1._script.append(True)

        game.trigger_manager.fire_event(
            game,
            DealsDamageTriggeredEvent(
                source=attacker,
                target=p2,
                amount=2,
                is_combat=True,
                combat=True,
            ),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert not game.get_graveyard(p1).contains(card)
        assert game.get_hand(p1).contains(card)
        assert p1.mana_pool.total() == 0

    def test_noncombat_damage_does_not_trigger_the_graveyard_return(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = KilliansConfidence(owner=p1, controller=p1)
        attacker = Creature(
            name="Practice Attacker",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[attacker], graveyard=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            DealsDamageTriggeredEvent(
                source=attacker,
                target=p2,
                amount=2,
                is_combat=False,
                combat=False,
            ),
        )

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(card)
        assert not game.get_hand(p1).contains(card)

