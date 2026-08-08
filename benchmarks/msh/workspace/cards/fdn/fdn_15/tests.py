"""Reference test for FDN 15 — Hare Apparent.

Illustrative test covering a **self-referential ETB token multiplier**: on
entry, the creature counts the *other* creatures you control that share its
name and mints that many 1/1 white Rabbit tokens. ``on_resolve`` is the
engine's enters-the-battlefield hook for a creature spell, so these tests
drive it directly (the isolated postcondition style) and also once through
the full cast pipeline (the real resolution path).

Note: engine-minted tokens carry no grpId identity, so the replay layer's
Rabbit-token zone divergences persist until the token-correlation phase —
what this card fixes is the ETB firing and the MISSING_CARD entries clearing.
"""

from __future__ import annotations

from cards.fdn.fdn_15.card_impl import HareApparent
from engine.card import Creature
from engine.types import ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _rabbit_tokens(game, player) -> list:
    """The 1/1 white Rabbit tokens on *player*'s battlefield."""
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if getattr(obj, "name", None) == "Rabbit"
        and "Rabbit" in getattr(obj, "subtypes", set())
    ]


class TestHareApparentProperties:
    """Static card data should match the FDN 15 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(HareApparent(owner=None), Creature)

    def test_name(self) -> None:
        assert HareApparent(owner=None).name == "Hare Apparent"

    def test_mana_cost(self) -> None:
        assert HareApparent(owner=None).mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = HareApparent(owner=None)
        assert (card.base_power, card.base_toughness) == (2, 2)

    def test_subtypes(self) -> None:
        assert HareApparent(owner=None).subtypes == {"Rabbit", "Noble"}


class TestHareApparentEtb:
    """ETB: one Rabbit per *other* Hare Apparent you control."""

    def test_lone_hare_makes_no_tokens(self) -> None:
        """The "other" clause: a Hare Apparent that is the only one you
        control mints zero tokens (it never counts itself)."""
        game = create_game()
        p1 = game.players[0]
        hare = HareApparent(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hare])

        hare.on_resolve(game)

        assert _rabbit_tokens(game, p1) == []

    def test_two_other_hares_make_two_rabbits(self) -> None:
        game = create_game()
        p1 = game.players[0]
        entering = HareApparent(owner=p1, controller=p1)
        other1 = HareApparent(owner=p1, controller=p1)
        other2 = HareApparent(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[entering, other1, other2])

        entering.on_resolve(game)

        assert len(_rabbit_tokens(game, p1)) == 2

    def test_only_your_own_hares_count(self) -> None:
        """Hare Apparents an opponent controls do not feed the count."""
        game = create_game()
        p1, p2 = game.players
        entering = HareApparent(owner=p1, controller=p1)
        mine = HareApparent(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[entering, mine])
        set_board_state(
            game, 1,
            battlefield=[
                HareApparent(owner=p2, controller=p2),
                HareApparent(owner=p2, controller=p2),
            ],
        )

        entering.on_resolve(game)

        # One *other* Hare of mine -> exactly one Rabbit; the opponent's two
        # do not contribute.
        assert len(_rabbit_tokens(game, p1)) == 1

    def test_tokens_are_one_one_rabbits(self) -> None:
        game = create_game()
        p1 = game.players[0]
        entering = HareApparent(owner=p1, controller=p1)
        other = HareApparent(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[entering, other])

        entering.on_resolve(game)

        tokens = _rabbit_tokens(game, p1)
        assert len(tokens) == 1
        tok = tokens[0]
        assert (tok.base_power, tok.base_toughness) == (1, 1)
        assert tok.is_token is True

    def test_etb_fires_through_the_cast_pipeline(self) -> None:
        """End-to-end: casting Hare Apparent with two others already in play
        resolves the ETB and leaves two fresh Rabbit tokens — proving
        ``on_resolve`` is driven at spell resolution, not only by hand."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(
            game, 0,
            battlefield=[
                HareApparent(owner=p1, controller=p1),
                HareApparent(owner=p1, controller=p1),
            ],
            hand=[HareApparent(owner=p1, controller=p1)],
            mana={ManaType.WHITE: 1, ManaType.RED: 1},
        )

        cast_spell(game, 0, "Hare Apparent")

        # Three Hares (two originals + the cast one) plus two new Rabbits.
        bf = game.get_battlefield(p1).get_all()
        hares = [c for c in bf if getattr(c, "name", None) == "Hare Apparent"]
        assert len(hares) == 3
        assert len(_rabbit_tokens(game, p1)) == 2
        assert game.players[0].zones[Zone.HAND].get_all() == []
