"""Audited tests for Together as One (sos_4).

Oracle: {6} Sorcery.
  Converge — Target player draws X cards, Together as One deals X damage to
  any target, and you gain X life, where X is the number of colors of mana
  spent to cast this spell.

Simulation-only shape (AUDITED-TEST-API.md): every cast runs through a
``CastSpell`` directive inside ``priority_loop``.  ``len(colors_spent)`` is
pinned by pre-setting the pool to exactly the colored mana the cast needs
(mana-minimality), so the engine has only one legal payment and X is
deterministic; the payment itself is then asserted with
``assert_colors_spent``.

Tests:
  1. test_card_identity
  2. test_one_color_draw_damage_life
  3. test_five_colors_full_effect
  4. test_zero_colors_no_effect
  5. test_insufficient_mana_cast_rejected
"""

from __future__ import annotations

from card_impl import TogetherAsOne

from engine.card import CardImpl, Creature, Sorcery
from engine.types import CardType, Color, ManaType, Phase, Zone
from test_utils import (
    CastSpell,
    DeterministicPlayer,
    advance_to_phase,
    assert_colors_spent,
    assert_damage,
    assert_in_zone,
    assert_life_total,
    assert_mana_pool,
    assert_stack_empty,
    assert_zone_count,
    create_game,
    no_op,
    perform_action,
    perform_illegal_action,
    priority_loop,
    set_board_state,
    set_player,
)


def _make_creature(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _fillers(n: int) -> list[CardImpl]:
    return [CardImpl(name=f"Filler{i}") for i in range(n)]


def _cast_together_as_one(game, mana, targets, *, directive=perform_action) -> None:
    """Drive a single Together as One cast through the priority loop."""
    set_board_state(game, 0, hand=[TogetherAsOne()], mana=mana)
    set_player(game, 0, DeterministicPlayer("P0", script=[
        directive(CastSpell("Together as One", targets=targets)),
        no_op(),
    ]))
    set_player(game, 1, DeterministicPlayer("P1", script=[no_op(), no_op()]))
    priority_loop(game)


class TestIdentity:
    def test_card_identity(self) -> None:
        card = TogetherAsOne()
        assert card.name == "Together as One"
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types
        assert card.mana_cost.generic == 6
        assert card.mana_cost.pips == {}
        assert card.mana_cost.cmc == 6


class TestOneColorResolution:
    def test_one_color_draw_damage_life(self) -> None:
        """{R} + 5 colorless pays {6} with one color → X=1: target player
        draws 1, the targeted creature takes 1, controller gains 1 life."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        bear = _make_creature()
        set_board_state(game, 1, battlefield=[bear], library=_fillers(5))

        _cast_together_as_one(
            game,
            {ManaType.RED: 1, ManaType.COLORLESS: 5},
            [game.players[1], bear],
        )

        assert_colors_spent(game, [Color.RED])
        assert_zone_count(game, 1, Zone.HAND, 1)
        assert_damage(game, bear, 1)
        assert_life_total(game, 0, 21)
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Together as One")
        assert_stack_empty(game)


class TestFiveColorResolution:
    def test_five_colors_full_effect(self) -> None:
        """WUBRG + 1 colorless → X=5: draw 5, deal 5 to the targeted player,
        gain 5 life."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        set_board_state(game, 1, library=_fillers(6))

        _cast_together_as_one(
            game,
            {
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.RED: 1,
                ManaType.GREEN: 1,
                ManaType.COLORLESS: 1,
            },
            [game.players[1], game.players[1]],
        )

        assert_colors_spent(
            game,
            [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN],
        )
        assert_zone_count(game, 1, Zone.HAND, 5)
        assert_life_total(game, 1, 15)
        assert_life_total(game, 0, 25)
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Together as One")


class TestZeroColorDiscriminator:
    def test_zero_colors_no_effect(self) -> None:
        """Six colorless mana → X=0: no draw, no damage, no life gain."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        bear = _make_creature()
        set_board_state(game, 1, battlefield=[bear], library=_fillers(5))

        _cast_together_as_one(
            game,
            {ManaType.COLORLESS: 6},
            [game.players[1], bear],
        )

        assert_colors_spent(game, [])
        assert_zone_count(game, 1, Zone.HAND, 0)
        assert_damage(game, bear, 0)
        assert_life_total(game, 0, 20)
        assert_life_total(game, 1, 20)
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Together as One")


class TestCastLegality:
    def test_insufficient_mana_cast_rejected(self) -> None:
        """{6} cannot be paid from five mana — the cast is illegal and the
        card stays in hand with no effects applied."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        bear = _make_creature()
        set_board_state(game, 1, battlefield=[bear], library=_fillers(5))

        _cast_together_as_one(
            game,
            {ManaType.COLORLESS: 5},
            [game.players[1], bear],
            directive=perform_illegal_action,
        )

        assert_in_zone(game, 0, Zone.HAND, "Together as One")
        assert_zone_count(game, 1, Zone.HAND, 0)
        assert_damage(game, bear, 0)
        assert_life_total(game, 0, 20)
        assert_mana_pool(game, 0, {ManaType.COLORLESS: 5})
