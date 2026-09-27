"""Reference test for FDN 2 — Arahbo, the First Fang (Phase F self-ETB).

Arahbo reads "Whenever Arahbo or another nontoken Cat you control enters, create
a 1/1 white Cat creature token." Its trigger condition deliberately returns True
for its own entry. Before Phase F the engine fired the ETB event before the card
registered, so the self-entry was handled by a bespoke ``on_resolve`` mint. The
Phase F ordering flip makes the trigger fire on Arahbo's own entry, so that
``on_resolve`` workaround was removed — this test proves Arahbo mints **exactly
one** Cat on its own entry (not zero, not two) and still fires for *another*
nontoken Cat but not for a Cat *token*.
"""
from __future__ import annotations

from cards.fdn.fdn_2.card_impl import ArahboTheFirstFang
from engine.card import Creature
from engine.protection import get_colors
from engine.types import Color, ManaType, Zone
from test_utils import cast_spell, create_game, resolve_stack, set_board_state


def _cat_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False) and "Cat" in getattr(o, "subtypes", set())
    ]


def _enter(game, player, card) -> None:
    from engine.zones import move_to_zone

    card.owner = player
    card.controller = player
    player.zones[Zone.HAND].add(card)
    move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
    resolve_stack(game)


class TestArahboSelfETB:
    def test_own_entry_mints_exactly_one_cat(self) -> None:
        arahbo = ArahboTheFirstFang()
        game = create_game()
        set_board_state(
            game, 0, hand=[arahbo],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2},
        )
        cast_spell(game, 0, "Arahbo, the First Fang")
        bf = game.players[0].zones[Zone.BATTLEFIELD]
        assert bf.contains(arahbo)
        assert len(_cat_tokens(game, 0)) == 1

    def test_minted_cat_has_spec_characteristics(self) -> None:
        """The minted token is a 1/1 white Cat creature token (via
        ``make_creature_token``). Colour must be explicit for ``get_colors``
        — a token has no mana cost to derive it from. ``base_power`` stays 1
        even though Arahbo's lord effect buffs the token's *modified* P/T."""
        arahbo = ArahboTheFirstFang()
        game = create_game()
        set_board_state(
            game, 0, hand=[arahbo],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2},
        )
        cast_spell(game, 0, "Arahbo, the First Fang")
        cats = _cat_tokens(game, 0)
        assert len(cats) == 1
        cat = cats[0]
        assert cat.subtypes == {"Cat"}
        assert (cat.base_power, cat.base_toughness) == (1, 1)
        assert cat.is_token is True
        assert get_colors(cat) == {Color.WHITE}

    def test_another_nontoken_cat_mints_but_a_cat_token_does_not(self) -> None:
        arahbo = ArahboTheFirstFang()
        game = create_game()
        p = game.players[0]
        set_board_state(game, 0, battlefield=[arahbo])
        arahbo.owner = p
        arahbo.controller = p
        arahbo.register_triggers(game)
        assert len(_cat_tokens(game, 0)) == 0

        # A nontoken Cat entering under our control fires the trigger.
        other_cat = Creature(name="Jungle Cat", subtypes={"Cat"}, base_power=2, base_toughness=2)
        _enter(game, p, other_cat)
        assert len(_cat_tokens(game, 0)) == 1

        # A Cat *token* entering must NOT fire (nontoken filter). The trigger
        # effect itself mints a Cat token — that token's own entry must not
        # re-trigger and loop.
        tokens_before = len(_cat_tokens(game, 0))
        token_cat = Creature(name="Cat", subtypes={"Cat"}, base_power=1, base_toughness=1)
        token_cat.is_token = True
        token_cat.owner = p
        token_cat.controller = p
        from engine.game import create_token
        create_token(game, p, token_cat)
        resolve_stack(game)
        # Only the token we placed appears; no extra Cat minted by re-trigger.
        assert len(_cat_tokens(game, 0)) == tokens_before + 1
