"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_1.card_impl import TheDawningArchaic
from benchmarks.sos.workspace.engine.casting import get_cost_reduction
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Supertype
from benchmarks.sos.workspace.tests.test_utils import (
    create_game,
    declare_attackers,
    set_board_state,
)


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_legendary_avatar_with_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes
        assert Keyword.REACH in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7
        assert card.base_toughness == 7


class TestTheDawningArchaicCostReduction:
    """Cost reduction should count only your instant and sorcery cards."""

    def test_cost_reduction_counts_only_your_instants_and_sorceries(self) -> None:
        game = create_game()
        p1, p2 = game.players

        set_board_state(
            game,
            0,
            graveyard=[
                Instant(name="Lightning Bolt"),
                Sorcery(name="Divination"),
                Creature(name="Grizzly Bears", base_power=2, base_toughness=2),
            ],
        )
        set_board_state(
            game,
            1,
            graveyard=[Instant(name="Opponent Spell")],
        )

        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 2

    def test_engine_clamps_reduction_to_generic_mana_in_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]

        graveyard = [Instant(name=f"Spell {idx}") for idx in range(12)]
        set_board_state(game, 0, graveyard=graveyard)

        card = TheDawningArchaic(owner=p1, controller=p1)
        assert get_cost_reduction(game, card, p1) == 10


class TestTheDawningArchaicAttackTriggerContract:
    """The printed attack ability should at least register an attack trigger."""

    def test_registers_an_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent


class TestTheDawningArchaicAttackTriggerResolution:
    """Attacking should allow a graveyard free-cast with flashback-style exile."""

    def test_may_decline_attack_trigger_cast(self) -> None:
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        spell = Instant(name="Opt")
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.summoning_sick = False

        set_board_state(game, 0, battlefield=[card], graveyard=[spell])
        card.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(spell)
        assert not game.get_exile(p1).contains(spell)

    def test_attack_trigger_casts_chosen_graveyard_spell_for_free(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = Instant(name="Lightning Bolt")
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.summoning_sick = False
        p1._script.extend([True, spell])

        set_board_state(game, 0, battlefield=[card], graveyard=[spell])
        card.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert not game.stack.is_empty()
        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)

    def test_attack_triggered_graveyard_spell_is_exiled_on_resolution(self) -> None:
        resolved: list[bool] = []

        class TrackingInstant(Instant):
            def on_resolve(self, game) -> None:
                resolved.append(True)

        game = create_game()
        p1 = game.players[0]
        spell = TrackingInstant(name="Ephemeral Insight")
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.summoning_sick = False
        p1._script.extend([True, spell])

        set_board_state(game, 0, battlefield=[card], graveyard=[spell])
        card.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])

        trigger = game.stack.pop()
        trigger.on_resolve(game)
        cast_spell = game.stack.pop()
        cast_spell.on_resolve(game)

        assert resolved == [True]
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
