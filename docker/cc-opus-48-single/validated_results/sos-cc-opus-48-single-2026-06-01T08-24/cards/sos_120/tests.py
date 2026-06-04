"""Tests for SOS 120 — Improvisation Capstone.

Improvisation Capstone is a ``{5}{R}{R}`` Sorcery — Lesson:

    "Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among them
    without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)"

These tests define the TDD contract; ``card_impl.py`` is a stub, so they are
expected to fail until the card is implemented (TDD red phase).

Coverage notes
--------------
* **Static data** — sorcery type, name, ``{5}{R}{R}`` mana cost, red, the
  ``Lesson`` subtype.
* **Exile-until-MV-4** — ``on_resolve`` exiles cards from the top of the
  controller's library, accumulating their total mana value, and stops as soon
  as the cumulative total reaches 4 or greater. It must not over-exile, must
  stop on the exact card that crosses the threshold, and must handle a single
  high-MV card and a library too small to reach 4.
* **Free-cast among exiled cards** — spells among the exiled cards may be cast
  for free (no mana paid). At least one castable spell is exercised end to end.

The **Paradigm** clause is recorded in ``untestable.json``: "Paradigm" is not a
member of ``engine.types.Keyword`` (the enum is frozen at 16 members and
``engine_tests/`` is authoritative), and the delayed "cast a copy from exile at
the beginning of each of your first main phases" machinery has no engine surface
to assert against. The exile-this-spell sub-clause and the recurring copy-cast
are therefore left to the implementer's discretion and not contract-tested here.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sorcery(name: str, cost: str) -> Sorcery:
    """A vanilla sorcery with the given parsed mana cost."""
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _instant(name: str, cost: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _creature(name: str, cost: str, power: int = 1, toughness: int = 1) -> Creature:
    c = Creature(
        name=name,
        mana_cost=ManaCost.parse(cost),
        base_power=power,
        base_toughness=toughness,
    )
    return c


def _set_library(game: Any, player_index: int, cards: list[Any]) -> None:
    """Place *cards* into a player's library, top-of-library = LAST in the list.

    The engine's :class:`ZoneContainer` treats index ``-1`` as the *top* of the
    zone (``add`` appends, ``top(n)`` returns the last n). So to make ``cards``
    read as a top-to-bottom ordering, we add them in reverse: the first element
    of *cards* ends up on top.
    """
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for obj in library.get_all():
        library.remove(obj)
    for card in reversed(cards):
        card.owner = player
        card.controller = player
        library.add(card)


def _exiled(game: Any, player: Any) -> list[Any]:
    return game.get_exile(player).get_all()


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ImprovisationCapstone(owner=None), Sorcery)

    def test_card_type_includes_sorcery(self) -> None:
        assert CardType.SORCERY in ImprovisationCapstone(owner=None).card_types

    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_is_red(self) -> None:
        cost = ImprovisationCapstone(owner=None).mana_cost
        assert cost.pips.get(ManaType.RED, 0) == 2
        assert cost.generic == 5

    def test_has_lesson_subtype(self) -> None:
        assert "Lesson" in ImprovisationCapstone(owner=None).subtypes


# ---------------------------------------------------------------------------
# Exile-from-library until total mana value >= 4
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneExileUntilFour:
    """on_resolve exiles from the top of the library until the cumulative mana
    value of the exiled cards reaches 4 or greater."""

    def test_exiles_until_total_mv_reaches_four(self) -> None:
        """Three 2-MV cards: exiling the first two (2+2=4) reaches the threshold
        exactly; the third stays in the library."""
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        top = _sorcery("Two A", "{1}{R}")   # MV 2
        mid = _sorcery("Two B", "{1}{R}")   # MV 2
        bottom = _sorcery("Two C", "{1}{R}")  # MV 2
        _set_library(game, 0, [top, mid, bottom])

        capstone.on_resolve(game)

        exiled = _exiled(game, p1)
        assert top in exiled
        assert mid in exiled
        # Threshold reached at 4 — do not exile beyond it.
        assert bottom not in exiled
        assert game.get_library(p1).contains(bottom)

    def test_total_mana_value_of_exiled_is_at_least_four(self) -> None:
        """Whatever the library composition, the exiled pile sums to >= 4 once a
        sufficient total is available."""
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        _set_library(
            game,
            0,
            [
                _sorcery("One", "{R}"),       # MV 1
                _sorcery("One Two", "{1}{R}"),  # MV 2
                _sorcery("One Three", "{2}{R}"),  # MV 3 (cumulative 6 -> stop)
                _sorcery("Extra", "{R}"),     # MV 1
            ],
        )

        capstone.on_resolve(game)

        total = sum(c.mana_cost.cmc for c in _exiled(game, p1))
        assert total >= 4

    def test_stops_on_card_that_crosses_threshold(self) -> None:
        """1 + 1 + 3 = 5 crosses 4 on the third card. Exactly three cards are
        exiled; the fourth remains."""
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        a = _sorcery("One A", "{R}")        # MV 1 (cum 1)
        b = _sorcery("One B", "{R}")        # MV 1 (cum 2)
        c = _sorcery("Three C", "{2}{R}")   # MV 3 (cum 5 -> stop)
        d = _sorcery("One D", "{R}")        # MV 1 (untouched)
        _set_library(game, 0, [a, b, c, d])

        capstone.on_resolve(game)

        exiled = _exiled(game, p1)
        assert a in exiled and b in exiled and c in exiled
        assert d not in exiled
        assert game.get_library(p1).contains(d)

    def test_single_high_mv_card_stops_immediately(self) -> None:
        """A single MV-4 card on top satisfies the threshold by itself; only it
        is exiled."""
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        big = _sorcery("Big", "{3}{R}")     # MV 4
        rest = _sorcery("Rest", "{R}")      # MV 1
        _set_library(game, 0, [big, rest])

        capstone.on_resolve(game)

        exiled = _exiled(game, p1)
        assert big in exiled
        assert rest not in exiled

    def test_exiles_from_top_of_library(self) -> None:
        """Cards are taken from the TOP of the library, not the bottom."""
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        top = _sorcery("Top", "{3}{R}")     # MV 4 (top of library)
        bottom = _sorcery("Bottom", "{R}")  # MV 1 (bottom of library)
        _set_library(game, 0, [top, bottom])

        capstone.on_resolve(game)

        exiled = _exiled(game, p1)
        assert top in exiled
        assert bottom not in exiled

    def test_small_library_exiles_everything_without_raising(self) -> None:
        """If the library can never reach total MV 4, every card is exiled and
        resolution does not raise."""
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        a = _sorcery("Lo A", "{R}")  # MV 1
        b = _sorcery("Lo B", "{R}")  # MV 1
        _set_library(game, 0, [a, b])

        capstone.on_resolve(game)

        exiled = _exiled(game, p1)
        assert a in exiled and b in exiled
        assert len(game.get_library(p1)) == 0

    def test_empty_library_is_a_noop(self) -> None:
        """An empty library exiles nothing and does not raise."""
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        _set_library(game, 0, [])

        capstone.on_resolve(game)

        assert len(_exiled(game, p1)) == 0

    def test_uses_controllers_library_not_opponents(self) -> None:
        """"Your library" is the controller's library; the opponent's library
        is never touched."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        mine = _sorcery("Mine", "{3}{R}")    # MV 4
        theirs = _sorcery("Theirs", "{3}{R}")  # MV 4
        _set_library(game, 0, [mine])
        _set_library(game, 1, [theirs])

        capstone.on_resolve(game)

        assert mine in _exiled(game, p1)
        # Opponent's library and exile are untouched.
        assert game.get_library(p2).contains(theirs)
        assert theirs not in _exiled(game, p2)
        assert theirs not in _exiled(game, p1)


