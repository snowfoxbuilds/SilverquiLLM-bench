"""Rewritten audited tests for Improvisation Capstone (sos_120).

Verifies correct oracle behavior:
- Identity: {5}{R}{R} Sorcery — Lesson, CMC 7, no Keyword.PARADIGM
- Exile from library until MV sum >= 4
- Does not target opponent creatures
- Cast chosen exiled cards for free
- Paradigm exiles self (not graveyard)
- Paradigm recurring cast across 3 turn cycles
- Paradigm offer can be declined
"""

from __future__ import annotations

import pytest

from card_impl import ImprovisationCapstone

from engine.card import Creature, Sorcery, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import (
    card_colors,
    create_game,
    resolve_top,
    set_library_top,
    set_board_state,
    advance_to_phase,
)


class TestIdentity:
    """Identity tests — name, {5}{R}{R}, CMC 7, Sorcery, Lesson, Red, no Keyword.PARADIGM."""

    def test_identity(self) -> None:
        """Full identity: name, mana_cost {5}{R}{R}, CMC 7, Sorcery, Lesson subtype, Red color, no PARADIGM keyword."""
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=None)

        # Name
        assert card.name == "Improvisation Capstone"

        # Type
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types

        # Mana cost: {5}{R}{R} → generic=5, 2 red pips
        assert card.mana_cost.generic == 5
        assert card.mana_cost.pips.get(ManaType.RED) == 2

        # CMC 7
        assert card.mana_cost.cmc == 7

        # Lesson subtype
        assert "Lesson" in card.subtypes

        # Color: Red
        assert "R" in card_colors(card)

        # Paradigm is an ability word, NOT a keyword — no Keyword.PARADIGM
        if hasattr(Keyword, "PARADIGM"):
            assert not (Keyword.PARADIGM & card.keywords)


class TestExileFromLibraryUntilThreshold:
    """Exile cards from top of library until total MV >= 4."""

    def test_exile_until_mv_sum_ge_4(self) -> None:
        """Exiles cards one at a time until MV sum >= 4."""
        game = create_game(scripts=([False, False, False], []))
        player = game.players[0]

        # Library top: MV 1, MV 2, MV 2 (sum after 3 cards = 5 >= 4)
        c1 = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}), owner=player)
        c2 = Creature(name="Bear", mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}), owner=player, base_power=2, base_toughness=2)
        c3 = Instant(name="Shock", mana_cost=ManaCost(generic=1, pips={ManaType.RED: 1}), owner=player)
        # Bottom of library cards (should not be touched)
        filler = Creature(name="Filler", mana_cost=ManaCost(generic=5), owner=player, base_power=5, base_toughness=5)

        set_library_top(game, 0, [c1, c2, c3])
        # Add filler below
        player.zones[Zone.LIBRARY].add(filler, position="bottom")

        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        card.on_resolve(game)

        exile = player.zones[Zone.EXILE].get_all()
        # c1 (MV 1) + c2 (MV 2) = 3 < 4, so c3 (MV 2) also exiled => sum 5 >= 4
        assert c1 in exile
        assert c2 in exile
        assert c3 in exile
        # Filler should remain in library
        assert filler not in exile
        lib_cards = player.zones[Zone.LIBRARY].get_all()
        assert filler in lib_cards


class TestDoesNotTargetOpponentCreatures:
    """Improvisation Capstone does NOT target opponent creatures."""

    def test_no_targets(self) -> None:
        """get_targets returns empty — spell doesn't target."""
        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert targets == []

    def test_resolution_does_not_affect_opponent_board(self) -> None:
        """Resolution exiles from OWN library, not opponent creatures."""
        game = create_game(scripts=([False], []))
        player = game.players[0]
        opponent = game.players[1]

        opp_creature = Creature(name="Opp Bear", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp_creature])

        # Library with a single MV 4 card
        lib_card = Creature(name="BigGuy", mana_cost=ManaCost(generic=4), owner=player, base_power=4, base_toughness=4)
        set_library_top(game, 0, [lib_card])

        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        card.on_resolve(game)

        # Opponent's creature still on battlefield
        opp_bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert opp_creature in opp_bf


