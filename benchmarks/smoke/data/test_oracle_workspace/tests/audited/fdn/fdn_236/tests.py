"""Public battlefield-entry and counter-synergy coverage for Wildwood Scourge.

Positive X entry is excluded because the frozen casting engine lacks that choice."""

from __future__ import annotations

from cards.fdn.fdn_236.card_impl import WildwoodScourge
from engine.card import Creature
from engine.game import add_counter
from engine.types import ManaCost
from test_utils import scenario_game as create_game


class TestWildwoodScourgeProperties:
    def test_name_and_cost(self) -> None:
        card = WildwoodScourge(owner=None)
        assert card.name == "Wildwood Scourge"
        assert card.mana_cost == ManaCost.parse("{X}{G}")

    def test_x_zero_enters_at_zero_zero_no_fabrication(self) -> None:
        from test_utils import cast_card, fund_mana_cost

        game = create_game()
        player = game.players[0]
        card = WildwoodScourge(owner=player)
        fund_mana_cost(player, card.mana_cost)
        cast_card(game, player, card)
        assert game.get_graveyard(player).contains(card)
        assert not game.get_battlefield(player).contains(card)


    def test_enters_with_x_counters(self) -> None:
        """X = 3 is chosen and paid while casting (rules 601.2b, 601.2f), and
        the permanent enters with three +1/+1 counters (400.7d, 614.1c)."""
        from engine.decisions import Decision
        from engine.types import ManaType
        from test_utils import cast_card, fund_mana_cost, prefer

        game = create_game()
        player = game.players[0]
        scourge = WildwoodScourge(owner=player)
        fund_mana_cost(player, scourge.mana_cost)
        player.mana_pool.add(ManaType.COLORLESS, 3)
        prefer(player, Decision.number(3))
        cast_card(game, player, scourge)
        assert game.get_battlefield(player).contains(scourge)
        assert scourge.counters.get("+1/+1", 0) == 3
        assert player.mana_pool.total() == 0


class TestWildwoodScourgeTriggerRegistration:
    """The previously-crashing register_triggers path."""

    def test_condition_matches_other_nonhydra_creature_you_control(self) -> None:
        from test_utils import enter_permanent, put_on_battlefield, resolve_stack

        game = create_game()
        player, opponent = game.players
        scourge = enter_permanent(game, player, WildwoodScourge())
        add_counter(game, scourge, "+1/+1", 1)
        other = put_on_battlefield(
            game, player, Creature(name="Other", subtypes={"Beast"}, base_power=1, base_toughness=1)
        )
        hydra = put_on_battlefield(
            game, player, Creature(name="Hydra", subtypes={"Hydra"}, base_power=1, base_toughness=1)
        )
        enemy = put_on_battlefield(
            game, opponent, Creature(name="Enemy", base_power=1, base_toughness=1)
        )
        add_counter(game, other, "+1/+1", 2)
        resolve_stack(game)
        assert scourge.power == 2
        add_counter(game, hydra, "+1/+1", 1)
        add_counter(game, enemy, "+1/+1", 1)
        resolve_stack(game)
        assert scourge.power == 2
        add_counter(game, scourge, "+1/+1", 1)
        resolve_stack(game)
        assert scourge.power == 3
