"""The FDN gain-life tapland cycle gains life via a real ETB trigger.

"When this land enters, you gain 1 life" is a triggered ability, not an
as-enters effect: it goes on the stack when the land enters and resolves at
its own cadence — which is what makes the replay executor's life match GRE
(GRE reports the clause as an ability that activates then resolves a step or
two later, not an instantaneous land-play side effect). "Enters tapped" stays
an as-enters effect. Seen through Wind-Scarred Crag.
"""

from __future__ import annotations

from cards.fdn.fdn_271.card_impl import WindScarredCrag, WindScarredCragAbility2
from test_interface import Phase, Side, Step, Zone, card, create_game

from table import Table, life, moves, off_stack, on_stack, taps


def _play_crag() -> Table:
    """Player 0 plays Wind-Scarred Crag: it enters tapped, and its trigger
    goes on the stack."""
    crag = card(WindScarredCrag)
    t = Table(create_game(Side(hand=[crag]), Side(), start=(Phase.PRECOMBAT_MAIN, 0)))
    t.act(
        0,
        crag,
        then=[moves(crag, Zone.BATTLEFIELD), taps(crag), on_stack(WindScarredCragAbility2, 0)],
        note="it enters tapped",
    )
    return t


class TestGainlifeTaplandTrigger:
    def test_life_not_gained_at_drive_time(self) -> None:
        final = _play_crag().run()
        assert final.players[0].life == 20  # the gain waits on the stack

    def test_life_gained_when_trigger_resolves(self) -> None:
        t = _play_crag()
        t.pass_(0)
        t.pass_(1, then=[off_stack(WindScarredCragAbility2), life(0, 21)], note="the trigger resolves")
        t.run()

    def test_trigger_gains_life_once_not_per_resolve_call(self) -> None:
        t = _play_crag()
        t.pass_(0)
        t.pass_(1, then=[off_stack(WindScarredCragAbility2), life(0, 21)])
        t.pass_to(Step.END, 0)
        final = t.run()
        assert final.players[0].life == 21