class TestCastChosenExiledCardsForFree:
    """May cast exiled cards without paying mana costs."""

    def test_cast_exiled_card_free(self) -> None:
        """Player can choose to cast an exiled card for free."""
        game = create_game(scripts=([True], []))
        player = game.players[0]

        # Single MV 4 creature in library
        lib_card = Creature(
            name="BigGuy",
            mana_cost=ManaCost(generic=4),
            owner=player,
            base_power=4,
            base_toughness=4,
        )
        set_library_top(game, 0, [lib_card])

        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        card.on_resolve(game)

        # The creature should be on the battlefield (cast for free)
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert lib_card in bf

    def test_decline_cast_exiled_card(self) -> None:
        """Player can decline to cast exiled cards."""
        game = create_game(scripts=([False], []))
        player = game.players[0]

        lib_card = Creature(
            name="BigGuy",
            mana_cost=ManaCost(generic=4),
            owner=player,
            base_power=4,
            base_toughness=4,
        )
        set_library_top(game, 0, [lib_card])

        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        card.on_resolve(game)

        # Card remains in exile (not cast)
        exile = player.zones[Zone.EXILE].get_all()
        assert lib_card in exile
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert lib_card not in bf


class TestParadigmExilesSelf:
    """Paradigm replacement effect routes self to exile, not graveyard."""

    def test_paradigm_exiles_self_on_resolution(self) -> None:
        """After resolution, Improvisation Capstone goes to exile (not GY).

        Card-side observable: the card registers a replacement effect that
        redirects its move-to-graveyard to exile. We feed the card-owned
        replacement a workspace-engine-native ``MoveToGraveyardReplacementEvent``
        (with a ``card`` field exposed via subclass) and verify the
        ``destination`` is mutated to ``"exile"``.
        """
        from dataclasses import dataclass, field
        from typing import Any
        from engine.events import MoveToGraveyardReplacementEvent

        game = create_game(scripts=([False], []))
        player = game.players[0]

        # Set up library with a single MV 4 card
        lib_card = Creature(
            name="BigGuy",
            mana_cost=ManaCost(generic=4),
            owner=player,
            base_power=4,
            base_toughness=4,
        )
        set_library_top(game, 0, [lib_card])

        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        card.owner = player

        # Register the replacement effect (happens on cast)
        card.register_replacement_effects(game)

        # Put card on stack zone (simulating cast) and resolve
        player.zones[Zone.STACK].add(card)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        card.on_resolve(game)
        player.zones[Zone.STACK].remove(card)

        # Build a workspace-native MoveToGraveyardReplacementEvent variant
        # carrying the resolving card, so the card-owned replacement can
        # match its identity check (``getattr(event, "spell", None) or
        # getattr(event, "card", None)``).
        @dataclass
        class _SpellGYEvent(MoveToGraveyardReplacementEvent):
            spell: Any = None

            @property  # override base property to expose the spell
            def card(self) -> Any:  # type: ignore[override]
                return self.spell

        event = _SpellGYEvent(spell=card, controller=player, owner=player)
        event = game.replacement_manager.apply(game, event)
        dest = getattr(event, "destination", "graveyard")

        if dest == "exile":
            player.zones[Zone.EXILE].add(card)
        else:
            player.zones[Zone.GRAVEYARD].add(card)

        # Card-side observable: paradigm replacement redirected to exile.
        assert dest == "exile"
        exile = player.zones[Zone.EXILE].get_all()
        assert card in exile
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card not in gy


