"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Covers:
  1. Static card properties (name, mana cost, P/T, card types, subtypes).
  2. ETB trigger registration (registers a trigger for EntersBattlefieldTriggeredEvent).
  3. ETB trigger fires for the Emeritus itself and not unrelated creatures.
  4. ETB effect: creates a 1/1 white-and-black Inkling token with flying for the target player.
  5. Inkling token properties: is_token, 1/1, flying, Inkling subtype.
  6. Prepared mechanic: card starts unprepared (prepared == False).
  7. Prepared condition: becomes prepared when an opponent controls strictly more creatures.
  8. Prepared condition: does NOT become prepared when creature counts are equal.
  9. Prepared condition: does NOT become prepared when controller has more creatures.
 10. Swords to Plowshares copy effect: exiles the target creature from the battlefield.
 11. Swords to Plowshares copy effect: target's controller gains life equal to target's power.
 12. After casting the prepared spell copy, the card is no longer prepared.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceProperties:
    """Static card data must match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Emeritus of Truce" in card.name

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_base_power(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3

    def test_base_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_toughness == 3

    def test_card_types_include_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtypes_include_cat(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes

    def test_subtypes_include_cleric(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cleric" in card.subtypes


# ---------------------------------------------------------------------------
# Prepared attribute
# ---------------------------------------------------------------------------


class TestPreparedAttribute:
    """The card must expose a 'prepared' boolean, defaulting to False."""

    def test_prepared_defaults_to_false(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.prepared is False

    def test_prepared_can_be_set_to_true(self) -> None:
        """prepared is writable — the ETB trigger sets it."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        card.prepared = True
        assert card.prepared is True

    def test_prepared_can_be_reset_to_false(self) -> None:
        """After casting the copy, prepared is reset to False."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        card.prepared = True
        card.prepared = False
        assert card.prepared is False


# ---------------------------------------------------------------------------
# ETB trigger registration
# ---------------------------------------------------------------------------


class TestEmeritusETBTriggerRegistration:
    """register_triggers must wire a trigger for EntersBattlefieldTriggeredEvent."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())

        assert after > before

    def test_registered_trigger_is_for_etb_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)

        etb_triggers = [
            t for t in triggers
            if t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert len(etb_triggers) >= 1

    def test_registered_trigger_has_correct_source(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)

        assert len(triggers) >= 1
        assert all(t.source is card for t in triggers)

    def test_registered_trigger_has_correct_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [t for t in triggers if t.event_type is EntersBattlefieldTriggeredEvent]

        assert len(etb_triggers) >= 1
        assert etb_triggers[0].controller is p1


# ---------------------------------------------------------------------------
# ETB trigger firing
# ---------------------------------------------------------------------------


class TestEmeritusETBTriggerFiring:
    """The ETB trigger fires when the Emeritus itself enters the battlefield,
    based on an EntersBattlefieldTriggeredEvent that references the card."""

    def test_trigger_fires_when_emeritus_enters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        before = len(game.stack)
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        after = len(game.stack)

        assert after > before

    def test_trigger_does_not_fire_for_unrelated_creature(self) -> None:
        """The ETB trigger is specific to this permanent, not all creatures."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        other = Creature(name="Other Bear", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)

        before = len(game.stack)
        event = EntersBattlefieldTriggeredEvent(permanent=other, controller=p1)
        game.trigger_manager.fire_event(game, event)
        after = len(game.stack)

        assert after == before

    def test_trigger_effect_callable_is_not_none(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [t for t in triggers if t.event_type is EntersBattlefieldTriggeredEvent]
        assert len(etb_triggers) >= 1
        assert etb_triggers[0].effect is not None


# ---------------------------------------------------------------------------
# ETB effect: Inkling token creation
# ---------------------------------------------------------------------------


class TestInklingTokenCreation:
    """When the ETB trigger resolves, a 1/1 white-and-black Inkling token
    with flying is created on the target player's battlefield."""

    def _get_etb_effect(self, game, card):
        """Helper: register triggers and return the ETB trigger's effect callable."""
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [t for t in triggers if t.event_type is EntersBattlefieldTriggeredEvent]
        assert etb_triggers, "No ETB trigger registered"
        return etb_triggers[0].effect

    def test_etb_effect_adds_creature_to_a_battlefield(self) -> None:
        """Resolving the ETB effect creates a token on some player's battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        # Script p1 to choose p1 as the target player for token creation.
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)

        before_total = (
            len(game.get_battlefield(p1).get_all())
            + len(game.get_battlefield(p2).get_all())
        )
        effect(game)
        after_total = (
            len(game.get_battlefield(p1).get_all())
            + len(game.get_battlefield(p2).get_all())
        )

        assert after_total == before_total + 1

    def test_etb_token_has_inkling_subtype(self) -> None:
        """The created token has the Inkling subtype."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)
        effect(game)

        bf = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf
            if isinstance(obj, Creature)
            and "Inkling" in getattr(obj, "subtypes", set())
        ]
        assert len(inkling_tokens) >= 1

    def test_etb_token_is_one_one(self) -> None:
        """The Inkling token is a 1/1."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)
        effect(game)

        bf = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf
            if isinstance(obj, Creature)
            and "Inkling" in getattr(obj, "subtypes", set())
        ]
        assert len(inkling_tokens) >= 1
        tok = inkling_tokens[0]
        assert tok.base_power == 1
        assert tok.base_toughness == 1

    def test_etb_token_has_flying(self) -> None:
        """The Inkling token has flying."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)
        effect(game)

        bf = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf
            if isinstance(obj, Creature)
            and "Inkling" in getattr(obj, "subtypes", set())
        ]
        assert len(inkling_tokens) >= 1
        tok = inkling_tokens[0]
        assert Keyword.FLYING in tok.keywords

    def test_etb_token_is_flagged_as_token(self) -> None:
        """The Inkling token has is_token == True."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)
        effect(game)

        bf = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf
            if isinstance(obj, Creature)
            and "Inkling" in getattr(obj, "subtypes", set())
        ]
        assert len(inkling_tokens) >= 1
        tok = inkling_tokens[0]
        assert tok.is_token is True

    def test_etb_creates_token_for_p2_when_p2_targeted(self) -> None:
        """When p2 is targeted, the token lands on p2's battlefield, not p1's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p2)

        effect = self._get_etb_effect(game, card)
        before_p2 = len(game.get_battlefield(p2).get_all())
        effect(game)
        after_p2 = len(game.get_battlefield(p2).get_all())

        assert after_p2 == before_p2 + 1


