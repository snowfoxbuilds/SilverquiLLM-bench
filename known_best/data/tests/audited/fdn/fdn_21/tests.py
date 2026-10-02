"""Reference test for FDN 21 — Prideful Parent (Phase F self-ETB probe).

Prideful Parent's "When this creature enters, create a 1/1 white Cat creature
token" is its own enters-trigger. Before Phase F the engine fired the ETB event
before the card registered its triggers, so this token was never minted (the
flagship MISSING_CARD / token casualty). The Phase F ordering flip — register
own triggers, then fire ETB (rule 603.3a) — makes it mint exactly one Cat on
its own entry, end-to-end through the real cast/resolve path.
"""
from __future__ import annotations

from cards.fdn.fdn_21.card_impl import PridefulParent
from engine.protection import get_colors
from engine.types import Color, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _cat_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False) and "Cat" in getattr(o, "subtypes", set())
    ]


class TestPridefulParentSelfETB:
    def test_own_entry_mints_exactly_one_cat(self) -> None:
        parent = PridefulParent()
        game = create_game()
        set_board_state(
            game, 0, hand=[parent],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2},
        )
        cast_spell(game, 0, "Prideful Parent")

        bf = game.players[0].zones[Zone.BATTLEFIELD]
        assert bf.contains(parent)
        cats = _cat_tokens(game, 0)
        assert len(cats) == 1
        assert (cats[0].base_power, cats[0].base_toughness) == (1, 1)

    def test_minted_cat_has_spec_characteristics(self) -> None:
        """The minted token is a 1/1 white Cat creature token (via
        ``make_creature_token``). Colour is explicit so ``get_colors`` sees
        white — a token has no mana cost to derive it from."""
        parent = PridefulParent()
        game = create_game()
        set_board_state(
            game, 0, hand=[parent],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2},
        )
        cast_spell(game, 0, "Prideful Parent")
        cats = _cat_tokens(game, 0)
        assert len(cats) == 1
        cat = cats[0]
        assert cat.subtypes == {"Cat"}
        assert (cat.base_power, cat.base_toughness) == (1, 1)
        assert cat.is_token is True
        assert get_colors(cat) == {Color.WHITE}