class TestParadigmRecurringCast:
    """Paradigm recurring trigger: cast copy from exile at first main phase."""

    def test_recurring_cast_across_3_turns(self) -> None:
        """Paradigm trigger fires at each first main phase for 3 turns."""
        game = create_game(scripts=(
            # Turn setup: decline exiled card cast during resolve,
            # then 3x yes for recurring paradigm trigger casts
            [False, True, True, True],
            [],
        ))
        player = game.players[0]

        # Library with MV 4 card
        lib_card = Creature(
            name="BigGuy",
            mana_cost=ManaCost(generic=4),
            owner=player,
            base_power=4,
            base_toughness=4,
        )
        set_library_top(game, 0, [lib_card])

        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        card.owner = player

        # Register replacement effects and resolve
        card.register_replacement_effects(game)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        # Put on stack zone
        player.zones[Zone.STACK].add(card)
        card.on_resolve(game)

        # Move to exile via the card's registered paradigm replacement,
        # using a workspace-native MoveToGraveyardReplacementEvent variant.
        player.zones[Zone.STACK].remove(card)
        from dataclasses import dataclass
        from typing import Any
        from engine.events import MoveToGraveyardReplacementEvent

        @dataclass
        class _SpellGYEvent(MoveToGraveyardReplacementEvent):
            spell: Any = None

            @property
            def card(self) -> Any:  # type: ignore[override]
                return self.spell

        event = _SpellGYEvent(spell=card, controller=player, owner=player)
        event = game.replacement_manager.apply(game, event)
        dest = getattr(event, "destination", "graveyard")
        if dest == "exile":
            player.zones[Zone.EXILE].add(card)
        else:
            player.zones[Zone.GRAVEYARD].add(card)

        # Register the recurring Paradigm trigger via the canonical hook.
        card.register_triggers(game)

        # Drive three of the controller's first main phases. We fire whichever
        # event the card's own trigger listens for — read from the public
        # trigger registration — so the test never names an engine-internal
        # event class, then resolve the stack normally.
        registered = game.trigger_manager.get_triggers_for_source(card)
        assert registered, "Paradigm should register a recurring trigger from exile"
        main_phase_event = registered[0].event_type

        for _turn in range(3):
            game.trigger_manager.fire_event(game, main_phase_event(player=player))
            while not game.stack.is_empty():
                resolve_top(game)

        # Observable outcome: three free copies were cast and resolved into the
        # graveyard, while the original spell stays in exile.
        gy = player.zones[Zone.GRAVEYARD].get_all()
        copies = [c for c in gy if getattr(c, "name", None) == "Improvisation Capstone"]
        assert len(copies) == 3, f"Expected 3 recurring copies cast, got {len(copies)}"
        assert card in player.zones[Zone.EXILE].get_all()


class TestParadigmOfferCanBeDeclined:
    """Paradigm recurring trigger: may decline to cast."""

    def test_paradigm_offer_declined(self) -> None:
        """Player can decline the recurring paradigm cast each turn."""
        game = create_game(scripts=(
            # Decline exiled card cast during resolve, then decline paradigm
            [False, False],
            [],
        ))
        player = game.players[0]

        lib_card = Creature(
            name="BigGuy",
            mana_cost=ManaCost(generic=4),
            owner=player,
            base_power=4,
            base_toughness=4,
        )
        set_library_top(game, 0, [lib_card])

        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        card.owner = player

        card.register_replacement_effects(game)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        player.zones[Zone.STACK].add(card)
        card.on_resolve(game)

        player.zones[Zone.STACK].remove(card)
        from dataclasses import dataclass
        from typing import Any
        from engine.events import MoveToGraveyardReplacementEvent

        @dataclass
        class _SpellGYEvent(MoveToGraveyardReplacementEvent):
            spell: Any = None

            @property
            def card(self) -> Any:  # type: ignore[override]
                return self.spell

        event = _SpellGYEvent(spell=card, controller=player, owner=player)
        event = game.replacement_manager.apply(game, event)
        dest = getattr(event, "destination", "graveyard")
        if dest == "exile":
            player.zones[Zone.EXILE].add(card)
        else:
            player.zones[Zone.GRAVEYARD].add(card)

        card.register_triggers(game)

        # Fire the controller's first main phase (event type read from the
        # card's own trigger registration). The player declines the recurring
        # cast (scripted False), so no copy is created.
        registered = game.trigger_manager.get_triggers_for_source(card)
        assert registered, "Paradigm should register a recurring trigger from exile"
        main_phase_event = registered[0].event_type
        game.trigger_manager.fire_event(game, main_phase_event(player=player))
        while not game.stack.is_empty():
            resolve_top(game)

        # Observable: the original stays in exile and no copy was cast — neither
        # to the battlefield nor (for a resolved sorcery copy) the graveyard.
        assert card in player.zones[Zone.EXILE].get_all()
        for zone in (Zone.BATTLEFIELD, Zone.GRAVEYARD):
            names = [getattr(c, "name", None) for c in player.zones[zone].get_all()]
            assert "Improvisation Capstone" not in names
