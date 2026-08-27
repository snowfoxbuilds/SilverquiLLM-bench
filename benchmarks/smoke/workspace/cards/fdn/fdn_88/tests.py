"""Reference test for FDN 88 — Goblin Negotiation (Phase H token minter).

"Goblin Negotiation deals X damage to target creature. Create a number of 1/1
red Goblin creature tokens equal to the amount of excess damage dealt to that
creature this way." The mint fires from the sorcery's ``on_resolve`` after the
excess is computed. Casting an {X} spell cannot set X/target through the test
harness, so this drives ``on_resolve`` directly with X and the chosen target
set on the spell — the same code path the executor runs — and proves the
excess-damage Goblins carry the exact 1/1 red Goblin characteristics.
"""
from __future__ import annotations

from cards.fdn.fdn_88.card_impl import GoblinNegotiation
from engine.card import Creature
from engine.protection import get_colors
from engine.types import Color, Zone
from test_utils import create_game, set_board_state


def _goblin_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and "Goblin" in getattr(o, "subtypes", set())
    ]


class TestGoblinNegotiationMint:
    def test_excess_damage_mints_11_red_goblin_tokens(self) -> None:
        spell = GoblinNegotiation()
        target = Creature(
            name="Grizzly Bears", subtypes={"Bear"}, base_power=2, base_toughness=2
        )
        game = create_game()
        set_board_state(game, 1, battlefield=[target])

        controller = game.players[0]
        spell.controller = controller
        # X = 5 dealt to a 2/2: 2 lethal, 3 excess -> three Goblin tokens.
        spell.x_value = 5
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        goblins = _goblin_tokens(game, 0)
        assert len(goblins) == 3
        for token in goblins:
            assert token.subtypes == {"Goblin"}
            assert get_colors(token) == {Color.RED}
            assert token.base_power == 1
            assert token.base_toughness == 1
            assert token.is_token is True
