"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from engine.card import Creature, Instant
from engine.types import Keyword, ManaType, Zone
from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from test_utils import cast_spell, create_game, set_board_state


class _Shock(Instant):
    """Test instant: deal 2 damage to player 2 on resolve."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Shock")
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        deal_damage(game, self, game.players[1], 2)


def _setup(script: list[Any], extra_battlefield: list[Any] | None = None):
    game = create_game(scripts=(script, []))
    sq = SilverquillTheDisputant()
    shock = _Shock()
    set_board_state(
        game, 0,
        battlefield=[sq] + (extra_battlefield or []),
        hand=[shock],
    )
    sq.register_triggers(game)
    return game, sq, shock


class TestCasualty:
    def test_sacrifice_copies_the_spell(self) -> None:
        """Sacrificing a power-1 creature copies the spell: 4 total damage."""
        pawn = Creature(name="Pawn", base_power=1, base_toughness=1)
        game, sq, shock = _setup([pawn], extra_battlefield=[pawn])
        cast_spell(game, 0, "Shock")
        p1, p2 = game.players
        assert p2.life == 20 - 4
        assert p1.zones[Zone.GRAVEYARD].contains(pawn)
        assert p1.zones[Zone.GRAVEYARD].contains(shock)
        # only one physical card in the graveyard for the spell + the pawn
        assert len(p1.zones[Zone.GRAVEYARD]) == 2

    def test_decline_no_copy(self) -> None:
        """Declining the sacrifice resolves the spell once."""
        pawn = Creature(name="Pawn", base_power=1, base_toughness=1)
        game, sq, shock = _setup([None], extra_battlefield=[pawn])
        cast_spell(game, 0, "Shock")
        p1, p2 = game.players
        assert p2.life == 18
        assert p1.zones[Zone.BATTLEFIELD].contains(pawn)

    def test_no_eligible_creature_no_prompt(self) -> None:
        """With no creature of power >= 1 there is no prompt and no copy.

        Silverquill itself is normally a legal casualty pick, so simulate a
        -4/-0 effect on it to zero out every power on the board.
        """
        wall = Creature(name="Wall", base_power=0, base_toughness=4)
        game, sq, shock = _setup([], extra_battlefield=[wall])
        sq.modified_power = 0
        cast_spell(game, 0, "Shock")  # script empty — would raise if prompted
        p1, p2 = game.players
        assert p2.life == 18
        assert p1.zones[Zone.BATTLEFIELD].contains(wall)
        assert p1.zones[Zone.BATTLEFIELD].contains(sq)

    def test_creature_spells_do_not_trigger(self) -> None:
        """Casualty applies only to instants and sorceries."""
        game = create_game()
        sq = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq], hand=[bear], mana={})
        sq.register_triggers(game)
        cast_spell(game, 0, "Bear")  # no prompt expected → no script needed
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(bear)

    def test_opponent_spells_do_not_trigger(self) -> None:
        """Only the controller's spells gain casualty."""
        game = create_game()
        sq = SilverquillTheDisputant()
        pawn = Creature(name="Pawn", base_power=1, base_toughness=1)
        shock = _Shock()
        set_board_state(game, 0, battlefield=[sq, pawn])
        set_board_state(game, 1, hand=[shock])
        sq.register_triggers(game)
        cast_spell(game, 1, "Shock")  # p2 casts; p1 must not be prompted
        assert game.players[1].life == 18
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(pawn)

    def test_keywords(self) -> None:
        card = SilverquillTheDisputant()
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
