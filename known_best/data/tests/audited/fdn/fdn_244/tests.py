"""Printed characteristics and public protection behavior for Progenitus.

The faulty graveyard replacement is recorded by an unscored baseline diagnostic."""

from __future__ import annotations

from cards.fdn.fdn_244.card_impl import Progenitus
from engine.card import Creature
from engine.types import ManaCost, Supertype
from test_utils import scenario_game as create_game


class TestProgenitusProperties:
    """Static card data should match the FDN 244 spec."""

    def test_name(self) -> None:
        assert Progenitus(owner=None).name == "Progenitus"

    def test_mana_cost(self) -> None:
        cost = ManaCost.parse("{W}{W}{U}{U}{B}{B}{R}{R}{G}{G}")
        assert Progenitus(owner=None).mana_cost == cost

    def test_legendary_hydra_avatar(self) -> None:
        card = Progenitus(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Hydra", "Avatar"} <= card.subtypes


def test_protection_from_everything_prevents_damage():
    from engine.game import deal_damage
    from test_utils import enter_permanent, resolve_stack

    game = create_game()
    player, opponent = game.players
    card = enter_permanent(game, player, Progenitus())
    source = Creature(name="Source", base_power=20, base_toughness=20, owner=opponent)
    deal_damage(game, source, card, 20)
    resolve_stack(game)
    assert card.damage_marked == 0 and game.get_battlefield(player).contains(card)
