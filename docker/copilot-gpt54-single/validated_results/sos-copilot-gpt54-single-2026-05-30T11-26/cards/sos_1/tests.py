"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


class _TestGraveyardInstant(Instant):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Test Graveyard Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{9}{U}"))
        super().__init__(**kwargs)
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True
        if self.controller is not None:
            self.controller.life += 2


class _TestGraveyardSorcery(Sorcery):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Test Graveyard Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{9}{R}"))
        super().__init__(**kwargs)
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True
        if self.controller is not None:
            self.controller.life += 3


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestTheDawningArchaicProperties:
    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_is_legendary_avatar_with_reach_and_seven_seven_stats(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Avatar"} <= card.subtypes
        assert Keyword.REACH in card.keywords
        assert card.base_power == 7
        assert card.base_toughness == 7


class TestTheDawningArchaicCostReduction:
    def test_cost_reduction_counts_only_instants_and_sorceries_in_your_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players

        archaic = TheDawningArchaic(owner=p1, controller=p1)
        own_instant = _TestGraveyardInstant(owner=p1, controller=p1)
        own_sorcery = _TestGraveyardSorcery(owner=p1, controller=p1)
        own_creature = Creature(
            name="Graveyard Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opponent_instant = _TestGraveyardInstant(owner=p2, controller=p2)

        set_board_state(
            game,
            0,
            graveyard=[own_instant, own_sorcery, own_creature],
        )
        set_board_state(game, 1, graveyard=[opponent_instant])

        assert archaic.cost_reduction(game) == 2

    def test_can_be_cast_for_reduced_cost_based_on_graveyard_count(self) -> None:
        game = create_game()
        p1 = game.players[0]

        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[archaic],
            graveyard=[
                _TestGraveyardInstant(owner=p1, controller=p1),
                _TestGraveyardSorcery(owner=p1, controller=p1),
            ],
            mana={ManaType.COLORLESS: 8},
        )

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(archaic)


class TestTheDawningArchaicAttackTrigger:
    def test_register_triggers_adds_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic])

        archaic.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_attack_trigger_only_fires_when_dawning_archaic_attacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        other_attacker = Creature(
            name="Other Attacker",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = _TestGraveyardInstant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic, other_attacker], graveyard=[spell])

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=other_attacker, attacker=other_attacker),
        )

        assert game.stack.is_empty()
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        assert not game.stack.is_empty()
        assert game.get_graveyard(p1).contains(spell)
        assert spell.was_resolved is False

    def test_attack_trigger_may_be_declined(self) -> None:
        game = create_game(scripts=([None], []))
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = _TestGraveyardInstant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        assert not game.stack.is_empty()
        _resolve_all(game)

        assert spell.was_resolved is False
        assert game.get_graveyard(p1).contains(spell)
        assert not game.get_exile(p1).contains(spell)

    def test_attack_trigger_is_noop_with_no_instant_or_sorcery_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        creature_card = Creature(
            name="Only Creature Card",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[archaic], graveyard=[creature_card])

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        assert not game.stack.is_empty()
        _resolve_all(game)

        assert game.get_graveyard(p1).contains(creature_card)
        assert not game.get_exile(p1).contains(creature_card)

    def test_attack_trigger_casts_chosen_instant_from_graveyard_for_free_and_exiles_it(self) -> None:
        game = create_game(scripts=([None], []))
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = _TestGraveyardInstant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        p1._script.clear()
        p1._script.append(spell)

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_all(game)

        assert spell.was_resolved is True
        assert p1.life == 22
        assert not game.get_graveyard(p1).contains(spell)
        assert game.get_exile(p1).contains(spell)

    def test_attack_trigger_casts_chosen_sorcery_and_leaves_unchosen_spell_in_graveyard(self) -> None:
        game = create_game(scripts=([None], []))
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        unchosen_instant = _TestGraveyardInstant(owner=p1, controller=p1)
        chosen_sorcery = _TestGraveyardSorcery(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[archaic],
            graveyard=[unchosen_instant, chosen_sorcery],
        )
        p1._script.clear()
        p1._script.append(chosen_sorcery)

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_all(game)

        assert chosen_sorcery.was_resolved is True
        assert p1.life == 23
        assert game.get_exile(p1).contains(chosen_sorcery)
        assert not game.get_graveyard(p1).contains(chosen_sorcery)
        assert game.get_graveyard(p1).contains(unchosen_instant)
