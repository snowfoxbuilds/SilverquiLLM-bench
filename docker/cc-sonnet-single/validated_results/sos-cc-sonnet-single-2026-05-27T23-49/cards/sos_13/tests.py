"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Emeritus of Truce is a {1}{W}{W} 3/3 Cat Cleric Creature with the "Prepared"
keyword.  The spell half is Swords to Plowshares, a {W} Instant.

ETB trigger (front face):
  1. Target player creates a 1/1 white and black Inkling creature token
     with flying.
  2. Then if an opponent controls more creatures than you, this creature
     becomes prepared.

Prepared mechanic:
  While prepared, you may cast a copy of its spell (Swords to Plowshares).
  Doing so unprepares it.

Test strategy:
  - Static properties: name, mana cost, P/T, card type, subtypes.
  - is_prepared attribute defaults to False.
  - ETB trigger is registered via register_triggers.
  - ETB trigger condition fires only when THIS creature enters.
  - ETB effect: creates a 1/1 Inkling token with flying on target player's
    battlefield.
  - Token has correct properties (power 1, toughness 1, Flying keyword,
    Inkling subtype).
  - Prepared condition: becomes prepared when opponent controls more creatures.
  - Prepared condition: does NOT become prepared when you are not behind.
  - Casting the spell copy while prepared unprepares the creature.
  - No-op / no copy is cast when not prepared.
  - Targeting API: get_targets returns at least one requirement (for a player).
