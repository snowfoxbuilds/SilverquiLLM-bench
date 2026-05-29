"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as engine_cast_spell
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


class TestPingInstant(Instant):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Test Ping Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        if not getattr(self, "chosen_targets", None):
            return
        deal_damage(game, self, self.chosen_targets[0], 1)


class TestPingSorcery(Sorcery):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Test Ping Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        if not getattr(self, "chosen_targets", None):
            return
        deal_damage(game, self, self.chosen_targets[0], 1)


def _creature(name: str, power: int, toughness: int, cost: str | None = None) -> Creature:
    kwargs = {
        "name": name,
        "base_power": power,
        "base_toughness": toughness,
    }
    if cost is not None:
        kwargs["mana_cost"] = ManaCost.parse(cost)
    return Creature(**kwargs)


def _set_main_phase(game) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


class TestSilverquillTheDisputantProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_a_legendary_elder_dragon_creature_with_flying_and_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords

    def test_name_mana_cost_and_power_toughness_match_the_spec(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestSilverquillTheDisputantCasualty:
    """Silverquill should grant casualty 1 to the controller's instants and sorceries."""

    def test_casting_an_instant_can_sacrifice_a_power_one_creature_to_copy_it_and_choose_new_targets(self) -> None:
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        disputant = SilverquillTheDisputant(owner=player, controller=player)
        fodder = _creature("Inkling Token", 1, 1)
        first_target = _creature("First Target", 2, 2)
        second_target = _creature("Second Target", 2, 2)
        spell = TestPingInstant(owner=player, controller=player)
        target_choices = iter([first_target, second_target])

        set_board_state(
            game,
            0,
            battlefield=[disputant, fodder],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[first_target, second_target])
        _set_main_phase(game)
        disputant.register_triggers(game)
        player.choose_yes_no = lambda prompt: True
        player.choose_card = lambda cards, description: fodder
        player.choose_target = lambda options, requirement: next(target_choices)

        engine_cast_spell(game, player, spell)
        _resolve_all(game)

        assert player.zones[Zone.GRAVEYARD].contains(fodder)
        assert not player.zones[Zone.BATTLEFIELD].contains(fodder)
        assert first_target.damage_marked == 1
        assert second_target.damage_marked == 1
        assert player.zones[Zone.GRAVEYARD].contains(spell)

    def test_declining_casualty_leaves_the_creature_on_the_battlefield_and_resolves_only_once(self) -> None:
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        disputant = SilverquillTheDisputant(owner=player, controller=player)
        fodder = _creature("Inkling Token", 1, 1)
        target = _creature("Only Target", 2, 2)
        spell = TestPingInstant(owner=player, controller=player)

        set_board_state(
            game,
            0,
            battlefield=[disputant, fodder],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        _set_main_phase(game)
        disputant.register_triggers(game)
        player.choose_yes_no = lambda prompt: False
        player.choose_target = lambda options, requirement: target

        engine_cast_spell(game, player, spell)
        _resolve_all(game)

        assert player.zones[Zone.BATTLEFIELD].contains(fodder)
        assert not player.zones[Zone.GRAVEYARD].contains(fodder)
        assert target.damage_marked == 1

    def test_only_creatures_with_power_one_or_greater_can_be_sacrificed_for_casualty(self) -> None:
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        disputant = SilverquillTheDisputant(owner=player, controller=player)
        powerless = _creature("Powerless Assistant", 0, 3)
        target = _creature("Only Target", 2, 2)
        spell = TestPingInstant(owner=player, controller=player)

        set_board_state(
            game,
            0,
            battlefield=[disputant, powerless],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        _set_main_phase(game)
        disputant.register_triggers(game)
        player.choose_yes_no = lambda prompt: True
        player.choose_card = lambda cards, description: None
        player.choose_target = lambda options, requirement: target

        engine_cast_spell(game, player, spell)
        _resolve_all(game)

        assert player.zones[Zone.BATTLEFIELD].contains(powerless)
        assert not player.zones[Zone.GRAVEYARD].contains(powerless)
        assert target.damage_marked == 1

    def test_casting_a_sorcery_also_gains_casualty_one(self) -> None:
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        disputant = SilverquillTheDisputant(owner=player, controller=player)
        fodder = _creature("Inkling Token", 1, 1)
        target = _creature("Lecture Bear", 2, 2)
        spell = TestPingSorcery(owner=player, controller=player)

        set_board_state(
            game,
            0,
            battlefield=[disputant, fodder],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        _set_main_phase(game)
        disputant.register_triggers(game)
        player.choose_yes_no = lambda prompt: True
        player.choose_card = lambda cards, description: fodder
        player.choose_target = lambda options, requirement: target

        engine_cast_spell(game, player, spell)
        _resolve_all(game)

        assert player.zones[Zone.GRAVEYARD].contains(fodder)
        assert target.damage_marked == 2

    def test_non_instant_and_non_sorcery_spells_are_not_granted_casualty(self) -> None:
        game = create_game()
        player = game.players[0]
        disputant = SilverquillTheDisputant(owner=player, controller=player)
        fodder = _creature("Inkling Token", 1, 1)
        creature_spell = _creature("Campus Bear", 2, 2, "{1}{G}")

        set_board_state(
            game,
            0,
            battlefield=[disputant, fodder],
            hand=[creature_spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        _set_main_phase(game)
        disputant.register_triggers(game)
        player.choose_yes_no = lambda prompt: True
        player.choose_card = lambda cards, description: fodder

        engine_cast_spell(game, player, creature_spell)
        _resolve_all(game)

        battlefield = player.zones[Zone.BATTLEFIELD]
        assert battlefield.contains(fodder)
        assert battlefield.contains(creature_spell)
        assert len([obj for obj in battlefield.get_all() if getattr(obj, "name", "") == "Campus Bear"]) == 1
