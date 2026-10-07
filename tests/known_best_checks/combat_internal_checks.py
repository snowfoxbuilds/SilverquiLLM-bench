"""Known-Best engine checks moved out of the Audited Engine Tests' test_combat.py:
they drive the engine directly or test its internals, in positions no
FDN card reaches through play, so they guard the Known-Best engine
without being graded against candidates (ADR-018)."""

from __future__ import annotations

import pytest
from engine.card import Creature, GameObject
from engine.combat import (
    end_combat_step,
)
from engine.game_state import GameState
from engine.player import Player
from engine.triggers import TriggerRegistration
from engine.types import Keyword, Zone
from test_interface import Decision, Phase, Side, Step, create_game
from test_utils import DeterministicPlayer

from table import (
    Table,
    first_strike_damage,
    moves,
    taps,
)

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_game_object_id() -> None:
    """Reset the GameObject auto-increment counter before each test."""
    GameObject.reset_id_counter()


def _make_creature(
    name: str = "Bear",
    power: int = 2,
    toughness: int = 2,
    keywords: Keyword | None = None,
    summoning_sick: bool = False,
    is_tapped: bool = False,
    owner: Player | None = None,
    controller: Player | None = None,
) -> Creature:
    """Create a creature for combat testing with sane defaults."""
    c = Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
        keywords=keywords,
        owner=owner,
        controller=controller,
    )
    c.summoning_sick = summoning_sick
    c.is_tapped = is_tapped
    return c


def _make_game(
    p1_life: int = 20,
    p2_life: int = 20,
) -> GameState:
    """Create a 2-player GameState with given life totals."""
    return GameState([DeterministicPlayer("Alice", life=p1_life), DeterministicPlayer("Bob", life=p2_life)])


def _place_on_battlefield(
    player: Player,
    creature: Creature,
    game: GameState | None = None,
) -> None:
    """Put a creature on a player's battlefield and set its controller; with
    *game*, also give it its battlefield ``instance_id``."""
    creature.controller = player
    creature.owner = player
    player.zones[Zone.BATTLEFIELD].add(creature)
    if game is not None:
        creature.instance_id = game.refs.instance_id(creature, Zone.BATTLEFIELD.value)


def _attacks(p0: Side, p1: Side | None = None) -> Table:
    """Player 0's turn, from its beginning of combat to the declaration of
    attackers."""
    t = Table(create_game(p0, p1 or Side(), start=(Step.BEGIN_COMBAT, 0)))
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    return t


def _main(p0: Side, p1: Side | None = None) -> Table:
    """Player 0's first main phase."""
    return Table(create_game(p0, p1 or Side(), start=(Phase.PRECOMBAT_MAIN, 0)))


def _cast(t: Table, land, spell, *, choices=(), then=()) -> None:
    """Player 0 taps ``land`` and casts ``spell``, and both players pass."""
    t.act(0, land, then=[taps(land)])
    t.act(0, spell, choices=list(choices), then=[moves(spell, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=list(then))


def _attack(t: Table, *attackers, tapping=None, then=()) -> None:
    """Player 0 declares ``attackers``, which tap — all of them unless
    ``tapping`` names the ones that do — and both players pass."""
    tapped = attackers if tapping is None else tapping
    t.act(0, *attackers, then=[*(taps(a) for a in tapped), *then])


def _to_blockers(t: Table) -> None:
    """Both players pass in the declare attackers step."""
    t.pass_(0)
    t.pass_(1)


def _no_blocks(t: Table, *, then=(), first_strike=None) -> None:
    """Player 1 declares no blockers and both players pass to combat damage,
    whose results are ``then``; with ``first_strike``, a first-strike combat
    damage step with those results comes first (rule 510.4)."""
    t.pass_(1, then=[first_strike_damage()] if first_strike is not None else [])
    t.pass_(0)
    if first_strike is not None:
        t.pass_(1, then=list(first_strike))
        t.pass_(0)
    t.pass_(1, then=list(then))


def _blocks(t: Table, blocks: dict, *, shares=None, then=(), first_strike=None) -> None:
    """Player 1 blocks as ``blocks`` says (blocker to attacker), and both
    players pass to combat damage, whose results are ``then``; ``shares``
    divides an attacker's damage, blocker to amount; with ``first_strike``,
    a first-strike combat damage step with those results comes first (rule
    510.4)."""
    t.act(1, *blocks, scoped=blocks, then=[first_strike_damage()] if first_strike is not None else [])
    per_query = {b: [Decision.number(n)] for b, n in (shares or {}).items()}
    t.pass_(0, per_query=per_query or None)
    if first_strike is not None:
        t.pass_(1, then=list(first_strike))
        t.pass_(0)
    t.pass_(1, then=list(then))


def _no_attack(t: Table) -> None:
    """Player 0 declares no attackers, so the declare blockers and combat
    damage steps are skipped (rule 508.8); play stops at end of combat."""
    t.pass_(0)
    t.pass_(0)
    t.pass_(1)


# ---------------------------------------------------------------------------
# CombatState — construction and clear
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Helper: _can_attack
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Helper: _can_block
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Helper: _get_lethal_damage
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Declare Attackers Step
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Declare Blockers Step
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Combat Damage Step
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# End Combat Step
# ---------------------------------------------------------------------------

class TestEndCombat:
    """Verify end_combat_step clears all combat state."""

    def test_clears_combat_flags(self) -> None:
        """end_combat_step should clear is_attacking and is_blocking flags."""
        attacker = _make_creature(name="Attacker")
        blocker = _make_creature(name="Blocker")

        game = _make_game()
        combat = game.combat_state
        combat.in_combat = True
        combat.attackers[attacker] = game.non_active_player
        combat.blockers[blocker] = [attacker]
        combat.attacker_blockers[attacker] = [blocker]
        attacker.is_attacking = True
        blocker.is_blocking = True

        end_combat_step(game)

        assert attacker.is_attacking is False
        assert blocker.is_blocking is False
        assert combat.in_combat is False
        assert combat.attackers == {}
        assert combat.blockers == {}



# ---------------------------------------------------------------------------
# Integration Scenarios
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Dormant-event firing (Phase I, issue #44): combat damage and attacks
# ---------------------------------------------------------------------------

def _record_events(game: GameState, event_type: type) -> list:
    """Register a spy trigger recording every fired *event_type*.

    The spy's condition appends the event and returns ``False`` so the event's
    facts are observed at the firing site without the trigger going on the
    stack — keeping these tests focused on *whether/what* fires, not resolution.
    Returns the list the spy appends to.
    """
    events: list = []

    def _cond(_g: GameState, event: object) -> bool:
        events.append(event)
        return False

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=event_type,
            condition=_cond,
            effect=lambda _g: None,
            source=object(),
            controller=game.active_player,
        )
    )
    return events