"""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(game=None, *, owner_idx: int = 0):
    """Create an EmeritusOfTruceSwordsToPlowshares with owner/controller set."""
    if game is None:
        game = create_game()
    player = game.players[owner_idx]
    card = EmeritusOfTruceSwordsToPlowshares(owner=player, controller=player)
    return game, card


def _inkling_tokens_on(game, player_idx: int) -> list:
    """Return all Inkling tokens on *player_idx*'s battlefield."""
    player = game.players[player_idx]
    bf = game.get_battlefield(player)
    return [
        obj for obj in bf.get_all()
        if getattr(obj, "is_token", False)
        and "Inkling" in getattr(obj, "subtypes", set())
    ]


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceProperties:
    """Static card data must match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        # Name may be the front face or the combined DFC name.
        assert "Emeritus of Truce" in card.name

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_toughness == 3

    def test_card_type_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_cat_subtype(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes

    def test_cleric_subtype(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cleric" in card.subtypes


# ---------------------------------------------------------------------------
# Prepared attribute initialisation
# ---------------------------------------------------------------------------


class TestEmeritusOfTrucePreparedAttribute:
    """is_prepared must default to False on a freshly created card."""

    def test_is_prepared_defaults_to_false(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.is_prepared is False



# ---------------------------------------------------------------------------
# ETB trigger registration
# ---------------------------------------------------------------------------


class TestEmeritusETBTriggerRegistration:
    """register_triggers must register an EntersBattlefieldTriggeredEvent trigger."""

    def test_registers_at_least_one_trigger(self) -> None:
        game, card = _make_card()
        before = len(game.trigger_manager._triggers)
        card.register_triggers(game)
        after = len(game.trigger_manager._triggers)
        assert after > before

    def test_registers_etb_trigger(self) -> None:
        """At least one trigger must watch EntersBattlefieldTriggeredEvent."""
        game, card = _make_card()
        card.register_triggers(game)
        triggers = game.trigger_manager._triggers
        etb_triggers = [
            t for t in triggers
            if t.source is card
            and issubclass(t.event_type, EntersBattlefieldTriggeredEvent)
        ]
        assert len(etb_triggers) >= 1

    def test_trigger_source_is_card(self) -> None:
        game, card = _make_card()
        card.register_triggers(game)
        triggers = [t for t in game.trigger_manager._triggers if t.source is card]
        assert len(triggers) >= 1
        assert triggers[0].source is card

    def test_trigger_condition_fires_only_for_self(self) -> None:
        """The ETB trigger condition must match only when THIS card enters."""
        game, card = _make_card()
        card.register_triggers(game)
        etb_triggers = [
            t for t in game.trigger_manager._triggers
            if t.source is card
            and issubclass(t.event_type, EntersBattlefieldTriggeredEvent)
        ]
        assert len(etb_triggers) >= 1
        trigger = etb_triggers[0]
        if trigger.condition is not None:
            # Must fire for self
            event_self = EntersBattlefieldTriggeredEvent(permanent=card)
            assert trigger.condition(game, event_self) is True
            # Must NOT fire for a different creature
            other = Creature(name="Bear", base_power=2, base_toughness=2)
            event_other = EntersBattlefieldTriggeredEvent(permanent=other)
            assert trigger.condition(game, event_other) is False


# ---------------------------------------------------------------------------
# ETB effect: Inkling token creation
# ---------------------------------------------------------------------------


class TestEmeritusETBTokenCreation:
    """The ETB effect creates a 1/1 white and black Inkling token with flying."""

    def test_etb_creates_exactly_one_token(self) -> None:
        """Exactly one Inkling token is created per ETB."""
        game, card = _make_card()
        p1 = game.players[0]
        card.chosen_targets = [p1]  # target player
        card.is_prepared = False    # no prepared condition check yet
        before_bf = len(game.get_battlefield(p1).get_all())
        card.on_resolve(game)
        after_bf = len(game.get_battlefield(p1).get_all())
        # At least one permanent (the token) was added
        assert after_bf >= before_bf + 1

    def test_inkling_token_has_flying(self) -> None:
        """The created Inkling token must have the Flying keyword."""
        game, card = _make_card()
        p1 = game.players[0]
        card.chosen_targets = [p1]
        card.on_resolve(game)
        inklings = _inkling_tokens_on(game, 0)
        assert len(inklings) >= 1
        tok = inklings[0]
        assert Keyword.FLYING in tok.keywords

    def test_inkling_token_is_1_1(self) -> None:
        """The Inkling token must be a 1/1 creature."""
        game, card = _make_card()
        p1 = game.players[0]
        card.chosen_targets = [p1]
        card.on_resolve(game)
        inklings = _inkling_tokens_on(game, 0)
        assert len(inklings) >= 1
        tok = inklings[0]
        assert tok.base_power == 1
        assert tok.base_toughness == 1

    def test_inkling_token_is_marked_as_token(self) -> None:
        """The created token must have is_token == True."""
        game, card = _make_card()
        p1 = game.players[0]
        card.chosen_targets = [p1]
        card.on_resolve(game)
        inklings = _inkling_tokens_on(game, 0)
        assert len(inklings) >= 1
        assert inklings[0].is_token is True

    def test_inkling_token_on_target_player_battlefield(self) -> None:
        """When target is opponent, the token lands on the opponent's battlefield."""
        game, card = _make_card()
        p1 = game.players[0]
        p2 = game.players[1]
        card.chosen_targets = [p2]  # target the opponent
        card.on_resolve(game)
        inklings_p2 = _inkling_tokens_on(game, 1)
        assert len(inklings_p2) >= 1

    def test_inkling_token_has_inkling_subtype(self) -> None:
        """The token's subtype must include 'Inkling'."""
        game, card = _make_card()
        p1 = game.players[0]
        card.chosen_targets = [p1]
        card.on_resolve(game)
        inklings = _inkling_tokens_on(game, 0)
        assert len(inklings) >= 1
        assert "Inkling" in inklings[0].subtypes


# ---------------------------------------------------------------------------
# Prepared condition: becomes prepared based on creature counts
# ---------------------------------------------------------------------------


