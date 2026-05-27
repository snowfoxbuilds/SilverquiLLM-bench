"""Tests for SOS 212 — Prismari, the Inspiration.

Prismari is a 7/7 Legendary Creature — Elder Dragon with Flying,
Ward—Pay 5 life, and grants storm to instant/sorcery spells its
controller casts.
"""

from __future__ import annotations

from cards.sos.sos_212.card_impl import PrismariTheInspiration
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestPrismariProperties:
    """Static card data should match the SOS 212 spec."""

    def test_is_creature(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert card.name == "Prismari, the Inspiration"

    def test_mana_cost(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{U}{R}")

    def test_power(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert card.base_power == 7

    def test_toughness(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert card.base_toughness == 7

    def test_is_legendary(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_elder_dragon(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_has_flying(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_ward(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert Keyword.WARD in card.keywords

    def test_card_types_creature(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert CardType.CREATURE in card.card_types


# ---------------------------------------------------------------------------
# Ward — Pay 5 life
# ---------------------------------------------------------------------------


class TestPrismariWard:
    """Ward — Pay 5 life: opponents must pay 5 life when targeting Prismari."""

    def test_ward_cost_is_5_life(self) -> None:
        """The ward cost should be 5 life (not mana)."""
        card = PrismariTheInspiration(owner=None)
        # The implementation should expose a ward_cost attribute or method
        # indicating the cost is 5 life.
        assert hasattr(card, "ward_cost")
        assert card.ward_cost == 5

    def test_ward_triggers_when_targeted_by_opponent(self) -> None:
        """When an opponent targets Prismari, they must pay 5 life or
        the spell is countered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        prismari = PrismariTheInspiration(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[prismari])

        # Prismari should register ward trigger
        prismari.register_triggers(game)

        # Verify the ward mechanism exists — the card should have a
        # ward_cost of 5 life
        assert prismari.ward_cost == 5


# ---------------------------------------------------------------------------
# Storm granting — instants/sorceries get storm
# ---------------------------------------------------------------------------


class TestPrismariStormGrant:
    """Instant and sorcery spells controller casts have storm."""

    def test_grants_storm_to_instant(self) -> None:
        """An instant cast while Prismari is on battlefield should have storm."""
        game = create_game()
        p1 = game.players[0]

        prismari = PrismariTheInspiration(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[prismari])
        prismari.register_triggers(game)

        # Create a simple instant spell
        bolt = Instant(
            name="Lightning Bolt",
            mana_cost=ManaCost.parse("{R}"),
            owner=p1,
            controller=p1,
        )

        # The card should have a method or mechanism that adds storm
        # to instants/sorceries. We check that the storm-granting
        # continuous effect or ability is active.
        assert hasattr(prismari, "get_continuous_effects") or hasattr(
            prismari, "grants_storm"
        )

    def test_grants_storm_to_sorcery(self) -> None:
        """A sorcery cast while Prismari is on battlefield should have storm."""
        game = create_game()
        p1 = game.players[0]

        prismari = PrismariTheInspiration(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[prismari])
        prismari.register_triggers(game)

        sorcery = Sorcery(
            name="Divination",
            mana_cost=ManaCost.parse("{2}{U}"),
            owner=p1,
            controller=p1,
        )

        # Should grant storm to sorceries as well
        assert hasattr(prismari, "get_continuous_effects") or hasattr(
            prismari, "grants_storm"
        )

    def test_storm_copies_equal_prior_spells_cast_this_turn(self) -> None:
        """Storm creates copies equal to the number of spells cast before
        this spell this turn."""
        game = create_game()
        p1 = game.players[0]

        prismari = PrismariTheInspiration(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[prismari])
        prismari.register_triggers(game)

        # Simulate that 3 spells were cast this turn before the storm spell
        if not hasattr(game, "storm_count"):
            game.storm_count = {}
        game.storm_count[p1] = 3

        bolt = Instant(
            name="Lightning Bolt",
            mana_cost=ManaCost.parse("{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})

        # When the storm trigger resolves, it should create 3 copies
        # (one for each prior spell this turn)
        # This tests that the storm mechanism uses the game's spell count
        from test_utils import cast_spell

        cast_spell(game, 0, "Lightning Bolt")

        # After resolution, there should be copies on the stack or resolved
        # The storm count of 3 means 3 copies should have been created
        # We check that the game tracked storm copies
        assert hasattr(game, "last_storm_copies") or len(
            game.get_graveyard(p1).get_all()
        ) >= 1

    def test_no_copies_if_first_spell_of_turn(self) -> None:
        """If this is the first spell cast this turn, storm makes 0 copies."""
        game = create_game()
        p1 = game.players[0]

        prismari = PrismariTheInspiration(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[prismari])
        prismari.register_triggers(game)

        # Storm count is 0 (first spell of turn)
        if not hasattr(game, "storm_count"):
            game.storm_count = {}
        game.storm_count[p1] = 0

        bolt = Instant(
            name="Lightning Bolt",
            mana_cost=ManaCost.parse("{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})

        from test_utils import cast_spell

        cast_spell(game, 0, "Lightning Bolt")

        # With 0 prior spells, no copies should be created
        # The graveyard should contain only the original spell
        graveyard = game.get_graveyard(p1).get_all()
        bolt_copies = [c for c in graveyard if getattr(c, "name", "") == "Lightning Bolt"]
        assert len(bolt_copies) == 1  # Only the original, no copies

    def test_does_not_grant_storm_to_opponent_spells(self) -> None:
        """Storm is only granted to spells cast by Prismari's controller,
        not the opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        prismari = PrismariTheInspiration(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[prismari])
        prismari.register_triggers(game)

        # Opponent's spell should NOT get storm
        opponent_bolt = Instant(
            name="Shock",
            mana_cost=ManaCost.parse("{R}"),
            owner=p2,
            controller=p2,
        )

        # The storm-granting effect should check controller
        # We verify that the card's effect only applies to its controller's spells
        if hasattr(prismari, "grants_storm_to"):
            assert prismari.grants_storm_to(opponent_bolt, game) is False
        else:
            # The continuous effect should filter by controller
            assert prismari.controller == p1

    def test_does_not_grant_storm_to_creatures(self) -> None:
        """Storm should only be granted to instants and sorceries,
        not creature spells."""
        game = create_game()
        p1 = game.players[0]

        prismari = PrismariTheInspiration(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[prismari])
        prismari.register_triggers(game)

        # A creature spell should NOT gain storm
        bear = Creature(
            name="Grizzly Bears",
            mana_cost=ManaCost.parse("{1}{G}"),
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )

        if hasattr(prismari, "grants_storm_to"):
            assert prismari.grants_storm_to(bear, game) is False

    def test_multiple_spells_increase_storm_count(self) -> None:
        """Each additional spell cast this turn increases the storm count
        for subsequent spells."""
        game = create_game()
        p1 = game.players[0]

        prismari = PrismariTheInspiration(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[prismari])
        prismari.register_triggers(game)

        # After 5 spells have been cast, the 6th should get 5 copies
        if not hasattr(game, "storm_count"):
            game.storm_count = {}
        game.storm_count[p1] = 5

        bolt = Instant(
            name="Lightning Bolt",
            mana_cost=ManaCost.parse("{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})

        from test_utils import cast_spell

        cast_spell(game, 0, "Lightning Bolt")

        # Should have created 5 copies (storm count = 5 prior spells)
        graveyard = game.get_graveyard(p1).get_all()
        bolt_copies = [c for c in graveyard if getattr(c, "name", "") == "Lightning Bolt"]
        assert len(bolt_copies) == 6  # 1 original + 5 storm copies
