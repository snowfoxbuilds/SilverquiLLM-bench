"""Reference tests for the shared FDN token factories (cards/fdn/tokens.py).

Phase H routes every common-token minter through one factory so a token's
identity — card types, subtypes, colours, base P/T — has a single definition
matching ``data/replays/token_id_map.json``, and so Food and Treasure carry
their REAL abilities as engine primitives (not per-card no-ops):

* Food: "{2}, {T}, Sacrifice this token: You gain 3 life."
* Treasure: "{T}, Sacrifice this token: Add one mana of any color."

These tests pin both the correlation-critical characteristics and that the
abilities actually work end to end.
"""

from __future__ import annotations

from cards.fdn.tokens import (
    make_creature_token,
    make_food_token,
    make_treasure_token,
)
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.protection import get_colors
from engine.types import CardType, Color, Keyword, ManaType, Zone
from test_utils import create_game, set_board_state


class TestFoodToken:
    def test_characteristics_match_the_token_map(self) -> None:
        food = make_food_token()
        assert food.name == "Food"
        assert food.card_types == {CardType.ARTIFACT}
        assert food.subtypes == {"Food"}
        # Explicit colourlessness (positive evidence for correlation).
        assert get_colors(food) == set()
        assert food.is_token is True

    def test_ability_pays_two_taps_sacrifices_and_gains_three_life(self) -> None:
        game = create_game()
        player = game.players[0]
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        food = make_food_token()
        from engine.game import create_token

        create_token(game, player, food)
        life_before = player.life

        ability = food.get_activated_abilities()[0]
        assert ability.cost(game, food) is True
        # Cost: {2} spent, token tapped then sacrificed to the graveyard.
        assert player.mana_pool.total() == 0
        assert food.is_tapped is True
        assert not game.get_battlefield(player).contains(food)
        assert player.zones[Zone.GRAVEYARD].contains(food)

        ability.effect(game)
        assert player.life == life_before + 3

    def test_ability_cannot_be_paid_without_two_mana(self) -> None:
        game = create_game()
        player = game.players[0]
        food = make_food_token()
        from engine.game import create_token

        create_token(game, player, food)
        ability = food.get_activated_abilities()[0]
        assert ability.cost(game, food) is False
        # Nothing spent, token still on the battlefield.
        assert game.get_battlefield(player).contains(food)


class TestTreasureToken:
    def test_characteristics_match_the_token_map(self) -> None:
        treasure = make_treasure_token()
        assert treasure.name == "Treasure"
        assert treasure.card_types == {CardType.ARTIFACT}
        assert treasure.subtypes == {"Treasure"}
        assert get_colors(treasure) == set()
        assert treasure.is_token is True

    def test_mana_ability_sacrifices_and_adds_one_mana_of_chosen_color(self) -> None:
        game = create_game()
        player = game.players[0]
        treasure = make_treasure_token()
        from engine.game import create_token

        create_token(game, player, treasure)
        ability = treasure.get_mana_abilities()[0]

        # Cost: tap + sacrifice.
        assert ability.cost(game, treasure) is True
        assert treasure.is_tapped is True
        assert not game.get_battlefield(player).contains(treasure)
        assert player.zones[Zone.GRAVEYARD].contains(treasure)

        # "Add one mana of any color" — the controller chooses; answer red.
        player.start_intent("treasure", Intent(
            pattern=GameRef(card=frozenset({("name", "Treasure")})),
            preferences=(Decision.color("R"),),
        ))
        try:
            ability.mana_produced(game)
        finally:
            player.end_intent("treasure")
        assert player.mana_pool.get(ManaType.RED) == 1


class TestCreatureTokenFactory:
    def test_sets_explicit_colour_subtypes_and_base_pt(self) -> None:
        soldier = make_creature_token("Soldier", {"Soldier"}, [Color.WHITE], 1, 1)
        assert soldier.card_types == {CardType.CREATURE}
        assert soldier.subtypes == {"Soldier"}
        assert soldier.base_power == 1 and soldier.base_toughness == 1
        assert get_colors(soldier) == {Color.WHITE}
        assert soldier.is_token is True

    def test_white_human_vs_red_human_are_distinguishable_by_colour(self) -> None:
        # The 1/1 white Human token (94158) shares its signature with the 1/1
        # red Human copy token (93797); only the explicit colour tells them
        # apart for correlation.
        white_human = make_creature_token("Human", {"Human"}, [Color.WHITE], 1, 1)
        assert get_colors(white_human) == {Color.WHITE}

    def test_multicolour_and_keyword(self) -> None:
        insect = make_creature_token(
            "Insect", {"Insect"}, [Color.BLACK, Color.GREEN], 1, 1,
            keywords=Keyword.FLYING,
        )
        assert get_colors(insect) == {Color.BLACK, Color.GREEN}
        assert insect.keywords & Keyword.FLYING
