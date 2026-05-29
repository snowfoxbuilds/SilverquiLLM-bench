"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as engine_cast_spell
from engine.events import AttacksTriggeredEvent
from engine.types import Keyword, ManaCost, ManaType, Phase, Supertype, Zone
from test_utils import create_game, declare_attackers, set_board_state


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_mana_cost_is_ten_generic(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_is_legendary_avatar_with_reach_and_seven_seven(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes
        assert Keyword.REACH in card.keywords
        assert card.base_power == 7
        assert card.base_toughness == 7


class TestTheDawningArchaicCostReduction:
    """The graveyard-spell discount should affect casting cost."""

    def test_cast_succeeds_with_three_graveyard_spells_and_only_seven_mana(self) -> None:
        game = create_game()
        player = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        graveyard_cards = [
            Instant(name="First Spark", mana_cost=ManaCost.parse("{R}")),
            Instant(name="Second Spark", mana_cost=ManaCost.parse("{R}")),
            Sorcery(name="Deep Study", mana_cost=ManaCost.parse("{2}{U}")),
            Creature(name="Bear", base_power=2, base_toughness=2),
        ]
        set_board_state(
            game,
            0,
            hand=[archaic],
            graveyard=graveyard_cards,
            mana={ManaType.COLORLESS: 7},
        )
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        engine_cast_spell(game, player, archaic)
        spell_obj = game.stack.pop()
        spell_obj.on_resolve(game)

        assert game.get_battlefield(player).contains(archaic)

    def test_creature_cards_in_graveyard_do_not_reduce_the_cost(self) -> None:
        game = create_game()
        player = game.players[0]
        archaic = TheDawningArchaic(owner=player, controller=player)
        set_board_state(
            game,
            0,
            hand=[archaic],
            graveyard=[Creature(name="Bear", base_power=2, base_toughness=2)],
            mana={ManaType.COLORLESS: 9},
        )
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, player, archaic)


class TestTheDawningArchaicAttackTrigger:
    """Attack trigger should let you free-cast a graveyard spell."""

    def test_registers_an_attacks_trigger(self) -> None:
        game = create_game()
        player = game.players[0]
        archaic = TheDawningArchaic(owner=player, controller=player)

        archaic.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_attack_trigger_free_casts_a_chosen_graveyard_spell(self) -> None:
        game = create_game()
        player = game.players[0]
        archaic = TheDawningArchaic(owner=player, controller=player)
        spell = Sorcery(name="Recovered Insight", mana_cost=ManaCost.parse("{3}{U}"))
        off_type = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell, off_type])

        def choose_card(cards, description):
            assert spell in cards
            assert off_type not in cards
            return spell

        player.choose_card = choose_card
        player.choose_target = lambda options, requirement: spell
        player.choose_yes_no = lambda prompt: True

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert player.zones[Zone.STACK].contains(spell)
        assert not player.zones[Zone.GRAVEYARD].contains(spell)
        assert player.mana_pool.total() == 0

    def test_attack_trigger_may_decline_the_free_cast(self) -> None:
        game = create_game()
        player = game.players[0]
        archaic = TheDawningArchaic(owner=player, controller=player)
        spell = Instant(name="Hidden Bolt", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])

        player.choose_card = lambda cards, description: spell
        player.choose_target = lambda options, requirement: spell
        player.choose_yes_no = lambda prompt: False

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert player.zones[Zone.GRAVEYARD].contains(spell)
        assert game.stack.is_empty()

    def test_spell_cast_by_the_attack_trigger_is_exiled_after_resolution(self) -> None:
        game = create_game()
        player = game.players[0]
        archaic = TheDawningArchaic(owner=player, controller=player)
        spell = Instant(name="Recovered Bolt", mana_cost=ManaCost.parse("{2}{R}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])

        player.choose_card = lambda cards, description: spell
        player.choose_target = lambda options, requirement: spell
        player.choose_yes_no = lambda prompt: True

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)
        spell_obj = game.stack.pop()
        spell_obj.on_resolve(game)

        assert player.zones[Zone.EXILE].contains(spell)
        assert not player.zones[Zone.GRAVEYARD].contains(spell)

    def test_declare_attackers_step_fires_the_attack_trigger_end_to_end(self) -> None:
        game = create_game()
        player = game.players[0]
        archaic = TheDawningArchaic(owner=player, controller=player)
        spell = Instant(name="Recovered Bolt", mana_cost=ManaCost.parse("{2}{R}"))
        archaic.summoning_sick = False
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])

        player.choose_card = lambda cards, description: spell
        player.choose_yes_no = lambda prompt: True

        archaic.register_triggers(game)
        declare_attackers(game, ["The Dawning Archaic"])

        trigger_obj = game.stack.pop()
        assert trigger_obj.source is archaic

        trigger_obj.on_resolve(game)

        assert player.zones[Zone.STACK].contains(spell)
        assert not player.zones[Zone.GRAVEYARD].contains(spell)

        spell_obj = game.stack.pop()
        spell_obj.on_resolve(game)

        assert player.zones[Zone.EXILE].contains(spell)