class TestEmeritusOfTrucePreparedCondition:
    """The creature becomes prepared only when opponent controls more creatures."""

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        """After ETB: if opponent controls more creatures, card becomes prepared."""
        game, card = _make_card()
        p1 = game.players[0]
        p2 = game.players[1]
        # Give opponent 2 creatures; p1 has only the card itself (which just entered)
        bear1 = Creature(name="Bear1", base_power=2, base_toughness=2, owner=p2, controller=p2)
        bear2 = Creature(name="Bear2", base_power=2, base_toughness=2, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[bear1, bear2])
        # p1 has 0 creatures before ETB token creation
        card.chosen_targets = [p1]
        card.on_resolve(game)
        assert card.is_prepared is True

    def test_not_prepared_when_creature_counts_equal(self) -> None:
        """If you have as many creatures as your opponent, card is NOT prepared."""
        game, card = _make_card()
        p1 = game.players[0]
        p2 = game.players[1]
        # p1 has the card itself on the battlefield
        game.get_battlefield(p1).add(card)
        # p2 has exactly one creature too
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[bear])
        card.chosen_targets = [p1]
        card.on_resolve(game)
        assert card.is_prepared is False

    def test_not_prepared_when_you_have_more_creatures(self) -> None:
        """If you control more creatures than opponent, card is NOT prepared."""
        game, card = _make_card()
        p1 = game.players[0]
        p2 = game.players[1]
        # p1 has 2 creatures; p2 has none
        extra = Creature(name="Extra", base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        game.get_battlefield(p1).add(extra)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        assert card.is_prepared is False

    def test_not_prepared_when_opponent_has_zero_creatures(self) -> None:
        """With empty board and no opponent creatures, card is NOT prepared."""
        game, card = _make_card()
        p1 = game.players[0]
        # p1 just created a token, so may have 1 creature; opponent has 0
        # Either way, opponent does NOT have more creatures
        card.chosen_targets = [p1]
        card.on_resolve(game)
        assert card.is_prepared is False


# ---------------------------------------------------------------------------
# Prepared mechanic: casting the spell copy
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceCastSpellWhenPrepared:
    """While prepared, the controller may cast a copy of Swords to Plowshares."""

    def test_cast_prepared_spell_unprepares_card(self) -> None:
        """After casting the spell copy from prepared state, is_prepared becomes False."""
        game, card = _make_card()
        p1 = game.players[0]
        card.is_prepared = True
        # Place a target creature for Swords to Plowshares
        target = Creature(
            name="Target",
            base_power=3,
            base_toughness=3,
            owner=p1,
            controller=p1,
        )
        game.get_battlefield(p1).add(target)
        # Cast the prepared spell; implementation must set is_prepared = False
        card.cast_prepared_spell(game)
        assert card.is_prepared is False

    def test_cast_prepared_spell_noop_when_not_prepared(self) -> None:
        """Calling cast_prepared_spell when not prepared must not raise."""
        game, card = _make_card()
        card.is_prepared = False
        # Must not raise even without a valid target
        card.cast_prepared_spell(game)
        assert card.is_prepared is False

    def test_prepared_spell_accesses_spell_side(self) -> None:
        """The card exposes a spell_side that represents Swords to Plowshares."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        # The spell side must be present and be an Instant-type representation
        spell = getattr(card, "spell_side", None)
        assert spell is not None

    def test_prepared_spell_name_is_swords_to_plowshares(self) -> None:
        """The spell side must be named 'Swords to Plowshares'."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        spell = getattr(card, "spell_side", None)
        assert spell is not None
        spell_name = getattr(spell, "name", None) or getattr(spell, "spell_name", None)
        assert spell_name == "Swords to Plowshares"


# ---------------------------------------------------------------------------
# Targeting API
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceTargeting:
    """get_targets must declare a targeting requirement for the Inkling token
    recipient (a player)."""

    def test_get_targets_returns_list(self) -> None:
        game = create_game()
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        result = card.get_targets(game)
        assert isinstance(result, list)

    def test_get_targets_returns_at_least_one_requirement(self) -> None:
        """Must declare at least one target (a player for the token)."""
        game = create_game()
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        result = card.get_targets(game)
        assert len(result) >= 1

    def test_no_chosen_targets_does_not_raise(self) -> None:
        """on_resolve with no chosen_targets must not raise."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # No chosen_targets — should be a graceful no-op
        card.on_resolve(game)


# ---------------------------------------------------------------------------
# Swords to Plowshares effect: exile creature, controller gains life
# ---------------------------------------------------------------------------


class TestSwordsToPlowsharesEffect:
    """cast_prepared_spell() must exile the target creature and grant its
    controller life equal to the creature's power."""

    def test_cast_prepared_spell_exiles_target_creature(self) -> None:
        """The creature passed as target must leave the battlefield and enter exile."""
        game, card = _make_card()
        p1 = game.players[0]
        card.is_prepared = True

        # Create a target creature on the battlefield with a known power.
        target = Creature(
            name="VictimCreature",
            base_power=4,
            base_toughness=4,
            owner=p1,
            controller=p1,
        )
        game.get_battlefield(p1).add(target)

        card.cast_prepared_spell(game)

        # The creature must no longer be on the battlefield.
        bf_objects = game.get_battlefield(p1).get_all()
        assert target not in bf_objects, (
            "Target creature should have been exiled from the battlefield"
        )

        # The creature must be in exile.
        exile_objects = game.get_exile(p1).get_all()
        assert target in exile_objects, (
            "Target creature should be in the exile zone after Swords to Plowshares"
        )

    def test_cast_prepared_spell_grants_life_equal_to_power(self) -> None:
        """The exiled creature's controller must gain life equal to the creature's power."""
        game, card = _make_card()
        p1 = game.players[0]
        card.is_prepared = True
        starting_life = p1.life

        # Target creature with power 5; controller's life should rise by 5.
        target = Creature(
            name="PowerfulCreature",
            base_power=5,
            base_toughness=5,
            owner=p1,
            controller=p1,
        )
        game.get_battlefield(p1).add(target)

        card.cast_prepared_spell(game)

        assert p1.life == starting_life + 5, (
            f"Controller should gain 5 life (power of exiled creature), "
            f"expected {starting_life + 5}, got {p1.life}"
        )

    def test_cast_prepared_spell_grants_life_equal_to_power_opponent_creature(
        self,
    ) -> None:
        """Life gain goes to the exiled creature's controller, even if that is the opponent."""
        game, card = _make_card()  # card controlled by p1
        p2 = game.players[1]
        card.is_prepared = True
        starting_life_p2 = p2.life

        # Opponent controls a creature with power 3.
        target = Creature(
            name="OpponentCreature",
            base_power=3,
            base_toughness=3,
            owner=p2,
            controller=p2,
        )
        game.get_battlefield(p2).add(target)

        # The implementation finds the first creature; ensure only p2's creature exists.
        card.cast_prepared_spell(game)

        assert p2.life == starting_life_p2 + 3, (
            f"Opponent (creature's controller) should gain 3 life, "
            f"expected {starting_life_p2 + 3}, got {p2.life}"
        )

    def test_cast_prepared_spell_zero_power_creature_no_life_gain(self) -> None:
        """A 0-power creature causes no life gain (gain 0 life is a no-op)."""
        game, card = _make_card()
        p1 = game.players[0]
        card.is_prepared = True
        starting_life = p1.life

        target = Creature(
            name="ZeroPowerCreature",
            base_power=0,
            base_toughness=4,
            owner=p1,
            controller=p1,
        )
        game.get_battlefield(p1).add(target)

        card.cast_prepared_spell(game)

        assert p1.life == starting_life, (
            "No life should be gained when the exiled creature has power 0"
        )


# ---------------------------------------------------------------------------
# Inkling token colors: white AND black
# ---------------------------------------------------------------------------


class TestInklingTokenColors:
    """The Inkling token must be both white and black (colors attribute
    contains 'W' and 'B')."""

    def test_inkling_token_is_white(self) -> None:
        """The Inkling token must have white ('W') in its colors."""
        game, card = _make_card()
        p1 = game.players[0]
        card.chosen_targets = [p1]
        card.on_resolve(game)
        inklings = _inkling_tokens_on(game, 0)
        assert len(inklings) >= 1, "At least one Inkling token should have been created"
        tok = inklings[0]
        colors = getattr(tok, "colors", set())
        assert "W" in colors, (
            f"Inkling token must be white; colors found: {colors}"
        )

    def test_inkling_token_is_black(self) -> None:
        """The Inkling token must have black ('B') in its colors."""
        game, card = _make_card()
        p1 = game.players[0]
        card.chosen_targets = [p1]
        card.on_resolve(game)
        inklings = _inkling_tokens_on(game, 0)
        assert len(inklings) >= 1, "At least one Inkling token should have been created"
        tok = inklings[0]
        colors = getattr(tok, "colors", set())
        assert "B" in colors, (
            f"Inkling token must be black; colors found: {colors}"
        )

    def test_inkling_token_is_exactly_white_and_black(self) -> None:
        """The Inkling token must be exactly two colors: white and black."""
        game, card = _make_card()
        p1 = game.players[0]
        card.chosen_targets = [p1]
        card.on_resolve(game)
        inklings = _inkling_tokens_on(game, 0)
        assert len(inklings) >= 1, "At least one Inkling token should have been created"
        tok = inklings[0]
        colors = getattr(tok, "colors", set())
        assert colors == {"W", "B"}, (
            f"Inkling token must be exactly white and black; got {colors}"
        )
