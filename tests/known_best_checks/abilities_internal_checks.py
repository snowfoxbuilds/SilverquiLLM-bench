"""Known-Best engine checks moved out of the Audited Engine Tests' test_abilities.py:
they drive the engine directly or test its internals, in positions no
FDN card reaches through play, so they guard the Known-Best engine
without being graded against candidates (ADR-018)."""

from __future__ import annotations

import pytest
from cards.fdn.fdn_134.card_impl import (
    AjaniCallerOfThePride,
)
from cards.fdn.fdn_272.card_impl import Plains
from engine.abilities import (
    AbilityError,
    activate_ability,
    tap_cost,
)
from engine.game_state import GameState
from test_interface import Phase, Side, Zone, card, create_game
from test_utils import DeterministicPlayer

from table import Table, moves, off_stack, on_stack, taps

# ---------------------------------------------------------------------------
# ActivatedAbilityInstance — construction
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# LoyaltyAbilityInstance — construction
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Engine entry points with no counterpart at the table
# ---------------------------------------------------------------------------


def _bare_game() -> GameState:
    return GameState([DeterministicPlayer("Alice"), DeterministicPlayer("Bob")])


class TestTapCostHelper:
    def test_source_without_is_tapped_attribute(self):
        """Source with no is_tapped attribute is treated as untapped."""

        class Bare:
            pass

        source = Bare()
        assert tap_cost(_bare_game(), source) is True
        assert source.is_tapped is True


class TestUnknownAbilityType:
    def test_unknown_type_raises(self):
        game = _bare_game()
        with pytest.raises(AbilityError, match="Unknown ability type"):
            activate_ability(game, game.players[0], "not an ability")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# {T} costs
# ---------------------------------------------------------------------------


def _main(p0: Side, p1: Side | None = None, *, active: int = 0) -> Table:
    return Table(create_game(p0, p1 or Side(), start=(Phase.PRECOMBAT_MAIN, active)))


def _resolve(t: Table, first: int, *results) -> None:
    """Both players pass, ``first`` first, and the top of the stack resolves."""
    t.pass_(first)
    t.pass_(1 - first, then=list(results))




# ---------------------------------------------------------------------------
# Mana abilities
# ---------------------------------------------------------------------------


def _bolt_with_mountain(t: Table, seat: int, mountain, bolt, at) -> None:
    t.act(seat, mountain, then=[taps(mountain)], note="the mana ability resolves at once, off the stack")
    t.act(seat, bolt, choices=[at], then=[moves(bolt, Zone.STACK)], note="its mana pays for Burst Lightning")




# ---------------------------------------------------------------------------
# Other activated abilities use the stack, at instant speed
# ---------------------------------------------------------------------------






# ---------------------------------------------------------------------------
# Loyalty abilities
# ---------------------------------------------------------------------------


def _ajani(*, hand=(), battlefield=(), p0_library=1) -> Table:
    """Player 0's turn 1 with Ajani (loyalty 4); each player has enough
    library for the next few turns."""
    ajani = card(AjaniCallerOfThePride)
    game = create_game(
        Side(hand=list(hand), battlefield=[ajani, *battlefield], library=[card(Plains) for _ in range(p0_library)]),
        Side(library=[card(Plains) for _ in range(p0_library)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game)


def _loyalty(t: Table, ability, *, choices=(), then=(), note="") -> None:
    """Player 0 activates the loyalty ability ``ability``, and it resolves."""
    t.act(0, ability, choices=list(choices), then=[on_stack(ability, 0)], note=note)
    _resolve(t, 0, off_stack(ability), *then)