# ---------------------------------------------------------------------------
# Free-cast among the exiled cards
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneFreeCast:
    """"You may cast any number of spells from among them without paying their
    mana costs." The exiled spells may be cast for free."""

    def test_castable_spell_among_exiles_can_be_cast_for_free(self) -> None:
        """An exiled instant/sorcery is cast without the controller spending any
        mana — it leaves exile and ends up resolved (in the graveyard)."""
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        # Controller has no mana at all; a free cast must still go through.
        set_board_state(game, 0, mana={})

        spell = _sorcery("Free Bolt", "{2}{R}")  # MV 3
        topper = _sorcery("Topper", "{R}")       # MV 1 (cum 4 -> stop)
        _set_library(game, 0, [spell, topper])

        # The "may" cast is exercised by scripting a yes/choice for the spell.
        p1._script.appendleft(spell)
        p1._script.appendleft(True)

        capstone.on_resolve(game)
        # Resolve anything the free cast pushed onto the stack.
        from engine.state_based_actions import resolve_state_based_actions

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
            resolve_state_based_actions(game)

        # The spell was exiled off the top of the library, then free-cast: it
        # is no longer in the library, no longer in exile, and (having resolved)
        # is now in the graveyard — all without the controller paying any mana.
        assert not game.get_library(p1).contains(spell)
        assert spell not in _exiled(game, p1)
        assert game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.get(ManaType.RED) == 0

    def test_resolution_does_not_raise_when_no_spells_to_cast(self) -> None:
        """If the only exiled cards are non-spell permanents (no instants or
        sorceries to free-cast), resolution still completes without raising and
        still exiles to threshold."""
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        # Lands are never cast — they are not spells; exile to threshold via
        # creatures that the controller declines / cannot free-cast meaningfully.
        big = _creature("Beast", "{3}{R}", power=4, toughness=4)  # MV 4
        _set_library(game, 0, [big])

        capstone.on_resolve(game)

        assert big in _exiled(game, p1)