# ---------------------------------------------------------------------------
# Prepared condition: set by ETB trigger
# ---------------------------------------------------------------------------


class TestPreparedCondition:
    """The ETB effect conditionally sets prepared=True when an opponent
    controls strictly more creatures than the card's controller."""

    def _get_etb_effect(self, game, card):
        """Helper: register triggers and return the ETB trigger's effect callable."""
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [t for t in triggers if t.event_type is EntersBattlefieldTriggeredEvent]
        assert etb_triggers, "No ETB trigger registered"
        return etb_triggers[0].effect

    def test_becomes_prepared_when_opponent_has_strictly_more_creatures(self) -> None:
        """With opponent having 2 creatures and controller having 0 (excluding self),
        the card should become prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        # p2 has 2 creatures; p1 has 0 (card is not on battlefield yet)
        opp_creature_1 = Creature(name="Opp1", owner=p2, controller=p2,
                                   base_power=1, base_toughness=1)
        opp_creature_2 = Creature(name="Opp2", owner=p2, controller=p2,
                                   base_power=1, base_toughness=1)
        set_board_state(game, 1, battlefield=[opp_creature_1, opp_creature_2])

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)
        effect(game)

        assert card.prepared is True

    def test_does_not_become_prepared_when_equal_creatures(self) -> None:
        """Equal creature counts: opponent does NOT have strictly more, so NOT prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        # p1 and p2 each have 1 creature (not counting the Emeritus itself)
        my_creature = Creature(name="MyBear", owner=p1, controller=p1,
                               base_power=2, base_toughness=2)
        opp_creature = Creature(name="OppBear", owner=p2, controller=p2,
                                base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[opp_creature])

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)
        effect(game)

        assert card.prepared is False

    def test_does_not_become_prepared_when_controller_has_more_creatures(self) -> None:
        """Controller having more creatures: not prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        # p1 has 2 creatures, p2 has 0
        my_1 = Creature(name="MyBear1", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        my_2 = Creature(name="MyBear2", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[my_1, my_2])

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)
        effect(game)

        assert card.prepared is False

    def test_does_not_become_prepared_when_both_have_zero_creatures(self) -> None:
        """0 vs 0 (empty battlefields): not prepared."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)
        effect(game)

        assert card.prepared is False

    def test_prepared_state_is_false_by_default_without_etb(self) -> None:
        """Without any ETB firing, prepared defaults to False."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.prepared is False


# ---------------------------------------------------------------------------
# Swords to Plowshares copy effect
# ---------------------------------------------------------------------------


class TestSwordsToPlowsharesEffect:
    """While prepared, casting the Swords to Plowshares copy should:
      - exile the target creature from the battlefield;
      - give the target creature's controller life equal to the creature's power;
      - set card.prepared = False.

    The prepared copy is invoked via card.resolve_prepared_spell(game) when
    card.chosen_targets is set to [target_creature].
    """

    def test_exiles_target_creature(self) -> None:
        """The target creature is moved from the battlefield to exile."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Target Bear", owner=p2, controller=p2,
                          base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        card.chosen_targets = [target]

        card.resolve_prepared_spell(game)

        # Target creature should now be in exile, not on battlefield.
        p2_bf = game.get_battlefield(p2).get_all()
        assert target not in p2_bf

        p2_exile = game.get_exile(p2).get_all()
        assert target in p2_exile

    def test_target_controller_gains_life_equal_to_power(self) -> None:
        """The target creature's controller gains life equal to target's power."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Big Bear", owner=p2, controller=p2,
                          base_power=5, base_toughness=5)
        set_board_state(game, 1, battlefield=[target])

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        card.chosen_targets = [target]

        starting_life = p2.life
        card.resolve_prepared_spell(game)

        assert p2.life == starting_life + 5

    def test_life_gain_matches_target_power_exactly(self) -> None:
        """Life gain equals exactly the target's current power (1 in this case)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Elf", owner=p2, controller=p2,
                          base_power=1, base_toughness=1)
        set_board_state(game, 1, battlefield=[target])

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        card.chosen_targets = [target]

        starting_life = p2.life
        card.resolve_prepared_spell(game)

        assert p2.life == starting_life + 1

    def test_resolving_prepared_spell_unprepares_card(self) -> None:
        """After resolve_prepared_spell is called, card.prepared becomes False."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Target", owner=p2, controller=p2,
                          base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        card.chosen_targets = [target]

        card.resolve_prepared_spell(game)

        assert card.prepared is False

    def test_no_target_noop_does_not_raise(self) -> None:
        """If chosen_targets is empty or unset, resolve_prepared_spell
        must not raise an exception (graceful no-op)."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        card.chosen_targets = []

        # Must not raise.
        card.resolve_prepared_spell(game)

    def test_target_controller_is_opponent_not_caster(self) -> None:
        """It is the target creature's controller (p2) who gains life,
        not the spell caster (p1)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Target", owner=p2, controller=p2,
                          base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[target])

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        card.chosen_targets = [target]

        p1_life_before = p1.life
        p2_life_before = p2.life
        card.resolve_prepared_spell(game)

        # p2 gains life; p1 gains nothing.
        assert p2.life == p2_life_before + 4
        assert p1.life == p1_life_before


# ---------------------------------------------------------------------------
# Inkling token color identity
# ---------------------------------------------------------------------------


class TestInklingTokenColorIdentity:
    """The oracle text specifies the token is 'white and black'.
    After the Implementer adds a first-class `colors: set` attribute to
    Creature/token instances, the Inkling token must report exactly both colors.
    """

    def _get_etb_effect(self, game, card):
        """Helper: register triggers and return the ETB trigger's effect callable."""
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [t for t in triggers if t.event_type is EntersBattlefieldTriggeredEvent]
        assert etb_triggers, "No ETB trigger registered"
        return etb_triggers[0].effect

    def _get_inkling_token(self, game, p1):
        """Helper: return the first Inkling token on p1's battlefield."""
        bf = game.get_battlefield(p1).get_all()
        tokens = [
            obj for obj in bf
            if isinstance(obj, Creature)
            and "Inkling" in getattr(obj, "subtypes", set())
        ]
        assert tokens, "No Inkling token found on battlefield"
        return tokens[0]

    def test_etb_token_colors_are_white_and_black(self) -> None:
        """The Inkling token must have colors == {'W', 'B'} (white and black)."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)
        effect(game)

        token = self._get_inkling_token(game, p1)
        assert hasattr(token, "colors"), (
            "Token must have a 'colors' attribute — engine needs colors support"
        )
        assert token.colors == {"W", "B"}, (
            f"Inkling token should be white and black, got: {token.colors!r}"
        )

    def test_etb_token_is_bicolor_not_monocolored(self) -> None:
        """The Inkling token must be BOTH white AND black — not just one color."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(p1)

        effect = self._get_etb_effect(game, card)
        effect(game)

        token = self._get_inkling_token(game, p1)
        assert hasattr(token, "colors"), (
            "Token must have a 'colors' attribute — engine needs colors support"
        )
        # Both colors must be present; neither white-only nor black-only is correct.
        assert "W" in token.colors, "Inkling token must include white (W)"
        assert "B" in token.colors, "Inkling token must include black (B)"
        # And there should be exactly two colors — no extras.
        assert len(token.colors) == 2, (
            f"Inkling token is bicolor; expected 2 colors, got {len(token.colors)}: {token.colors!r}"
        )
