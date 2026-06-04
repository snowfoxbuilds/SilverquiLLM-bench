"""Audited tests for Lorehold, the Historian (sos_201).

Oracle: {3}{R}{W} 5/5 Legendary Creature — Elder Dragon.
  Flying, haste
  Each instant and sorcery card in your hand has miracle {2}.
  At the beginning of each opponent's upkeep, you may discard a card.
  If you do, draw a card.

Simulation-only shape (AUDITED-TEST-API.md): every behaviour is reached
within player 0's turn by giving Lorehold to **player 1** — player 0's upkeep
is "each opponent's upkeep" for Lorehold's controller, and player 1's first
draw of the turn is produced in-game by a fixture draw instant cast at
instant speed.  The miracle "cast it for its miracle cost?" yes/no is
answered from the choice script; that the alternative cost was actually used
is observed through mana-minimality (the drawn spell's printed cost is
unpayable from the pool, while miracle {2} is exactly payable).

Tests:
  1. test_card_identity
  2. test_miracle_cast_on_first_draw
  3. test_miracle_offer_may_be_declined
  4. test_no_miracle_on_second_draw
  5. test_no_miracle_without_lorehold
  6. test_miracle_grant_scoped_to_controllers_hand
  7. test_opponent_upkeep_discard_to_draw_accepted
  8. test_opponent_upkeep_discard_declined
  9. test_no_trigger_on_controllers_own_upkeep
"""

from __future__ import annotations

from card_impl import LoreholdTheHistorian

from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Supertype, Zone
from test_utils import (
    CastSpell,
    DeterministicPlayer,
    advance_to_phase,
    assert_in_zone,
    assert_library_order,
    assert_mana_pool,
    assert_stack_empty,
    assert_zone_count,
    create_game,
    no_op,
    perform_action,
    priority_loop,
    set_board_state,
    set_player,
)

_NAME = "Lorehold, the Historian"


