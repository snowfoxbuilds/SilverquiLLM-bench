"""Audited tests for FDN 53 — Uncharted Voyage."""

from __future__ import annotations

from card_impl import UnchartedVoyage
from engine.card import Creature, Instant
from engine.types import ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestUnchartedVoyageBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = UnchartedVoyage(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = UnchartedVoyage(owner=None)
        assert card.name == "Uncharted Voyage"

    def test_mana_cost(self) -> None:
        card = UnchartedVoyage(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}")


class TestUnchartedVoyageResolve:
    """Put target creature on top/bottom of library, then surveil 1."""

    def test_puts_creature_on_top_of_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = UnchartedVoyage(owner=p1, controller=p1)
        target = Creature(name="Enemy", base_power=3, base_toughness=3, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        # Owner chooses top (True), surveil keep on top (False = don't put in gy)
        p2._script.append(True)   # put on top
        p1._script.append(False)  # surveil: keep on top
        # Add a library card for surveil
        lib_card = Creature(name="LibTop", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        card.on_resolve(game)
        # Target should be on top of owner's library
        lib_cards = list(p2.zones[Zone.LIBRARY].get_all())
        assert lib_cards[-1] is target

    def test_puts_creature_on_bottom_of_library(self) -> None:
        """When owner chooses bottom, creature goes to the bottom of the library."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = UnchartedVoyage(owner=p1, controller=p1)
        target = Creature(name="Enemy", base_power=3, base_toughness=3, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        # Add existing library card so we can verify target ends up at bottom
        existing = Creature(name="Existing", base_power=1, base_toughness=1, owner=p2)
        p2.zones[Zone.LIBRARY].add(existing)
        # Owner chooses bottom (False), surveil keep (False)
        p2._script.append(False)  # put on bottom
        p1._script.append(False)  # surveil: keep on top
        lib_card = Creature(name="LibTop", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        card.on_resolve(game)
        # Target should be at the bottom of owner's library (_objects[0])
        lib = p2.zones[Zone.LIBRARY]
        assert lib._objects[0] is target

    def test_removes_creature_from_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = UnchartedVoyage(owner=p1, controller=p1)
        target = Creature(name="Enemy", base_power=3, base_toughness=3, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        p2._script.append(True)
        p1._script.append(False)
        lib_card = Creature(name="LibTop", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        card.on_resolve(game)
        bf = game.get_battlefield(p2)
        assert not bf.contains(target)

    def test_surveil_puts_card_in_graveyard(self) -> None:
        """When target is valid, surveil after bouncing puts card in graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = UnchartedVoyage(owner=p1, controller=p1)
        target = Creature(name="Enemy", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        p2._script.append(True)   # put on top
        top_card = Creature(name="TopCard", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(top_card)
        # Surveil: put in graveyard (True)
        p1._script.append(True)
        card.on_resolve(game)
        gy = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert top_card in gy

    def test_surveil_keeps_card_on_top(self) -> None:
        """When target is valid, surveil can keep card on top of library."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = UnchartedVoyage(owner=p1, controller=p1)
        target = Creature(name="Enemy", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        p2._script.append(True)   # put on top
        top_card = Creature(name="TopCard", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(top_card)
        # Surveil: keep on top (False)
        p1._script.append(False)
        card.on_resolve(game)
        lib_cards = list(p1.zones[Zone.LIBRARY].get_all())
        assert top_card in lib_cards

    def test_fizzles_when_target_is_none(self) -> None:
        """Single-target spell fizzles entirely when target is None (illegal)."""
        game = create_game()
        p1 = game.players[0]
        card = UnchartedVoyage(owner=p1, controller=p1)
        card.chosen_targets = [None]
        top_card = Creature(name="TopCard", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(top_card)
        card.on_resolve(game)
        # Spell fizzled — no surveil should happen
        gy = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert len(gy) == 0
        # Library should be untouched
        lib_cards = list(p1.zones[Zone.LIBRARY].get_all())
        assert top_card in lib_cards

    def test_fizzles_when_target_left_battlefield(self) -> None:
        """If the target creature left the battlefield, spell fizzles — no surveil."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = UnchartedVoyage(owner=p1, controller=p1)
        target = Creature(name="Enemy", base_power=3, base_toughness=3, owner=p2, controller=p2)
        # Target was on battlefield when spell was cast but left before resolution
        card.chosen_targets = [target]
        # Don't add to battlefield — simulates target already gone
        top_card = Creature(name="TopCard", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(top_card)
        card.on_resolve(game)
        # No surveil — spell fizzled
        gy = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert len(gy) == 0