class QuickStudy(Instant):
    """Fixture card — {1} instant: its controller draws a card.

    Hook bodies are card-implementation code (the same kind of code as a
    ``card_impl.py``), exempt from the API conformance scan.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Quick Study")
        kwargs.setdefault("mana_cost", ManaCost(generic=1))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import draw_card

        draw_card(game, self.controller)


def _make_expensive_instant() -> Instant:
    """An instant whose printed cost {4}{R} is deliberately unpayable in the
    miracle tests — only the miracle {2} alternative cost can cast it."""
    return Instant(
        name="Stroke of Genius",
        mana_cost=ManaCost(generic=4, pips={ManaType.RED: 1}),
    )


class TestIdentity:
    def test_card_identity(self) -> None:
        card = LoreholdTheHistorian()
        assert card.name == _NAME
        assert card.mana_cost.generic == 3
        assert card.mana_cost.pips.get(ManaType.RED) == 1
        assert card.mana_cost.pips.get(ManaType.WHITE) == 1
        assert card.mana_cost.cmc == 5
        assert CardType.CREATURE in card.card_types
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestMiracle:
    def _draw_first_card_via_fixture(self, game, *, p1_choices) -> None:
        """Player 1 casts Quick Study at instant speed, drawing their first
        card of the turn."""
        set_player(game, 0, DeterministicPlayer("P0", script=[
            no_op(), no_op(), no_op(), no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[
            perform_action(CastSpell("Quick Study")),
            no_op(), no_op(), no_op(),
        ], choices=p1_choices))
        priority_loop(game)

    def test_miracle_cast_on_first_draw(self) -> None:
        """The first instant drawn this turn may be cast for miracle {2} —
        with only {C}3 in the pool ({1} Quick Study + {2} miracle), the
        printed {4}{R} cost is unpayable, so the spell resolving proves the
        granted miracle cost was used."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        stroke = _make_expensive_instant()
        set_board_state(
            game, 1,
            battlefield=[LoreholdTheHistorian()],
            hand=[QuickStudy()],
            library=[stroke],
            mana={ManaType.COLORLESS: 3},
        )

        self._draw_first_card_via_fixture(game, p1_choices=[True])

        assert_in_zone(game, 1, Zone.GRAVEYARD, "Stroke of Genius")
        assert_in_zone(game, 1, Zone.GRAVEYARD, "Quick Study")
        assert_zone_count(game, 1, Zone.HAND, 0)
        assert_mana_pool(game, 1, {})
        assert_stack_empty(game)

    def test_miracle_offer_may_be_declined(self) -> None:
        """Declining the miracle offer keeps the drawn card in hand and
        spends no mana on it."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        stroke = _make_expensive_instant()
        set_board_state(
            game, 1,
            battlefield=[LoreholdTheHistorian()],
            hand=[QuickStudy()],
            library=[stroke],
            mana={ManaType.COLORLESS: 3},
        )

        self._draw_first_card_via_fixture(game, p1_choices=[False])

        assert_in_zone(game, 1, Zone.HAND, "Stroke of Genius")
        assert_mana_pool(game, 1, {ManaType.COLORLESS: 2})

    def test_no_miracle_on_second_draw(self) -> None:
        """Only the first card drawn in a turn triggers miracle: drawing an
        instant as the second card offers nothing (a dry choice script would
        fail the test if it did)."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        stroke = _make_expensive_instant()
        set_board_state(
            game, 1,
            battlefield=[LoreholdTheHistorian()],
            hand=[QuickStudy(), QuickStudy()],
            library=[bear, stroke],
            mana={ManaType.COLORLESS: 4},
        )

        set_player(game, 0, DeterministicPlayer("P0", script=[
            no_op(), no_op(), no_op(), no_op(), no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[
            perform_action(CastSpell("Quick Study")),
            no_op(),
            perform_action(CastSpell("Quick Study")),
            no_op(), no_op(),
        ]))
        priority_loop(game)

        # Draw 1: a creature (no miracle); draw 2: an instant, but it is the
        # second draw — no trigger, the card stays in hand.
        assert_in_zone(game, 1, Zone.HAND, "Bear")
        assert_in_zone(game, 1, Zone.HAND, "Stroke of Genius")
        assert_in_zone(game, 1, Zone.GRAVEYARD, "Quick Study", count=2)

    def test_no_miracle_without_lorehold(self) -> None:
        """No granter on the battlefield → a first-draw instant offers no
        miracle and stays in hand."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        stroke = _make_expensive_instant()
        set_board_state(
            game, 1,
            hand=[QuickStudy()],
            library=[stroke],
            mana={ManaType.COLORLESS: 3},
        )

        self._draw_first_card_via_fixture(game, p1_choices=[])

        assert_in_zone(game, 1, Zone.HAND, "Stroke of Genius")

    def test_miracle_grant_scoped_to_controllers_hand(self) -> None:
        """Lorehold grants miracle to *its controller's* hand only — the
        opponent's first-drawn instant gets no offer."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        # Player 0 controls Lorehold; player 1 draws the instant.
        set_board_state(game, 0, battlefield=[LoreholdTheHistorian()])
        stroke = _make_expensive_instant()
        set_board_state(
            game, 1,
            hand=[QuickStudy()],
            library=[stroke],
            mana={ManaType.COLORLESS: 3},
        )

        self._draw_first_card_via_fixture(game, p1_choices=[])

        assert_in_zone(game, 1, Zone.HAND, "Stroke of Genius")


class TestOpponentUpkeepTrigger:
    """'At the beginning of each opponent's upkeep' — player 0's upkeep is an
    opponent's upkeep for Lorehold's controller (player 1)."""

    def test_opponent_upkeep_discard_to_draw_accepted(self) -> None:
        game = create_game()
        shock = Instant(name="Shock", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        new_card = Creature(name="NewCard", base_power=1, base_toughness=1)
        set_board_state(
            game, 1,
            battlefield=[LoreholdTheHistorian()],
            hand=[shock],
            library=[new_card],
        )
        set_player(game, 0, DeterministicPlayer("P0"))
        set_player(game, 1, DeterministicPlayer("P1", choices=[True, shock]))

        advance_to_phase(game, Phase.BEGINNING, Step.UPKEEP)

        assert_in_zone(game, 1, Zone.GRAVEYARD, "Shock")
        assert_in_zone(game, 1, Zone.HAND, "NewCard")
        assert_zone_count(game, 1, Zone.LIBRARY, 0)

    def test_opponent_upkeep_discard_declined(self) -> None:
        game = create_game()
        shock = Instant(name="Shock", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        new_card = Creature(name="NewCard", base_power=1, base_toughness=1)
        set_board_state(
            game, 1,
            battlefield=[LoreholdTheHistorian()],
            hand=[shock],
            library=[new_card],
        )
        set_player(game, 0, DeterministicPlayer("P0"))
        set_player(game, 1, DeterministicPlayer("P1", choices=[False]))

        advance_to_phase(game, Phase.BEGINNING, Step.UPKEEP)

        assert_in_zone(game, 1, Zone.HAND, "Shock")
        assert_zone_count(game, 1, Zone.GRAVEYARD, 0)
        assert_library_order(game, 1, ["NewCard"])

    def test_no_trigger_on_controllers_own_upkeep(self) -> None:
        """Player 0 controls Lorehold: player 0's own upkeep must not fire
        the trigger (a dry choice script would fail the test if it did)."""
        game = create_game()
        shock = Instant(name="Shock", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        set_board_state(
            game, 0,
            battlefield=[LoreholdTheHistorian()],
            hand=[shock],
        )
        set_player(game, 0, DeterministicPlayer("P0"))
        set_player(game, 1, DeterministicPlayer("P1"))

        advance_to_phase(game, Phase.BEGINNING, Step.UPKEEP)

        assert_in_zone(game, 0, Zone.HAND, "Shock")
        assert_zone_count(game, 0, Zone.GRAVEYARD, 0)
